"""Build the feasible network arcs for each wool source.

An arc is allowed when the quality rules, process chain and any fixed
predecessor rules all agree.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from woolshed.core.models import Product, Source, Process
from woolshed.core.quality import QualityState, apply_transform, is_quality_compatible


def build_feasible_arcs(
    sources: List[Source],
    procs: List[Process],
    products: List[Product],
) -> Tuple[
    Dict[str, Set[str]],  # Source to first-stage process IDs.
    Dict[str, Dict[str, Set[str]]],  # Source to process-to-process arcs.
    Dict[str, Dict[str, Set[str]]],  # Source to process-to-product arcs.
    Dict[str, Dict[str, QualityState]],  # Quality after each process.
]:
    """Return feasible arcs and the quality reached after each process."""
    stages = sorted({t.stage for t in procs})

    # Group processes by stage.
    procs_at_stage: Dict[int, List[Process]] = {}
    for t in procs:
        procs_at_stage.setdefault(t.stage, []).append(t)

    # Store the reachable arcs for each source.
    arcs_st: Dict[str, Set[str]] = {}
    arcs_tt: Dict[str, Dict[str, Set[str]]] = {}
    arcs_tp: Dict[str, Dict[str, Set[str]]] = {}
    quality_after: Dict[str, Dict[str, QualityState]] = {}

    for src in sources:
        arcs_st[src.id] = set()
        arcs_tt[src.id] = {}
        arcs_tp[src.id] = {}
        quality_after[src.id] = {}

        first_stage = stages[0] if stages else None
        if first_stage is None:
            continue

        # Source to first-stage processes.
        for t in procs_at_stage.get(first_stage, []):
            if is_quality_compatible(src.quality, t.input_requirements):
                arcs_st[src.id].add(t.id)
                q_out = apply_transform(src.quality, t.output_transform)
                quality_after[src.id][t.id] = q_out

        # Walk the process stages in order.
        for si in range(len(stages) - 1):
            cur_stage = stages[si]
            nxt_stage = stages[si + 1]
            for t1 in procs_at_stage.get(cur_stage, []):
                if t1.id not in quality_after[src.id]:
                    continue  # This source cannot reach the process.
                q_in_to_next = quality_after[src.id][t1.id]
                for t2 in procs_at_stage.get(nxt_stage, []):
                    # Fixed predecessors replace the normal chain and quality checks.
                    if getattr(t2, "fixed_predecessor_ids", None) is not None:
                        if t1.id not in t2.fixed_predecessor_ids:
                            continue
                    else:
                        # Processes must share a chain, unless one is "main".
                        if (
                            t1.chain != t2.chain
                            and t1.chain != "main"
                            and t2.chain != "main"
                        ):
                            continue
                        if not is_quality_compatible(q_in_to_next, t2.input_requirements):
                            continue
                    arcs_tt[src.id].setdefault(t1.id, set()).add(t2.id)
                    q_out = apply_transform(q_in_to_next, t2.output_transform)
                    quality_after[src.id][t2.id] = q_out

        # Process to product.
        for t in procs:
            if t.id not in quality_after[src.id]:
                continue
            q_out = quality_after[src.id][t.id]
            for p in products:
                # Keep products on their required chain.
                if p.required_chain and t.chain != p.required_chain:
                    continue
                # Some products require a minimum processing stage.
                if p.required_min_stage is not None and t.stage < p.required_min_stage:
                    continue
                if is_quality_compatible(q_out, p.quality_requirements):
                    arcs_tp[src.id].setdefault(t.id, set()).add(p.id)

    return arcs_st, arcs_tt, arcs_tp, quality_after
