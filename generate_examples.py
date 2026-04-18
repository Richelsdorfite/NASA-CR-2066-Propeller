#!/usr/bin/env python
"""
generate_examples.py
--------------------
Creates the four H432 example sets in the examples/ sub-directory.

For each case the script produces:
  caseN_<name>.h432   -- session file (loadable via HMI "Load" button)
  caseN_<name>.txt    -- plain-text results report with variable definitions
  caseN_<name>.csv    -- CSV results with variable definitions as header comments
  caseN_<name>.json   -- JSON results with a "variable_definitions" section
"""

import dataclasses
import json
import textwrap
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from operating_condition import OperatingCondition, PropellerGeometry
from output import ResultsCollector, ReportWriter
from MAIN import call_input, main_loop
import MAIN as main_module

OUT_DIR = Path(__file__).parent / "examples"
OUT_DIR.mkdir(exist_ok=True)


# ======================================================================
# Variable definitions — two flavours
# ======================================================================

# --- Performance output (IW = 1 and IW = 2) ---------------------------
DEFS_PERF = {
    "condition":  "Operating condition index (1-based). "
                  "Each row in the table belongs to one operating condition.",
    "blades":     "Number of propeller blades.",
    "af":         "Activity factor (AF) — dimensionless measure of blade chord "
                  "distribution along the radius. Typical range: 80–200.",
    "cli":        "Integrated design lift coefficient (CLi). "
                  "Typical range: 0.3–0.8.",
    "dia_ft":     "Propeller diameter (ft).",
    "tipspd_fps": "Blade tip speed (ft/s).",
    "cp":         "Power coefficient: CP = SHP x 550 / (rho x n^3 x D^5), "
                  "where n is rotational speed in rev/s and rho is air density.",
    "ct":         "Thrust coefficient: CT = Thrust / (rho x n^2 x D^4).",
    "blade_ang":  "Blade angle at the 3/4-radius station (degrees).",
    "j":          "Advance ratio: J = V / (n x D), "
                  "where V is true airspeed in ft/s.",
    "mach_tip":   "Blade tip Mach number (tip speed / speed of sound).",
    "mach_fs":    "Freestream Mach number (true airspeed / speed of sound).",
    "ft":         "Compressibility correction factor applied to CT and CP "
                  "(1.0 = no correction needed).",
    "thrust_lb":  "Net propulsive thrust (lbf). "
                  "IW=1: computed from BHP. IW=2: equals the specified target.",
    "shp":        "Shaft horsepower (hp). "
                  "IW=1: equals the specified input. IW=2: computed by solver.",
    "pnl_db":     "Perceived Noise Level at the specified sideline distance (dB). "
                  "0.0 when noise computation is not requested (DIST = 0).",
    "qty70":      "Production quantity used for the 1970-technology cost estimate.",
    "wt70_lb":    "Propeller assembly weight — 1970 technology level (lb).",
    "cost70_qty": "Unit manufacturing cost at the 1970 technology level ($). "
                  "Decreases with production quantity (learning-curve effect).",
    "qty80":      "Production quantity used for the 1980-technology cost estimate.",
    "wt80_lb":    "Propeller assembly weight — 1980 technology level (lb). "
                  "Typically lower than wt70_lb due to advanced materials.",
    "cost80_qty": "Unit manufacturing cost at the 1980 technology level ($).",
    "off_chart":  "True when the operating point lies outside the aerodynamic "
                  "chart limits of the Hamilton Standard method. "
                  "Results marked True should be used with caution.",
}

# --- Reverse-thrust output (IW = 3) -----------------------------------
DEFS_REV = {
    "condition":  "Operating condition index (1-based).",
    "blades":     "Number of propeller blades.",
    "af":         "Activity factor (AF). Typical range: 80–200.",
    "cli":        "Integrated design lift coefficient (CLi). "
                  "Typical range: 0.3–0.8.",
    "dia_ft":     "Propeller diameter (ft).",
    "pcpw":       "Power setting as a percentage of the full-throttle SHP (%). "
                  "100 % = full power; reduced settings model partial braking.",
    "theta_deg":  "Blade angle at the 3/4-radius station (degrees). "
                  "Negative values indicate reverse pitch.",
    "vk_kts":     "Aircraft ground speed at the instant of computation (knots). "
                  "The table is computed from 0 kts up to the touch-down speed.",
    "thrust_lb":  "Reverse (braking) thrust produced by the propeller (lbf). "
                  "Acts opposite to the direction of motion.",
    "shp":        "Shaft horsepower absorbed by the propeller at this speed "
                  "and power setting (hp).",
    "rpm":        "Propeller rotational speed (RPM). "
                  "May be lower than full-throttle RPM for reciprocating engines "
                  "because torque limits the available power at reverse pitch.",
}


# ======================================================================
# Variable definitions — session file (.h432) fields
# ======================================================================

DEFS_GEOMETRY = {
    # --- Diameter sweep ---
    "D":     "Starting propeller diameter (ft). "
             "The solver sweeps ND diameters beginning at D.",
    "DD":    "Diameter increment (ft). Added to D for each successive step. "
             "Set to 0 when ND=1.",
    "ND":    "Number of diameter steps (1-10). "
             "Diameters computed: D, D+DD, D+2*DD, ...",
    # --- Activity-factor sweep ---
    "AF":    "Starting activity factor. Dimensionless measure of the blade "
             "chord distribution along the radius. Typical range: 80-200.",
    "DAF":   "Activity-factor increment. Set to 0 when NAF=1.",
    "NAF":   "Number of activity-factor steps (1-10).",
    # --- Blade-count sweep ---
    "BLADN": "Starting number of blades (2-8).",
    "DBLAD": "Blade-count increment. Set to 0 when NBL=1.",
    "NBL":   "Number of blade-count steps (1-10).",
    # --- Integrated design CLi sweep ---
    "CLII":  "Starting integrated design lift coefficient (CLi). "
             "Typical range: 0.3-0.8.",
    "DCLI":  "CLi increment. Set to 0 when ZNCLI=1.",
    "ZNCLI": "Number of CLi steps (1-10).",
    # --- Design Mach ---
    "ZMWT":  "Design flight Mach number. Used for weight and cost estimation "
             "via the tip-speed correction. Not used in reverse-thrust mode.",
    # --- Weight / cost ---
    "WTCON": "Airplane category for weight and cost estimation (1-5). "
             "1 = single-engine piston, 2 = multi-engine piston, "
             "3 = turboprop (Category III), 4 = advanced turboprop (Cat. IV), "
             "5 = advanced turboprop (Cat. V). "
             "Set to 0 to skip weight and cost.",
    "XNOE":  "Number of engines on the aircraft. "
             "Used in the unit-cost calculation (cost shared across engines).",
    "CLF1":  "Learning-curve factor 1 (quantity exponent). "
             "Set to 0 to use the program default (3.2178).",
    "CLF":   "Learning-curve factor 2 (cost slope). "
             "Set to 0 to use the program default (1.02).",
    "CK70":  "1970-technology cost slope constant. "
             "Set to 0 to have the program derive it from the aircraft category.",
    "CK80":  "1980-technology cost slope constant. "
             "Set to 0 to have the program derive it from the aircraft category.",
    "CAMT":  "Starting production quantity for the cost table. "
             "Typical values: 1 (prototype) to 500+ (series production).",
    "DAMT":  "Production-quantity increment for each cost table step.",
    "NAMT":  "Number of production-quantity steps (1-10). "
             "NAMT=1 computes cost at CAMT only.",
    # --- Reverse-thrust options ---
    "RTC":   "Reverse-thrust blade-angle control. "
             "1.0 = blade angle beta computed from CP (RTC mode). "
             "2.0 = blade angle beta supplied explicitly (BETA field). "
             "Set to 0 for IW=1 or IW=2 conditions.",
    "ROT":   "Engine type for reverse-thrust (IW=3). "
             "1.0 = reciprocating engine. "
             "2.0 = turbine engine. "
             "Set to 0 for IW=1 or IW=2 conditions.",
}

DEFS_CONDITION = {
    # --- Mode ---
    "IW":     "Computation mode. "
              "1 = shaft horsepower specified (BHP is the input, thrust computed). "
              "2 = thrust specified (THRUST is the input, BHP computed). "
              "3 = reverse-thrust computation (uses RPMC, ANDVK, PCPW, etc.).",
    # --- Power / thrust input ---
    "BHP":    "Shaft horsepower input (hp). Used when IW=1 or IW=3. "
              "For IW=3 this is the full-throttle SHP of the engine.",
    "THRUST": "Thrust target (lbf). Used when IW=2. "
              "The solver finds the BHP that produces exactly this thrust.",
    # --- Flight condition ---
    "ALT":    "Pressure altitude (ft). Range: 0-100 000 ft. "
              "Used to compute air density via the standard atmosphere.",
    "VKTAS":  "True airspeed (knots). Used to compute advance ratio J. "
              "Set to 0 for static (ground-run) conditions.",
    "T":      "Outside air temperature (degrees F). "
              "Set to 0 or negative to use the ISA standard temperature "
              "for the specified altitude.",
    # --- Tip-speed sweep ---
    "TS":     "Starting tip speed (ft/s). "
              "Ignored when STALIT > 0.5 (stall iteration overrides).",
    "DTS":    "Tip-speed increment (ft/s). Negative values decrease tip speed. "
              "Set to 0 when NDTS=1.",
    "NDTS":   "Number of tip-speed steps (1-10). "
              "Forced to 10 internally when STALIT > 0.5.",
    # --- Options ---
    "DIST":   "Sideline distance for noise computation (ft). "
              "Set to 0 to skip the noise calculation.",
    "STALIT": "50% stall tip-speed iteration flag. "
              "Set > 0.5 to have the solver iterate until the tip speed that "
              "produces 50% blade stall is found. "
              "Set to 0 for a normal tip-speed sweep.",
    "DCOST":  "Cost-calculation flag. "
              "1 = compute weight and unit cost (requires WTCON > 0 in geometry). "
              "0 = skip weight and cost.",
    # --- Reverse-thrust fields (IW=3 only) ---
    "RPMC":   "Full-throttle RPM of the engine (IW=3 only).",
    "ANDVK":  "Aircraft touch-down speed (knots). The reverse-thrust table is "
              "computed from 0 kts up to this speed (IW=3 only).",
    "PCPW":   "Starting power setting as a percentage of full-throttle SHP (%). "
              "Typically 100 % (IW=3 only).",
    "NPCPW":  "Number of power-setting steps (IW=3 only). "
              "The table is repeated for each step.",
    "DPCPW":  "Power-setting increment per step (%). "
              "Negative values reduce power (e.g. -20 gives 100/80/60 %) "
              "(IW=3 only).",
    "BETA":   "Blade angle at the 3/4-radius station (degrees). "
              "Used only when RTC=2.0 (blade angle given explicitly). "
              "Ignored when RTC=1.0 (IW=3 only).",
}


def _inject_defs_h432(path: Path) -> None:
    """Add variable_definitions to an existing .h432 session file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    ordered = {
        "variable_definitions": {
            "geometry":  DEFS_GEOMETRY,
            "condition": DEFS_CONDITION,
        }
    }
    ordered.update(data)          # geometry and conditions follow unchanged
    path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False),
                    encoding="utf-8")


def _fmt_defs_txt(defs: dict, title: str) -> str:
    """Format variable definitions as a plain-text block."""
    lines = [
        "=" * 80,
        f"  {title}",
        "=" * 80,
    ]
    for var, desc in defs.items():
        wrapped = textwrap.fill(desc, width=70,
                                initial_indent="    ",
                                subsequent_indent="    ")
        lines.append(f"  {var:<14}: {wrapped.strip()}")
    lines.append("=" * 80)
    return "\n".join(lines)


def _fmt_defs_csv(defs: dict, title: str) -> str:
    """Format variable definitions as # comment lines for CSV."""
    lines = [f"# {title}", "#"]
    for var, desc in defs.items():
        # Wrap long descriptions, prefixing each continuation line with #
        wrapped = textwrap.fill(f"{var}: {desc}", width=76,
                                initial_indent="#  ",
                                subsequent_indent="#    ")
        lines.append(wrapped)
    lines.append("#")
    return "\n".join(lines) + "\n"


def _inject_defs_txt(path: Path, defs: dict, title: str) -> None:
    """Prepend variable definitions into an existing .txt report."""
    original = path.read_text(encoding="utf-8")
    block = _fmt_defs_txt(defs, title)
    path.write_text(block + "\n\n" + original, encoding="utf-8")


def _inject_defs_csv(path: Path, defs: dict, title: str) -> None:
    """Prepend # comment definitions into an existing .csv file."""
    original = path.read_text(encoding="utf-8")
    block = _fmt_defs_csv(defs, title)
    path.write_text(block + original, encoding="utf-8")


def _inject_defs_json(path: Path, defs: dict) -> None:
    """Add a 'variable_definitions' key to an existing .json result file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    # Insert as the second key (after 'timestamp') for readability
    ordered = {}
    for k, v in data.items():
        ordered[k] = v
        if k == "program":
            ordered["variable_definitions"] = defs
    path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False),
                    encoding="utf-8")


# ======================================================================
# Main driver
# ======================================================================

def run_and_save(stem: str, conditions, geometry, description: str,
                 defs: dict, defs_title: str):
    """Run one case, save all four file formats, inject variable definitions."""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}")

    # ── Save loadable session (.h432) ─────────────────────────────
    session = {
        "geometry":   dataclasses.asdict(geometry),
        "conditions": [dataclasses.asdict(c) for c in conditions],
    }
    h432_path = OUT_DIR / f"{stem}.h432"
    h432_path.write_text(json.dumps(session, indent=2))
    _inject_defs_h432(h432_path)
    print(f"  Session  -> {h432_path.name}")

    # ── Run computation ───────────────────────────────────────────
    collector = ResultsCollector()
    main_module.set_collector(collector)
    call_input(conditions, geometry)
    try:
        main_loop()
    finally:
        main_module.set_collector(None)
    collector.summary.nof = len(conditions)

    n_rows = len(collector.summary.rows)
    n_rev  = len(collector.summary.rev_rows)
    print(f"  Result rows: {n_rows}   Rev-thrust rows: {n_rev}")

    # ── Save raw results ──────────────────────────────────────────
    writer = ReportWriter(collector.summary)
    stem_path = OUT_DIR / stem
    saved = writer.save_all(stem_path)

    # ── Inject variable definitions ───────────────────────────────
    _inject_defs_txt(saved["text"], defs, defs_title)
    _inject_defs_csv(saved["csv"],  defs, defs_title)
    _inject_defs_json(saved["json"], defs)

    for fmt, path in saved.items():
        print(f"  {fmt:5s}    -> {path.name}")


# ======================================================================
# Case 1 — SHP INPUT  |  TIPSPEED & DIAMETER VARIATION  |  COST & WEIGHT
# ======================================================================
# Two operating conditions on the same propeller geometry:
#   Cond 1 — Climb  : 350 SHP, sea level, 90 kts
#   Cond 2 — Cruise : 350 SHP, 7 500 ft,  150 kts
# Two diameters (6 ft and 8 ft) × four tip speeds (850→550 fps).
# Results: 16 performance rows (8 per condition) + weight/cost (Cat. II).
# ======================================================================
geom1 = PropellerGeometry(
    D=6.0,   DD=2.0, ND=2,          # 6.0 ft and 8.0 ft
    AF=150.0, DAF=0.0, NAF=1,
    BLADN=4.0, DBLAD=0.0, NBL=1,
    CLII=0.5,  DCLI=0.0, ZNCLI=1,
    ZMWT=0.262,                      # design Mach ~ 0.26
    WTCON=2.0,                       # Category II - multi-engine piston
    XNOE=1.0,
    CAMT=500.0, DAMT=500.0, NAMT=1,
)
cond1 = [
    OperatingCondition(              # Condition 1 - Climb
        IW=1,
        BHP=350.0,
        ALT=0.0, VKTAS=90.0, T=0.0,
        TS=850.0, DTS=-100.0, NDTS=4,   # 850 / 750 / 650 / 550 fps
        DCOST=1.0,
    ),
    OperatingCondition(              # Condition 2 - Cruise
        IW=1,
        BHP=350.0,
        ALT=7500.0, VKTAS=150.0, T=0.0,
        TS=850.0, DTS=-100.0, NDTS=4,
        DCOST=1.0,
    ),
]
run_and_save(
    "case1_shp_tipspeed_diameter_cost", cond1, geom1,
    "Case 1 - SHP INPUT | TIPSPEED & DIAMETER VARIATION | COST & WEIGHT",
    DEFS_PERF,
    "VARIABLE DEFINITIONS — Case 1: SHP Input, Tip-Speed & Diameter Variation, "
    "Cost & Weight",
)


# ======================================================================
# Case 2 — THRUST INPUT  |  TIPSPEED & DIAMETER VARIATION  |  COST & WEIGHT
# ======================================================================
# Two operating conditions on the same propeller geometry:
#   Cond 1 — Take-off : 820 lbf,  sea level,  71.2 kts, noise at 500 ft
#   Cond 2 — Cruise   : 370 lbf,  7 500 ft,  163.2 kts, T=32.33 F
# Two diameters (6 ft and 8 ft) × four tip speeds (850→550 fps).
# Results: 16 performance rows (8 per condition) + weight/cost (Cat. II).
# ======================================================================
geom2 = PropellerGeometry(
    D=6.0,   DD=2.0, ND=2,          # 6.0 ft and 8.0 ft
    AF=150.0, DAF=0.0, NAF=1,
    BLADN=4.0, DBLAD=0.0, NBL=1,
    CLII=0.5,  DCLI=0.0, ZNCLI=1,
    ZMWT=0.262,
    WTCON=2.0,                       # Category II
    XNOE=1.0,
    CAMT=500.0, DAMT=500.0, NAMT=1,
)
cond2 = [
    OperatingCondition(              # Condition 1 - Take-off
        IW=2,
        THRUST=820.0,
        ALT=0.0, VKTAS=71.2, T=0.0,
        TS=850.0, DTS=-100.0, NDTS=4,   # 850 / 750 / 650 / 550 fps
        DIST=500.0,                      # noise at 500 ft sideline
        DCOST=1.0,
    ),
    OperatingCondition(              # Condition 2 - Cruise
        IW=2,
        THRUST=370.0,
        ALT=7500.0, VKTAS=163.2, T=32.33,   # explicit temperature 32.33 F
        TS=850.0, DTS=-100.0, NDTS=4,
        DIST=0.0,
        DCOST=0.0,
    ),
]
run_and_save(
    "case2_thrust_tipspeed_diameter_cost", cond2, geom2,
    "Case 2 - THRUST INPUT | TIPSPEED & DIAMETER VARIATION | COST & WEIGHT",
    DEFS_PERF,
    "VARIABLE DEFINITIONS — Case 2: Thrust Input, Tip-Speed & Diameter "
    "Variation, Cost & Weight",
)


# ======================================================================
# Case 3 — SHP INPUT  |  50% STALL TIP SPEED  |  COST FOR RANGE OF QTY
# ======================================================================
# Turboprop — 340 SHP, sea level, 77.5 kts.
# STALIT=1 -> solver iterates to find 50% stall tip speed.
# Two blade counts (4 and 6), five production quantities.
# ======================================================================
geom3 = PropellerGeometry(
    D=8.0,   DD=0.0, ND=1,
    AF=200.0, DAF=0.0, NAF=1,
    BLADN=4.0, DBLAD=2.0, NBL=2,   # 4 blades and 6 blades
    CLII=0.6,  DCLI=0.0, ZNCLI=1,
    ZMWT=0.327,
    WTCON=4.0,                       # Category IV - advanced turboprop
    XNOE=2.0,
    CAMT=1.0, DAMT=1000.0, NAMT=5, # qty: 1 / 1001 / 2001 / 3001 / 4001
)
cond3 = [OperatingCondition(
    IW=1,
    BHP=340.0,
    ALT=0.0, VKTAS=77.5, T=0.0,
    TS=700.0, DTS=0.0, NDTS=1,      # starting TS - overridden by STALIT loop
    DIST=500.0,
    STALIT=1.0,                      # iterate to 50% stall tip speed
    DCOST=1.0,
)]
run_and_save(
    "case3_shp_stall_cost_qty", cond3, geom3,
    "Case 3 - SHP INPUT | 50% STALL TIP SPEED | COST FOR RANGE OF QTY",
    DEFS_PERF,
    "VARIABLE DEFINITIONS — Case 3: SHP Input, 50% Stall Tip-Speed Iteration, "
    "Cost for Range of Production Quantities",
)


# ======================================================================
# Case 4 — REVERSE THRUST
# ======================================================================
# Reciprocating engine, 550 SHP / 2200 RPM.
# RTC=1 -> blade angle beta computed from CP.
# Three power settings: 100% / 80% / 60%.
# ======================================================================
geom4 = PropellerGeometry(
    D=8.5,   DD=0.0, ND=1,
    AF=109.0, DAF=0.0, NAF=1,
    BLADN=3.0, DBLAD=0.0, NBL=1,
    CLII=0.509, DCLI=0.0, ZNCLI=1,
    ZMWT=0.3,
    RTC=1.0,                         # compute beta from CP
    ROT=1.0,                         # reciprocating engine
)
cond4 = [OperatingCondition(
    IW=3,
    BHP=550.0,
    ALT=0.0, VKTAS=0.0, T=0.0,
    RPMC=2200.0,
    ANDVK=72.0,                      # touch-down speed
    PCPW=100.0, NPCPW=3, DPCPW=-20.0,  # 100 / 80 / 60 %
    BETA=0.0,
    TS=700.0, DTS=0.0, NDTS=1,
)]
run_and_save(
    "case4_reverse_thrust", cond4, geom4,
    "Case 4 - REVERSE THRUST | Reciprocating 550 SHP | 3 power steps",
    DEFS_REV,
    "VARIABLE DEFINITIONS — Case 4: Reverse Thrust Computation",
)


print(f"\n{'='*60}")
print(f"  All examples written to: {OUT_DIR}")
print(f"{'='*60}\n")
