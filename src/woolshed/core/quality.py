"""Quality classes and matching rules for wool batches.

The model tracks fineness, colour, staple length and scouring yield as small
integer classes. Processes and products can then state which classes they
accept and how a process changes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

# Quality class labels.

FINENESS_CLASSES: Dict[int, str] = {
    1: "Ultrafine (< 17 µm)",
    2: "Fine (17–20 µm)",
    3: "Medium (20–25 µm)",
    4: "Strong (25–30 µm)",
    5: "Coarse (> 30 µm)",
}

COLOR_CLASSES: Dict[int, str] = {
    1: "White",
    2: "Cream",
    3: "Pale",
    4: "Grey",
    5: "Brown",
    6: "Black",
}

STAPLE_LENGTH_CLASSES: Dict[int, str] = {
    1: "Very Short (< 4 cm)",
    2: "Short (4–7 cm)",
    3: "Medium (7–10 cm)",
    4: "Long (10–15 cm)",
    5: "Very Long (> 15 cm)",
}

SCOURING_YIELD_CLASSES: Dict[int, str] = {
    1: "Very Low (< 40 %)",
    2: "Low (40–50 %)",
    3: "Medium (50–65 %)",
    4: "High (65–80 %)",
    5: "Very High (> 80 %)",
}


# Quality dataclasses.


@dataclass
class QualityState:
    """Current quality of a wool batch (four discrete descriptors)."""

    fineness: Optional[int] = None  # Classes 1-5.
    color: Optional[int] = None  # Classes 1-6.
    staple_length: Optional[int] = None  # Classes 1-5.
    scouring_yield: Optional[int] = None  # Classes 1-5.

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def from_dict(cls, d: dict) -> "QualityState":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class QualityRequirement:
    """Acceptable input quality ranges for a process or product."""

    fineness_min: Optional[int] = None
    fineness_max: Optional[int] = None
    color_accepted: Optional[List[int]] = None  # Accepted colour classes.
    staple_length_min: Optional[int] = None
    staple_length_max: Optional[int] = None
    scouring_yield_min: Optional[int] = None
    scouring_yield_max: Optional[int] = None


@dataclass
class QualityTransform:
    """How a process changes wool quality.

    Each value can be:
      - ``None`` to leave the property unchanged.
      - an ``int`` to set the output class.
      - ``"remove"`` when the property no longer applies.
    """

    fineness: Optional[object] = None
    color: Optional[object] = None
    staple_length: Optional[object] = None
    scouring_yield: Optional[object] = None


# Matching and transform helpers.


def _check_range(
    value: Optional[int], lo: Optional[int], hi: Optional[int]
) -> bool:
    """Return True if the value fits inside the optional bounds."""
    if value is None:
        return True  # Missing values are treated as compatible.
    if lo is not None and value < lo:
        return False
    if hi is not None and value > hi:
        return False
    return True


def is_quality_compatible(
    state: QualityState, req: QualityRequirement
) -> bool:
    """Return True when the quality state satisfies the requirement."""
    if not _check_range(state.fineness, req.fineness_min, req.fineness_max):
        return False
    if req.color_accepted and state.color is not None:
        if state.color not in req.color_accepted:
            return False
    if not _check_range(
        state.staple_length, req.staple_length_min, req.staple_length_max
    ):
        return False
    if not _check_range(
        state.scouring_yield, req.scouring_yield_min, req.scouring_yield_max
    ):
        return False
    return True


def apply_transform(
    state: QualityState, transform: QualityTransform
) -> QualityState:
    """Return a new quality state with the transform applied."""
    new = QualityState(
        fineness=state.fineness,
        color=state.color,
        staple_length=state.staple_length,
        scouring_yield=state.scouring_yield,
    )
    for prop in ("fineness", "color", "staple_length", "scouring_yield"):
        t_val = getattr(transform, prop)
        if t_val is None:
            continue
        if t_val == "remove":
            setattr(new, prop, None)
        else:
            setattr(new, prop, int(t_val))
    return new
