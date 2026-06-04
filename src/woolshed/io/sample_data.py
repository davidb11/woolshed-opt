"""Generate a sample WoolShed input workbook.

You can also run it directly::

    python -m woolshed.io.sample_data [output.xlsx]
"""

from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from woolshed.core.quality import (
    COLOR_CLASSES,
    FINENESS_CLASSES,
    SCOURING_YIELD_CLASSES,
    STAPLE_LENGTH_CLASSES,
)


# Formatting helpers.


def _header_style(ws, row: int = 1):
    """Style the header row."""
    fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
    font = Font(bold=True)
    for cell in ws[row]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(wrap_text=True)


def _auto_width(ws):
    for col_cells in ws.columns:
        max_len = max((len(str(c.value)) if c.value else 0) for c in col_cells)
        ws.column_dimensions[get_column_letter(col_cells[0].column)].width = min(
            max_len + 3, 30
        )


# Workbook generator.


def generate(output_path: str | Path = "woolshed_sample_input.xlsx"):
    """Write a complete sample workbook to the output path."""
    wb = openpyxl.Workbook()

    # Sources.
    ws = wb.active
    ws.title = "Sources"
    headers = [
        "id", "name", "lat", "lon", "quantity_kg",
        "cost_per_kg", "impact_per_kg",
        "fineness", "color", "staple_length", "scouring_yield",
    ]
    ws.append(headers)
    data = [
        # id, name, lat, lon, quantity, cost, impact, fineness, colour, staple, scour
        ("SRC_ALP_01", "Bergschaf – Innsbruck",   47.260, 11.390, 500,  2.5, 1.8, 5, 4, 3, 3),
        ("SRC_ALP_02", "Merino – Meran",           46.670, 11.160, 200, 12.0, 2.5, 2, 1, 4, 4),
        ("SRC_ALP_03", "Jezersko-Solčavska",       46.420, 14.690, 300,  3.0, 1.5, 3, 2, 3, 3),
        ("SRC_ALP_04", "Brogna – Lessinia",        45.630, 11.050, 400,  3.5, 1.6, 4, 5, 2, 2),
        ("SRC_ALP_05", "Alpagota – Belluno",        46.140, 12.220, 250,  4.0, 1.7, 3, 3, 3, 3),
        ("SRC_ALP_06", "Foza – Altopiano",          45.890, 11.650, 350,  2.8, 1.4, 4, 2, 2, 2),
    ]
    for r in data:
        ws.append(r)
    _header_style(ws)
    _auto_width(ws)

    # Processes.
    ws2 = wb.create_sheet("Processes")
    headers = [
        "id", "name", "lat", "lon",
        "stage", "chain", "conversion_pct", "max_capacity_kg",
        "cost_per_kg", "impact_per_kg", "fixed_predecessor",
        # Input requirements.
        "in_fineness_min", "in_fineness_max", "in_color",
        "in_staple_min", "in_staple_max",
        "in_scouring_min", "in_scouring_max",
        # Output transforms.
        "out_fineness", "out_color", "out_staple", "out_scouring",
    ]
    ws2.append(headers)

    procs = [
        # Stage 1: sorting and grading. The "main" chain can connect to any chain.
        ("T_SORT_01", "Sorting – Biella",         45.560, 8.050,  1, "main",     95, 2000, 0.30, 0.10, "",
         "", "", "", "", "", 1, 5, "", "", "", ""),
        ("T_SORT_02", "Sorting – Ljubljana",      46.056, 14.506, 1, "main",     95, 1500, 0.35, 0.12, "",
         "", "", "", "", "", 1, 5, "", "", "", ""),
        ("T_SORT_03", "Sorting – Bergauf",        46.700, 11.460, 1, "main",     95, 1000, 0.30, 0.10, "",
         "", "", "", "", "", 1, 5, "", "", "", ""),

        # Stage 2: scouring and washing.
        ("T_SCOUR_01", "Scouring – Biella",       45.560, 8.050,  2, "yarn",     65, 1800, 1.20, 0.80, "",
         "", "", "", "", "", 2, 5, "", "", "", "remove"),
        ("T_SCOUR_02", "Scouring – Ljubljana",    46.056, 14.506, 2, "felt",     60, 1200, 1.30, 0.85, "",
         "", "", "", "", "", 2, 5, "", "", "", "remove"),
        ("T_SCOUR_03", "Scouring – Bergauf",      46.700, 11.460, 2, "insulation", 70, 800, 1.10, 0.70, "",
         "", "", "", "", "", 1, 5, "", "", "", "remove"),

        # Stage 3: carding and combing.
        ("T_CARD_01", "Carding – Biella",         45.560, 8.050,  3, "yarn",     90, 1500, 0.80, 0.30, "",
         1, 3, "", 2, 5, "", "", "", "", "", ""),
        ("T_CARD_02", "Carding – Bergauf",        46.700, 11.460, 3, "felt",     88, 800,  0.70, 0.25, "",
         "", "", "", "", "", "", "", "", "", "", ""),
        ("T_CARD_03", "Carding – Bergauf Ins.",    46.700, 11.460, 3, "insulation", 85, 600, 0.65, 0.20, "",
         3, 5, "", "", "", "", "", "", "", "", ""),

        # Stage 4: spinning, felting and needling.
        ("T_SPIN_01", "Spinning – Paoletti",       45.950, 12.660, 4, "yarn",     85, 1000, 1.50, 0.40, "T_CARD_01,T_CARD_02",
         1, 3, "", 3, 5, "", "", "", "", "", ""),
        ("T_FELT_01", "Needle felting – Bergauf",  46.700, 11.460, 4, "felt",     92, 600,  1.00, 0.35, "",
         "", "", "", "", "", "", "", "", "", "", ""),
        ("T_NEED_01", "Needling – Bergauf Ins.",    46.700, 11.460, 4, "insulation", 90, 500, 0.90, 0.30, "",
         3, 5, "", "", "", "", "", "", "", "", ""),

        # Stage 5: final shaping.
        ("T_WEAV_01", "Weaving – Paoletti",        45.950, 12.660, 5, "yarn",     95, 800,  2.00, 0.50, "",
         1, 3, "", "", "", "", "", "", "", "", ""),
        ("T_KNIT_01", "Knitting – Le Textile Lab", 45.190, 5.720,  5, "yarn",     93, 400,  2.50, 0.60, "",
         1, 3, "", "", "", "", "", "", "", "", ""),
        ("T_PRESS_01", "Panel pressing – Bergauf", 46.700, 11.460, 5, "insulation", 97, 400, 1.80, 0.45, "",
         3, 5, "", "", "", "", "", "", "", "", ""),

        # Fertiliser chain.
        # Stage 2: drying and composting.
        ("T_DRY_01", "Drying – Nova Gorica",       45.956, 13.640, 2, "fertiliser", 85, 1000, 0.40, 0.10, "",
         "", "", "", "", "", "", "", "", "", "", ""),
        # Stage 3: pelletising.
        ("T_PELLET_01", "Pelletising – Nova Gorica", 45.956, 13.640, 3, "fertiliser", 80, 1000, 0.50, 0.15, "",
         "", "", "", "", "", "", "", "", "", "", ""),
    ]
    for t in procs:
        ws2.append(t)
    _header_style(ws2)
    _auto_width(ws2)

    # Products.
    ws3 = wb.create_sheet("Products")
    headers = [
        "id", "name", "lat", "lon",
        "demand_min_kg", "demand_max_kg", "price_per_kg",
        "required_chain", "required_min_stage",
        "req_fineness_min", "req_fineness_max", "req_color",
        "req_staple_min", "req_staple_max",
    ]
    ws3.append(headers)

    products = [
        # Yarn needs the yarn chain and at least stage 4.
        ("P_YARN_01",  "Fine Yarn – Fashion",       45.440, 12.320, 80,  300,  40.0, "yarn", 4, 1, 3, "1,2,3", 3, 5),
        # Woven fabric needs the yarn chain at stage 5.
        ("P_WEAVE_01", "Woven Fabric – Apparel",    45.440, 12.320, 50,  200,  35.0, "yarn", 5, 1, 3, "1,2,3", 3, 5),
        # Felt needs the felt chain at stage 4.
        ("P_FELT_01",  "Wool Felt – Crafts",         46.056, 14.506, 60,  250, 18.0, "felt", 4, "", "", "", "", ""),
        # Insulation needs the insulation chain from stage 4 onward.
        ("P_INS_01",   "Insulation Panel – Construction", 46.700, 11.460, 100, 500, 15.0, "insulation", 4, 3, 5, "", "", ""),
        # Fertiliser needs the fertiliser chain at stage 3.
        ("P_FERT_01",  "Fertiliser Pellets",          45.956, 13.640, 50,  400,  5.0, "fertiliser", 3, "", "", "", "", ""),
    ]
    for p in products:
        ws3.append(p)
    _header_style(ws3)
    _auto_width(ws3)

    # Parameters.
    ws4 = wb.create_sheet("Parameters")
    ws4.append(["parameter", "value"])
    ws4.append(["transport_cost_per_kg_km", 0.001])
    ws4.append(["transport_impact_per_kg_km", 0.0005])
    _header_style(ws4)
    _auto_width(ws4)

    # Quality reference sheet.
    ws5 = wb.create_sheet("QualityRef")
    ws5.append(["Property", "Class", "Label"])
    for cls_val, label in FINENESS_CLASSES.items():
        ws5.append(["Fineness", cls_val, label])
    ws5.append([])
    for cls_val, label in COLOR_CLASSES.items():
        ws5.append(["Colour", cls_val, label])
    ws5.append([])
    for cls_val, label in STAPLE_LENGTH_CLASSES.items():
        ws5.append(["Staple Length", cls_val, label])
    ws5.append([])
    for cls_val, label in SCOURING_YIELD_CLASSES.items():
        ws5.append(["Scouring Yield", cls_val, label])
    _header_style(ws5)
    _auto_width(ws5)

    wb.save(str(output_path))
    print(f"Sample input written to {output_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "woolshed_sample_input.xlsx"
    generate(out)
