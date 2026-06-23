"""Flask routes for the WoolShed web app.

The app serves the map page, handles Excel upload and sample generation, and
runs the optimisation API.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Dict

from flask import Flask, jsonify, render_template, request, send_file

from woolshed.core.models import Parameters
from woolshed.io.excel_reader import read_input_excel
from woolshed.io.sample_data import generate as generate_sample
from woolshed.optimizer.solver import optimize
from woolshed.core.quality import (
    COLOR_CLASSES,
    FINENESS_CLASSES,
    SCOURING_YIELD_CLASSES,
    STAPLE_LENGTH_CLASSES,
)

logger = logging.getLogger(__name__)

# Simple in-memory app state.

_state: Dict = {
    "sources": [],
    "processes": [],
    "products": [],
    "params": Parameters(),
    "result": None,
}


def _entity_to_dict(e) -> dict:
    """Convert a dataclass entity to a JSON-friendly dict."""
    d: dict = {}
    for k, v in e.__dict__.items():
        if hasattr(v, "__dict__"):
            d[k] = {kk: vv for kk, vv in v.__dict__.items()}
        else:
            d[k] = v
    return d


# Flask app factory.


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit.

    # Pages.

    @app.route("/")
    def index():
        return render_template("index.html")

    # Data API.

    @app.route("/api/data")
    def api_data():
        """Return the currently loaded data."""
        return jsonify(
            sources=[_entity_to_dict(s) for s in _state["sources"]],
            processes=[_entity_to_dict(t) for t in _state["processes"]],
            products=[_entity_to_dict(p) for p in _state["products"]],
            params=_entity_to_dict(_state["params"]),
        )

    @app.route("/api/quality-classes")
    def api_quality_classes():
        return jsonify(
            fineness=FINENESS_CLASSES,
            color=COLOR_CLASSES,
            staple_length=STAPLE_LENGTH_CLASSES,
            scouring_yield=SCOURING_YIELD_CLASSES,
        )

    # Excel upload API.

    @app.route("/api/upload", methods=["POST"])
    def api_upload():
        if "file" not in request.files:
            return jsonify(error="No file uploaded"), 400
        f = request.files["file"]
        if not f.filename:
            return jsonify(error="Empty filename"), 400

        suffix = Path(f.filename).suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        f.save(tmp.name)
        tmp.close()

        # Very small files are unlikely to be valid workbooks.
        try:
            if os.path.getsize(tmp.name) < 512:
                return (
                    jsonify(error="Uploaded file is too small to be a valid Excel workbook."),
                    400,
                )
        except OSError:
            pass

        try:
            sources, procs, products, params = read_input_excel(tmp.name)
            # Make sure the workbook actually contained usable data.
            if not (sources or procs or products):
                return (
                    jsonify(
                        error=(
                            "Uploaded workbook contained no data or was not in the expected "
                            "template format. Please check the sheet names and columns."
                        )
                    ),
                    400,
                )

            _state["sources"] = sources
            _state["processes"] = procs
            _state["products"] = products
            _state["params"] = params
            _state["result"] = None
            return jsonify(
                ok=True,
                counts=dict(
                    sources=len(sources),
                    processes=len(procs),
                    products=len(products),
                ),
            )
        except Exception as exc:
            logger.exception("Failed to parse Excel")
            return jsonify(error=str(exc)), 400
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    # Sample data API.

    @app.route("/api/generate-sample", methods=["POST"])
    def api_generate_sample():
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        tmp.close()
        generate_sample(tmp.name)
        sources, procs, products, params = read_input_excel(tmp.name)
        _state["sources"] = sources
        _state["processes"] = procs
        _state["products"] = products
        _state["params"] = params
        _state["result"] = None
        os.unlink(tmp.name)
        return jsonify(
            ok=True,
            counts=dict(
                sources=len(sources),
                processes=len(procs),
                products=len(products),
            ),
        )

    @app.route("/api/download-sample")
    def api_download_sample():
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        tmp.close()
        generate_sample(tmp.name)
        return send_file(
            tmp.name, as_attachment=True, download_name="woolshed_sample_input.xlsx"
        )

    # Entity patch API.

    @app.route("/api/entity", methods=["PATCH"])
    def api_patch_entity():
        body = request.get_json(silent=True) or {}
        entity_type = body.get("type")
        entity_id   = body.get("id")
        field       = body.get("field")
        value       = body.get("value")

        if not all([entity_type, entity_id, field]) or value is None:
            return jsonify(error="Missing type, id, field, or value"), 400

        lists = {
            "source":  _state["sources"],
            "process": _state["processes"],
            "product": _state["products"],
        }
        if entity_type not in lists:
            return jsonify(error=f"Unknown entity type: {entity_type}"), 400

        entity = next((e for e in lists[entity_type] if e.id == entity_id), None)
        if entity is None:
            return jsonify(error=f"{entity_type} '{entity_id}' not found"), 404

        numeric_fields = {
            "lat", "lon", "quantity_kg", "cost_per_kg", "impact_per_kg",
            "conversion_pct", "max_capacity_kg",
            "demand_min_kg", "demand_max_kg", "price_per_kg",
        }
        string_fields = {"name"}
        quality_fields = {"quality.fineness", "quality.color", "quality.staple_length", "quality.scouring_yield"}
        quality_ranges = {
            "fineness": (1, 5), "color": (1, 6), "staple_length": (1, 5), "scouring_yield": (1, 5),
        }

        if field in quality_fields:
            if not hasattr(entity, "quality") or entity.quality is None:
                return (
                    jsonify(error=f"Field '{field}' is not editable for entity type '{entity_type}'"),
                    400,
                )
            sub = field.split(".")[1]
            lo, hi = quality_ranges[sub]
            if value == "" or value is None:
                setattr(entity.quality, sub, None)
            else:
                try:
                    iv = int(value)
                except (TypeError, ValueError):
                    return jsonify(error=f"Expected an integer class for '{sub}'"), 400
                if not (lo <= iv <= hi):
                    return jsonify(error=f"'{sub}' must be between {lo} and {hi}"), 400
                setattr(entity.quality, sub, iv)
        elif field in numeric_fields:
            try:
                value = float(value)
            except (TypeError, ValueError):
                return jsonify(error=f"Expected a number for '{field}'"), 400
            import math
            if not math.isfinite(value):
                return jsonify(error=f"Expected a finite number for '{field}'"), 400
            if field == "lat" and not (-90.0 <= value <= 90.0):
                return jsonify(error="Latitude must be between -90 and 90"), 400
            if field == "lon" and not (-180.0 <= value <= 180.0):
                return jsonify(error="Longitude must be between -180 and 180"), 400
            setattr(entity, field, value)
        elif field in string_fields:
            value = str(value).strip()
            if not value:
                return jsonify(error="Name cannot be empty"), 400
            setattr(entity, field, value)
        else:
            return jsonify(error=f"Field '{field}' is not editable"), 400

        return jsonify(ok=True)

    # Optimisation API.

    @app.route("/api/optimize", methods=["POST"])
    def api_optimize():
        body = request.get_json(silent=True) or {}
        objective = body.get("objective", "max_profit")
        if objective not in ("max_profit", "min_cost", "min_impact"):
            return jsonify(error=f"Unknown objective: {objective}"), 400

        if not _state["sources"] or not _state["processes"]:
            return jsonify(error="No data loaded. Upload an Excel file first."), 400

        try:
            result = optimize(
                _state["sources"],
                _state["processes"],
                _state["products"],
                _state["params"],
                objective=objective,
            )
            _state["result"] = result
            flows = []
            for (a, b), val in result.arc_flows.items():
                flows.append(dict(from_id=a, to_id=b, mass_kg=round(val, 2)))
            return jsonify(
                status=result.status,
                objective_value=round(result.objective_value, 2),
                flows=flows,
                summary=result.summary_lines,
            )
        except Exception as exc:
            logger.exception("Optimisation failed")
            return jsonify(error=str(exc)), 500

    return app
