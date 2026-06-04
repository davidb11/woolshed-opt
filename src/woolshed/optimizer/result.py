"""Data container returned by the MILP solver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class OptimizationResult:
    """Solver status, objective value and flows."""

    status: str
    objective_value: float
    # Total flow on each arc, keyed by (from_id, to_id).
    arc_flows: Dict[Tuple[str, str], float] = field(default_factory=dict)
    # Per-source flow on each arc, keyed by (source_id, from_id, to_id).
    commodity_flows: Dict[Tuple[str, str, str], float] = field(default_factory=dict)
    # Lines shown in the results panel.
    summary_lines: List[str] = field(default_factory=list)
