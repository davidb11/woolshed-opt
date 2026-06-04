"""Entity models for wool sources, processes and products."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from .quality import QualityRequirement, QualityState, QualityTransform


# Entity models.


@dataclass
class Source:
    """A batch of raw wool available at a geographic location."""

    id: str
    name: str
    lat: float
    lon: float
    quantity_kg: float
    cost_per_kg: float = 0.0  # Procurement cost per kg.
    impact_per_kg: float = 0.0  # Environmental impact score per kg.
    quality: QualityState = field(default_factory=QualityState)


@dataclass
class Process:
    """A processing step that transforms wool."""

    id: str
    name: str
    lat: float
    lon: float
    stage: int  # Position in the process chain.
    chain: str = "main"  # Processing-chain name.
    conversion_pct: float = 100.0  # Output mass as a percentage of input mass.
    max_capacity_kg: float = 1e9  # Maximum input capacity.
    cost_per_kg: float = 0.0  # Processing cost per input kg.
    impact_per_kg: float = 0.0  # Environmental impact per input kg.
    # When set, this process only accepts input from these process IDs.
    fixed_predecessor_ids: Optional[List[str]] = None

    input_requirements: QualityRequirement = field(
        default_factory=QualityRequirement
    )
    output_transform: QualityTransform = field(
        default_factory=QualityTransform
    )


@dataclass
class Product:
    """A final wool-derived product with demand and price."""

    id: str
    name: str
    lat: float
    lon: float
    demand_min_kg: float = 0.0
    demand_max_kg: float = 1e9
    price_per_kg: float = 0.0
    quality_requirements: QualityRequirement = field(
        default_factory=QualityRequirement
    )
    required_chain: Optional[str] = None  # If set, only accept this chain.
    required_min_stage: Optional[int] = None  # If set, require at least this stage.


@dataclass
class Parameters:
    """Global optimisation parameters."""

    transport_cost_per_kg_km: float = 0.001  # Cost per kg per km.
    transport_impact_per_kg_km: float = 0.0005  # Impact per kg per km.
