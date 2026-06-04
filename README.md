# WoolShed – Wool Value-Chain Optimisation Tool

A web-based tool that optimises how wool flows from raw sources through processing stages to final products. Optimisation done with a  **MILP** model (solved via PuLP/GLPK) and shows the results on an interactive map.

---

## Install

```bash
pip install -e .
```

**GLPK** is the recommended solver. Without it the tool falls back to PuLP's built-in CBC solver.

- Windows: download from https://sourceforge.net/projects/winglpk/ and add to `PATH`
- Linux: `sudo apt install glpk-utils`
- macOS: `brew install glpk`

---

## Run

```bash
python -m woolshed --browser
```

Opens the app in your browser at `http://localhost:5000`.

---

## Usage

1. **Load data** – click *Load Sample Data* to try the built-in Alpine example, *Upload Excel* to use your own file, or *Download Template* to get a starting workbook.
2. **Pick an objective** – Maximise Profit, Minimise Cost, or Minimise Environmental Impact.
3. **Click Optimise** – optimised flows appear as lines on the map and a summary shows in the *Results* tab.

---

## Excel Input Format

The workbook needs four sheets: **Sources**, **Processes**, **Products**, and **Parameters**.

### Sources
| Column | Type | Description |
|--------|------|-------------|
| `id`, `name` | string | Identifier and display name |
| `lat`, `lon` | float | Location (WGS 84) |
| `quantity_kg` | float | Available quantity |
| `cost_per_kg` | float | Procurement cost (€/kg) |
| `impact_per_kg` | float | Environmental impact score per kg |
| `fineness` | int 1–5 | Fibre fineness class |
| `color` | int 1–6 | Colour class |
| `staple_length` | int 1–5 | Staple length class |
| `scouring_yield` | int 1–5 | Scouring yield class |

### Processes
| Column | Type | Description |
|--------|------|-------------|
| `id`, `name` | string | Identifier and display name |
| `lat`, `lon` | float | Location |
| `stage` | int | Processing stage (1, 2, 3 …) |
| `chain` | string | Chain label (`yarn`, `felt`, `insulation`, `main`) |
| `conversion_pct` | float | Output mass as % of input |
| `max_capacity_kg` | float | Max input capacity (kg) |
| `cost_per_kg` | float | Processing cost (€/input kg) |
| `impact_per_kg` | float | Environmental impact per input kg |
| `fixed_predecessor` | string | Accept input only from this process ID (comma-separated list allowed) |
| `in_fineness_min/max` | int | Accepted fineness range |
| `in_color` | string | Comma-separated accepted colour classes |
| `in_staple_min/max` | int | Accepted staple length range |
| `in_scouring_min/max` | int | Accepted scouring yield range |
| `out_fineness/color/staple/scouring` | int/empty | Output quality (empty = passthrough; `remove` clears scouring after washing) |

### Products
| Column | Type | Description |
|--------|------|-------------|
| `id`, `name` | string | Identifier and display name |
| `lat`, `lon` | float | Delivery location |
| `demand_min_kg`, `demand_max_kg` | float | Demand range (kg) |
| `price_per_kg` | float | Selling price (€/kg) |
| `required_chain` | string | Must come from this chain |
| `required_min_stage` | int | Must pass through at least this stage |
| `req_fineness_min/max` | int | Required fineness range |
| `req_color` | string | Comma-separated accepted colours |
| `req_staple_min/max` | int | Required staple length range |

### Parameters
| parameter | value |
|-----------|-------|
| `transport_cost_per_kg_km` | 0.001 |
| `transport_impact_per_kg_km` | 0.0005 |

---


## Wool Quality Classes

### Fineness (fibre diameter)
| Class | Label |
|-------|-------|
| 1 | Ultrafine (< 17 µm) |
| 2 | Fine (17–20 µm) |
| 3 | Medium (20–25 µm) |
| 4 | Strong (25–30 µm) |
| 5 | Coarse (> 30 µm) |

### Colour
| Class | Label |
|-------|-------|
| 1 | White |
| 2 | Cream |
| 3 | Pale |
| 4 | Grey |
| 5 | Brown |
| 6 | Black |

### Staple Length
| Class | Label |
|-------|-------|
| 1 | Very Short (< 4 cm) |
| 2 | Short (4–7 cm) |
| 3 | Medium (7–10 cm) |
| 4 | Long (10–15 cm) |
| 5 | Very Long (> 15 cm) |

### Scouring Yield
| Class | Label |
|-------|-------|
| 1 | Very Low (< 40 %) |
| 2 | Low (40–50 %) |
| 3 | Medium (50–65 %) |
| 4 | High (65–80 %) |
| 5 | Very High (> 80 %) |

---

## Supply Chain Structure

The optimiser models the wool value chain as a staged directed network.

Processes with `chain="main"` can feed into **any** downstream chain.  Otherwise, arcs only connect processes that share the same chain label.

Products specify a `required_chain` and `required_min_stage` to ensure material has been properly processed before delivery.

Flow is only created along **quality-compatible** arcs.  Each process can specify **input requirements** (which quality classes it accepts) and an **output transform** (how it changes quality).

A `fixed_predecessor` field allows hard-wiring a process to accept input only from specific upstream step(s). The cell may contain a single process ID or a comma-separated list of IDs; when present the process will accept input only from the listed predecessor(s), overriding the usual chain/quality checks.

---

## License

Open-source, released as part of the WOOLSHED Alpine Space project (Interreg).
