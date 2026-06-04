"""Read a WoolShed input workbook.

Expected sheets:
Sources, Processes, Products, Parameters and QualityRef.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import openpyxl

from woolshed.core.models import Parameters, Product, Source, Process
from woolshed.core.quality import QualityRequirement, QualityState, QualityTransform


# Small parsing helpers.


def _safe_float(val, default: float = 0.0) -> float:
    if val is None or str(val).strip() == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default: Optional[int] = None) -> Optional[int]:
    if val is None or str(val).strip() == "":
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _parse_int_list(val) -> Optional[List[int]]:
    """Parse a comma-separated list of integers."""
    if val is None or str(val).strip() == "":
        return None
    try:
        return [int(x.strip()) for x in str(val).split(",") if x.strip()]
    except ValueError:
        return None


def _parse_transform_value(val):
    """Parse a transform value as pass-through, remove, or an integer."""
    if val is None or str(val).strip() == "":
        return None
    s = str(val).strip().lower()
    if s == "remove":
        return "remove"
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _parse_str_list(val) -> Optional[List[str]]:
    """Parse a comma-separated list of strings."""
    if val is None or str(val).strip() == "":
        return None
    try:
        return [x.strip() for x in str(val).split(",") if x.strip()]
    except Exception:
        return None


# Public reader.


def read_input_excel(
    path: str | Path,
) -> Tuple[List[Source], List[Process], List[Product], Parameters]:
    """Return sources, processes, products and parameters from a workbook."""
    wb = openpyxl.load_workbook(str(path), data_only=True)

    # Parameters.
    params = Parameters()
    if "Parameters" in wb.sheetnames:
        ws = wb["Parameters"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            key = str(row[0]).strip().lower() if row[0] else ""
            val = _safe_float(row[1] if len(row) > 1 else None, 0.0)
            if "transport_cost" in key:
                params.transport_cost_per_kg_km = val
            elif "transport_impact" in key:
                params.transport_impact_per_kg_km = val

    # Sources.
    sources: List[Source] = []
    if "Sources" in wb.sheetnames:
        ws = wb["Sources"]
        headers = [
            str(c.value).strip().lower() if c.value else ""
            for c in next(ws.iter_rows(min_row=1, max_row=1))
        ]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            d = dict(zip(headers, row))
            sources.append(
                Source(
                    id=str(d.get("id", "")),
                    name=str(d.get("name", d.get("id", ""))),
                    lat=_safe_float(d.get("lat"), 0.0),
                    lon=_safe_float(d.get("lon"), 0.0),
                    quantity_kg=_safe_float(d.get("quantity_kg"), 0.0),
                    cost_per_kg=_safe_float(d.get("cost_per_kg"), 0.0),
                    impact_per_kg=_safe_float(d.get("impact_per_kg"), 0.0),
                    quality=QualityState(
                        fineness=_safe_int(d.get("fineness")),
                        color=_safe_int(d.get("color")),
                        staple_length=_safe_int(d.get("staple_length")),
                        scouring_yield=_safe_int(d.get("scouring_yield")),
                    ),
                )
            )

    # Processes.
    processes: List[Process] = []
    if "Processes" in wb.sheetnames:
        ws = wb["Processes"]
        headers = [
            str(c.value).strip().lower() if c.value else ""
            for c in next(ws.iter_rows(min_row=1, max_row=1))
        ]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            d = dict(zip(headers, row))
            # The fixed predecessor cell may contain one ID, many IDs, or be empty.
            fp = _parse_str_list(d.get("fixed_predecessor"))
            processes.append(
                Process(
                    id=str(d.get("id", "")),
                    name=str(d.get("name", d.get("id", ""))),
                    lat=_safe_float(d.get("lat"), 0.0),
                    lon=_safe_float(d.get("lon"), 0.0),
                    stage=_safe_int(d.get("stage"), 1),
                    chain=str(d.get("chain", "main")).strip() or "main",
                    conversion_pct=_safe_float(d.get("conversion_pct"), 100.0),
                    max_capacity_kg=_safe_float(d.get("max_capacity_kg"), 1e9),
                    cost_per_kg=_safe_float(d.get("cost_per_kg"), 0.0),
                    impact_per_kg=_safe_float(d.get("impact_per_kg"), 0.0),
                    fixed_predecessor_ids=fp,
                    input_requirements=QualityRequirement(
                        fineness_min=_safe_int(d.get("in_fineness_min")),
                        fineness_max=_safe_int(d.get("in_fineness_max")),
                        color_accepted=_parse_int_list(d.get("in_color")),
                        staple_length_min=_safe_int(d.get("in_staple_min")),
                        staple_length_max=_safe_int(d.get("in_staple_max")),
                        scouring_yield_min=_safe_int(d.get("in_scouring_min")),
                        scouring_yield_max=_safe_int(d.get("in_scouring_max")),
                    ),
                    output_transform=QualityTransform(
                        fineness=_parse_transform_value(d.get("out_fineness")),
                        color=_parse_transform_value(d.get("out_color")),
                        staple_length=_parse_transform_value(d.get("out_staple")),
                        scouring_yield=_parse_transform_value(
                            d.get("out_scouring")
                        ),
                    ),
                )
            )

    # Products.
    products: List[Product] = []
    if "Products" in wb.sheetnames:
        ws = wb["Products"]
        headers = [
            str(c.value).strip().lower() if c.value else ""
            for c in next(ws.iter_rows(min_row=1, max_row=1))
        ]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            d = dict(zip(headers, row))
            rc = d.get("required_chain")
            if rc is not None and str(rc).strip() == "":
                rc = None
            elif rc is not None:
                rc = str(rc).strip()
            products.append(
                Product(
                    id=str(d.get("id", "")),
                    name=str(d.get("name", d.get("id", ""))),
                    lat=_safe_float(d.get("lat"), 0.0),
                    lon=_safe_float(d.get("lon"), 0.0),
                    demand_min_kg=_safe_float(d.get("demand_min_kg"), 0.0),
                    demand_max_kg=_safe_float(d.get("demand_max_kg"), 1e9),
                    price_per_kg=_safe_float(d.get("price_per_kg"), 0.0),
                    quality_requirements=QualityRequirement(
                        fineness_min=_safe_int(d.get("req_fineness_min")),
                        fineness_max=_safe_int(d.get("req_fineness_max")),
                        color_accepted=_parse_int_list(d.get("req_color")),
                        staple_length_min=_safe_int(d.get("req_staple_min")),
                        staple_length_max=_safe_int(d.get("req_staple_max")),
                    ),
                    required_chain=rc,
                    required_min_stage=_safe_int(d.get("required_min_stage")),
                )
            )

    wb.close()
    return sources, processes, products, params
