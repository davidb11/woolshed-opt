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
