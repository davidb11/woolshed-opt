"""MILP solver for the WoolShed value chain.

PuLP builds the model. GLPK is tried first, then CBC is used as a fallback.
Each source is treated as its own commodity so quality can be tracked exactly
along every path.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import pulp

from woolshed.core.models import Parameters, Product, Source, Process
from woolshed.core.geo import haversine_km

from .feasibility import build_feasible_arcs
from .result import OptimizationResult

logger = logging.getLogger(__name__)


def optimize(
    sources: List[Source],
    procs: List[Process],
    products: List[Product],
    params: Parameters,
    objective: str = "max_profit",
) -> OptimizationResult:
    """Build and solve the model for the selected objective."""

    src_by_id = {s.id: s for s in sources}
    prod_by_id = {p.id: p for p in products}

    # Look up each entity location by ID.
    loc: Dict[str, Tuple[float, float]] = {}
    for s in sources:
        loc[s.id] = (s.lat, s.lon)
    for t in procs:
        loc[t.id] = (t.lat, t.lon)
    for p in products:
        loc[p.id] = (p.lat, p.lon)

    def dist(a: str, b: str) -> float:
        la, lo = loc[a]
        lb, lo2 = loc[b]
        return haversine_km(la, lo, lb, lo2)

    # Build the feasible network.
    arcs_st, arcs_tt, arcs_tp, _ = build_feasible_arcs(sources, procs, products)

    # Create the PuLP problem.
    sense = pulp.LpMaximize if objective == "max_profit" else pulp.LpMinimize
    prob = pulp.LpProblem("WoolShed", sense)

    # Decision variables. Each flow is indexed by source.
    x_st: Dict[Tuple[str, str], pulp.LpVariable] = {}
    x_tt: Dict[Tuple[str, str, str], pulp.LpVariable] = {}
    x_tp: Dict[Tuple[str, str, str], pulp.LpVariable] = {}

    for s in sources:
        for t_id in arcs_st.get(s.id, set()):
            x_st[(s.id, t_id)] = pulp.LpVariable(
                f"xst_{s.id}_{t_id}", lowBound=0, cat="Continuous"
            )
        for t1_id, t2_set in arcs_tt.get(s.id, {}).items():
            for t2_id in t2_set:
                x_tt[(s.id, t1_id, t2_id)] = pulp.LpVariable(
                    f"xtt_{s.id}_{t1_id}_{t2_id}", lowBound=0, cat="Continuous"
                )
        for t_id, p_set in arcs_tp.get(s.id, {}).items():
            for p_id in p_set:
                x_tp[(s.id, t_id, p_id)] = pulp.LpVariable(
                    f"xtp_{s.id}_{t_id}_{p_id}", lowBound=0, cat="Continuous"
                )

    if not x_st:
        return OptimizationResult(
            status="Infeasible",
            objective_value=0.0,
            summary_lines=["No feasible source->process arcs (quality mismatch)."],
        )

    # Constraints.

    # Limit each source to its available supply.
    for s in sources:
        out_vars = [
            x_st[(s.id, t)]
            for t in arcs_st.get(s.id, set())
            if (s.id, t) in x_st
        ]
        if out_vars:
            prob += pulp.lpSum(out_vars) <= s.quantity_kg, f"src_cap_{s.id}"

    # Keep mass balanced at each process for each source.
    for s in sources:
        for t in procs:
            # Incoming mass for this source.
            inc: List[pulp.LpVariable] = []
            if (s.id, t.id) in x_st:
                inc.append(x_st[(s.id, t.id)])
            for t_prev in procs:
                if (s.id, t_prev.id, t.id) in x_tt:
                    inc.append(x_tt[(s.id, t_prev.id, t.id)])
            if not inc:
                continue

            input_mass = pulp.lpSum(inc)
            produced = t.conversion_pct / 100.0 * input_mass

            # Outgoing mass for this source.
            out: List[pulp.LpVariable] = []
            for t2 in procs:
                if (s.id, t.id, t2.id) in x_tt:
                    out.append(x_tt[(s.id, t.id, t2.id)])
            for p in products:
                if (s.id, t.id, p.id) in x_tp:
                    out.append(x_tp[(s.id, t.id, p.id)])

            if out:
                prob += pulp.lpSum(out) <= produced, f"bal_{s.id}_{t.id}"

    # Limit process capacity across all sources.
    for t in procs:
        cap_terms: List[pulp.LpVariable] = []
        for s in sources:
            if (s.id, t.id) in x_st:
                cap_terms.append(x_st[(s.id, t.id)])
            for t_prev in procs:
                if (s.id, t_prev.id, t.id) in x_tt:
                    cap_terms.append(x_tt[(s.id, t_prev.id, t.id)])
        if cap_terms and t.max_capacity_kg < 1e8:
            prob += pulp.lpSum(cap_terms) <= t.max_capacity_kg, f"cap_{t.id}"

    # Apply product demand bounds.
    for p in products:
        prod_in: List[pulp.LpVariable] = []
        for s in sources:
            for t in procs:
                if (s.id, t.id, p.id) in x_tp:
                    prod_in.append(x_tp[(s.id, t.id, p.id)])
        if prod_in:
            total_in = pulp.lpSum(prod_in)
            if p.demand_max_kg < 1e8:
                prob += total_in <= p.demand_max_kg, f"dmax_{p.id}"
            if p.demand_min_kg > 0:
                prob += total_in >= p.demand_min_kg, f"dmin_{p.id}"

    # Objective terms.

    # Cost.
    source_cost = pulp.lpSum(
        x_st[(s_id, t_id)]
        * (src_by_id[s_id].cost_per_kg + params.transport_cost_per_kg_km * dist(s_id, t_id))
        for (s_id, t_id) in x_st
    )

    processing_cost = []
    for t in procs:
        t_input: List = []
        for s in sources:
            if (s.id, t.id) in x_st:
                t_input.append(x_st[(s.id, t.id)])
            for t_prev in procs:
                if (s.id, t_prev.id, t.id) in x_tt:
                    t_input.append(x_tt[(s.id, t_prev.id, t.id)])
        if t_input:
            processing_cost.append(pulp.lpSum(t_input) * t.cost_per_kg)

    transport_tt = pulp.lpSum(
        x_tt[key] * params.transport_cost_per_kg_km * dist(key[1], key[2])
        for key in x_tt
    )
    transport_tp = pulp.lpSum(
        x_tp[key] * params.transport_cost_per_kg_km * dist(key[1], key[2])
        for key in x_tp
    )

    total_cost = source_cost + pulp.lpSum(processing_cost) + transport_tt + transport_tp

    # Revenue.
    revenue = pulp.lpSum(
        x_tp[(s_id, t_id, p_id)] * prod_by_id[p_id].price_per_kg
        for (s_id, t_id, p_id) in x_tp
    )

    # Impact uses the same shape as cost.
    source_impact = pulp.lpSum(
        x_st[(s_id, t_id)]
        * (src_by_id[s_id].impact_per_kg + params.transport_impact_per_kg_km * dist(s_id, t_id))
        for (s_id, t_id) in x_st
    )

    processing_impact = []
    for t in procs:
        t_input: List = []
        for s in sources:
            if (s.id, t.id) in x_st:
                t_input.append(x_st[(s.id, t.id)])
            for t_prev in procs:
                if (s.id, t_prev.id, t.id) in x_tt:
                    t_input.append(x_tt[(s.id, t_prev.id, t.id)])
        if t_input:
            processing_impact.append(pulp.lpSum(t_input) * t.impact_per_kg)

    transport_tt_imp = pulp.lpSum(
        x_tt[key] * params.transport_impact_per_kg_km * dist(key[1], key[2])
        for key in x_tt
    )
    transport_tp_imp = pulp.lpSum(
        x_tp[key] * params.transport_impact_per_kg_km * dist(key[1], key[2])
        for key in x_tp
    )

    total_impact = (
        source_impact + pulp.lpSum(processing_impact) + transport_tt_imp + transport_tp_imp
    )

    # Set the requested objective.
    if objective == "max_profit":
        prob += revenue - total_cost
    elif objective == "min_cost":
        prob += total_cost
    elif objective == "min_impact":
        prob += total_impact
    else:
        raise ValueError(f"Unknown objective: {objective}")

    # Solve the model.
    try:
        solver = pulp.GLPK_CMD(msg=False)
        prob.solve(solver)
    except Exception:
        logger.warning("GLPK not found - falling back to default solver")
        prob.solve(pulp.PULP_CBC_CMD(msg=False))

    status = pulp.LpStatus[prob.status]
    obj_val = pulp.value(prob.objective) if prob.objective is not None else 0.0

    # Extract the result flows.
    arc_flows: Dict[Tuple[str, str], float] = {}
    commodity_flows: Dict[Tuple[str, str, str], float] = {}
    lines: List[str] = [f"Status: {status}", f"Objective value: {obj_val:.2f}"]

    def _add(from_id, to_id, val, src_id=None):
        if val and val > 1e-6:
            arc_flows[(from_id, to_id)] = arc_flows.get((from_id, to_id), 0) + val
            if src_id:
                commodity_flows[(src_id, from_id, to_id)] = val

    for (s_id, t_id), var in x_st.items():
        _add(s_id, t_id, var.value(), s_id)
    for (s_id, t1_id, t2_id), var in x_tt.items():
        _add(t1_id, t2_id, var.value(), s_id)
    for (s_id, t_id, p_id), var in x_tp.items():
        _add(t_id, p_id, var.value(), s_id)

    for (a, b), val in sorted(arc_flows.items(), key=lambda x: -x[1]):
        lines.append(f"  {a} -> {b}: {val:.1f} kg")

    # Product totals.
    lines.append("")
    for p in products:
        total = sum(v for (a, b), v in arc_flows.items() if b == p.id)
        if total > 1e-6:
            lines.append(f"  Product {p.id} ({p.name}): {total:.1f} kg")

    # Cost, impact and revenue breakdown.
    if status == "Optimal":
        rev_val = sum(
            (var.value() or 0) * prod_by_id[p_id].price_per_kg
            for (s_id, t_id, p_id), var in x_tp.items()
        )
        lines.append(f"\n  Revenue:  {rev_val:>10.2f} EUR")
        lines.append(f"  Cost:     {pulp.value(total_cost):>10.2f} EUR")
        lines.append(f"  Impact:   {pulp.value(total_impact):>10.2f} units")
        lines.append(f"  Profit:   {rev_val - pulp.value(total_cost):>10.2f} EUR")

    return OptimizationResult(
        status=status,
        objective_value=obj_val or 0.0,
        arc_flows=arc_flows,
        commodity_flows=commodity_flows,
        summary_lines=lines,
    )
