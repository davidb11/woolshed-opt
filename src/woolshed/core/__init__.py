"""Core domain objects for WoolShed.

This package holds the entity models, quality rules and geographic helpers.
It has no I/O or web framework dependencies.
"""

from .geo import haversine_km
from .models import Parameters, Product, Source, Process
from .quality import (
    COLOR_CLASSES,
    FINENESS_CLASSES,
    SCOURING_YIELD_CLASSES,
    STAPLE_LENGTH_CLASSES,
    QualityRequirement,
    QualityState,
    QualityTransform,
    apply_transform,
    is_quality_compatible,
)

__all__ = [
    # Models
    "Source",
    "Process",
    "Product",
    "Parameters",
    # Quality
    "QualityState",
    "QualityRequirement",
    "QualityTransform",
    "is_quality_compatible",
    "apply_transform",
    "FINENESS_CLASSES",
    "COLOR_CLASSES",
    "STAPLE_LENGTH_CLASSES",
    "SCOURING_YIELD_CLASSES",
    # Geography
    "haversine_km",
]
