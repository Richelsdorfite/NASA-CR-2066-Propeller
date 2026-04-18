"""
output.py — Results capture, formatting, and export for the NASA CR-2066 propeller program.

Provides
--------
ResultRow        dataclass for one line of propeller performance output
ResultsCollector accumulates rows during a run; replaces print-only approach
ReportWriter     formats collected results as plain text (Fortran-compatible),
                 CSV, and JSON; handles file I/O
"""

from __future__ import annotations
import csv
import json
import io
import textwrap
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from units import (UnitSystem, FT_TO_M, FPS_TO_MS, HP_TO_KW,
                   LBF_TO_N, LB_TO_KG, FTLBF_TO_NM, to_si, unit_label)


# ======================================================================
# Data structures
# ======================================================================

@dataclass
class ResultRow:
    """One line of propeller performance output (one diameter / tip-speed point)."""
    # Operating condition index (1-based)
    condition:  int   = 0
    # Geometry
    blades:     float = 0.0   # number of blades
    af:         float = 0.0   # activity factor
    cli:        float = 0.0   # integrated design CL
    dia_ft:     float = 0.0   # diameter, ft
    tipspd_fps: float = 0.0   # tip speed, ft/s
    # Performance
    cp:         float = 0.0   # power coefficient
    ct:         float = 0.0   # thrust coefficient
    blade_ang:  float = 0.0   # blade angle, deg (BLLLL)
    j:          float = 0.0   # advance ratio
    mach_tip:   float = 0.0   # tip Mach number
    mach_fs:    float = 0.0   # freestream Mach number
    ft:         float = 0.0   # compressibility correction factor
    eta:        float = 0.0   # propeller efficiency  η = J·CT/CP  (0–1); 0 when J=0 or CP=0
    # Output (IW-dependent)
    thrust_lb:  float = 0.0   # thrust, lbf
    shp:        float = 0.0   # shaft horsepower
    torque:     float = 0.0   # shaft torque, ft·lbf  (= SHP × 5252.11 / RPM)
    pnl_db:     float = 0.0   # perceived noise level, dB (0 = not computed)
    # Weight / cost (optional)
    wt70_lb:    float = 0.0   # 1970-tech weight, lb
    wt80_lb:    float = 0.0   # 1980-tech weight, lb
    cost70:     float = 0.0   # 1970-tech unit cost ($)
    cost80:     float = 0.0   # 1980-tech unit cost ($)
    qty70:      List[float] = field(default_factory=list)  # 1970-tech production quantities
    qty80:      List[float] = field(default_factory=list)  # 1980-tech production quantities
    cost70_qty: List[float] = field(default_factory=list)  # 1970-tech costs at qty levels
    cost80_qty: List[float] = field(default_factory=list)  # 1980-tech costs at qty levels
    # Flags
    off_chart:  bool  = False  # True if PERFM returned ASTERK


@dataclass
class RevThrustRow:
    """One speed-point row of a reverse-thrust performance table (IW=3)."""
    condition: int   = 0      # 1-based operating condition index
    blades:    float = 0.0    # blade count
    af:        float = 0.0    # activity factor
    cli:       float = 0.0    # integrated design CL
    dia_ft:    float = 0.0    # propeller diameter, ft
    pcpw:      float = 0.0    # power setting, %
    theta_deg: float = 0.0    # blade angle at 3/4 radius, degrees
    vk_kts:    float = 0.0    # airspeed, knots
    thrust_lb: float = 0.0    # reverse thrust, lbf
    shp:       float = 0.0    # shaft horsepower
    torque:    float = 0.0    # shaft torque, ft·lbf  (= SHP × 5252.11 / RPM)
    rpm:       float = 0.0    # propeller RPM


@dataclass
class MapPoint:
    """One J-sweep point on a propeller characteristic curve."""
    j:         float = 0.0
    cp:        float = 0.0
    ct:        float = 0.0
    eta:       float = 0.0    # J·CT/CP; 0.0 when J=0 or CP≤0
    blade_ang: float = 0.0    # blade angle at 3/4 radius, deg
    off_chart: bool  = False  # True when PERFM returned the ASTERK sentinel


@dataclass
class MapCurve:
    """One geometry combination's complete J sweep."""
    label:  str              = ""
    blades: float            = 0.0
    af:     float            = 0.0
    cli:    float            = 0.0
    dia_ft: float            = 0.0
    vt_fps: float            = 0.0
    points: List[MapPoint]   = field(default_factory=list)


@dataclass
class MapResult:
    """All curves from one propeller characteristic map run."""
    timestamp: str            = field(default_factory=lambda: datetime.now().isoformat(timespec='seconds'))
    curves:    List[MapCurve] = field(default_factory=list)

    def as_csv(self) -> str:
        """Export every map point as a flat CSV file."""
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator='\n')
        w.writerow(["curve", "blades", "af", "cli", "dia_ft", "vt_fps",
                    "j", "cp", "ct", "eta", "blade_ang", "off_chart"])
        for c in self.curves:
            for p in c.points:
                w.writerow([c.label, c.blades, c.af, c.cli, c.dia_ft, c.vt_fps,
                            p.j, p.cp, p.ct, p.eta, p.blade_ang, p.off_chart])
        return buf.getvalue()


@dataclass
class RunSummary:
    """Metadata for one complete program run."""
    timestamp:   str        = field(default_factory=lambda: datetime.now().isoformat(timespec='seconds'))
    program:     str        = "Hamilton Standard H432 – NASA CR-2066"
    nof:         int        = 0      # number of operating conditions
    unit_system: str        = "US"   # "US" or "SI" — unit system used for display/save
    rows:        List[ResultRow] = field(default_factory=list)
    rev_rows:    List[RevThrustRow] = field(default_factory=list)
    messages:    List[str]  = field(default_factory=list)   # warnings / errors


# ======================================================================
# Collector – used by MAIN.py to accumulate results
# ======================================================================

class ResultsCollector:
    """
    Accumulates ResultRow objects and text messages during a run.

    Usage
    -----
    collector = ResultsCollector()
    MAIN.set_collector(collector)   # wires _emit() in MAIN/PERFM/REVTHT
    try:
        main_loop()
    finally:
        MAIN.set_collector(None)
    # collector.summary now contains all rows and messages
    """

    def __init__(self):
        self.summary = RunSummary()
        # Optional progress callback — called (from the background thread) after
        # each row is added.  Set by the HMI to drive the progress bar.
        self._tick_fn: Optional[callable] = None

    # ── Row accumulation ──────────────────────────────────────────────────

    def add_row(self, row: ResultRow) -> None:
        self.summary.rows.append(row)
        if self._tick_fn is not None:
            self._tick_fn()

    def add_rev_row(self, row: RevThrustRow) -> None:
        self.summary.rev_rows.append(row)
        if self._tick_fn is not None:
            self._tick_fn()

    def add_message(self, msg: str) -> None:
        self.summary.messages.append(msg)

    def set_nof(self, nof: int) -> None:
        self.summary.nof = nof

    def clear(self) -> None:
        self.summary = RunSummary()


# ======================================================================
# Report writer – formats and saves results
# ======================================================================

class ReportWriter:
    """
    Formats a RunSummary as plain text, CSV, or JSON and writes to disk.

    All three formats are independent; call whichever you need.
    """

    HEADER_BANNER = textwrap.dedent("""\
        ================================================================================
                           HAMILTON STANDARD COMPUTER DECK NO. H432
                         COMPUTES PERFORMANCE, NOISE, WEIGHT, AND COST FOR
                                    GENERAL AVIATION PROPELLERS
        ================================================================================
    """)

    # CSV column order for normal performance rows
    CSV_FIELDS = [
        "condition", "blades", "af", "cli",
        "dia_ft", "tipspd_fps",
        "cp", "ct", "blade_ang", "j", "mach_tip", "mach_fs", "ft", "eta",
        "thrust_lb", "shp", "torque", "pnl_db",
        "qty70", "wt70_lb", "cost70_qty",
        "qty80", "wt80_lb", "cost80_qty",
        "off_chart",
    ]

    # CSV column order for reverse-thrust rows
    REV_CSV_FIELDS = [
        "condition", "blades", "af", "cli", "dia_ft",
        "pcpw", "theta_deg", "vk_kts", "thrust_lb", "shp", "torque", "rpm",
    ]

    def __init__(self, summary: RunSummary):
        self.summary = summary

    # ── Text report ───────────────────────────────────────────────────────

    def as_text(self) -> str:
        """Return a full plain-text report."""
        us = UnitSystem(self.summary.unit_system)
        lines = [self.HEADER_BANNER]
        lines.append(f"  Run date/time : {self.summary.timestamp}")
        lines.append(f"  Unit system   : {self.summary.unit_system}")
        lines.append(f"  Conditions    : {self.summary.nof}")
        lines.append(f"  Result rows   : {len(self.summary.rows)}")
        if self.summary.rev_rows:
            lines.append(f"  Rev-thrust rows: {len(self.summary.rev_rows)}")
        lines.append("")

        if self.summary.rows:
            lines.append(self._text_table(us))

        if self.summary.rev_rows:
            lines.append(self._rev_text_table(us))

        if self.summary.messages:
            lines.append("\n── Messages / Warnings " + "─"*57)
            for msg in self.summary.messages:
                lines.append(f"  {msg}")

        return "\n".join(lines) + "\n"

    def _rev_text_table(self, us: UnitSystem = UnitSystem.US) -> str:
        """Format RevThrustRow list as a fixed-width table."""
        d_u  = unit_label("ft",     "m",   us)
        t_u  = unit_label("lbf",    "N",   us)
        p_u  = unit_label("hp",     "kW",  us)
        q_u  = unit_label("ft·lbf", "N·m", us)
        hdr   = (f"{'IC':>3} {'BL':>3} {'AF':>5} {'CLi':>5} {'Dia':>6}"
                 f" {'PCPW%':>6} {'Theta':>7} {'VK':>7} {'Thrust':>9} {'SHP':>8}"
                 f" {'Torque':>10} {'RPM':>7}")
        units = (f"{'':>3} {'':>3} {'':>5} {'':>5} {d_u:>6}"
                 f" {'%':>6} {'deg':>7} {'kts':>7} {t_u:>9} {p_u:>8}"
                 f" {q_u:>10} {'':>7}")
        sep   = "─" * len(hdr)
        rows_text = []
        for r in self.summary.rev_rows:
            dia    = to_si(r.dia_ft,    FT_TO_M,     us)
            thrust = to_si(r.thrust_lb, LBF_TO_N,    us)
            shp    = to_si(r.shp,       HP_TO_KW,    us)
            torque = to_si(r.torque,    FTLBF_TO_NM, us)
            rows_text.append(
                f"{r.condition:>3} {r.blades:>3.0f} {r.af:>5.0f} {r.cli:>5.3f} {dia:>6.2f}"
                f" {r.pcpw:>6.0f} {r.theta_deg:>7.1f} {r.vk_kts:>7.1f}"
                f" {thrust:>9.0f} {shp:>8.1f}"
                f" {torque:>10.1f} {r.rpm:>7.0f}"
            )
        title = "\n── Reverse Thrust Performance " + "─" * 60
        return "\n".join([title, sep, hdr, units, sep] + rows_text + [sep])

    def _text_table(self, us: UnitSystem = UnitSystem.US) -> str:
        """Format ResultRow list as a fixed-width table."""
        d_u  = unit_label("ft",     "m",     us)
        vt_u = unit_label("fps",    "m/s",   us)
        t_u  = unit_label("lbf",    "N",     us)
        p_u  = unit_label("hp",     "kW",    us)
        w_u  = unit_label("lb",     "kg",    us)
        q_u  = unit_label("ft·lbf", "N·m",   us)

        hdr  = (f"{'IC':>3} {'BL':>3} {'AF':>5} {'CLi':>5} "
                f"{'Dia':>6} {'Vt':>7} "
                f"{'J':>6} {'M':>6} {'Mt':>6} {'BldAng':>7} "
                f"{'CP':>8} {'CT':>8} "
                f"{'FT':>6} {'Eff':>7} "
                f"{'Thrust':>9} {'SHP':>8} {'Torque':>10} {'PNL':>7} "
                f"{'Wt70':>7} {'Wt80':>7} {'$70':>8} {'$80':>8}")
        units = (f"{'':>3} {'':>3} {'':>5} {'':>5} "
                 f"{d_u:>6} {vt_u:>7} "
                 f"{'':>6} {'':>6} {'':>6} {'deg':>7} "
                 f"{'':>8} {'':>8} "
                 f"{'':>6} {'%':>7} "
                 f"{t_u:>9} {p_u:>8} {q_u:>10} {'dB':>7} "
                 f"{w_u:>7} {w_u:>7} {'$':>8} {'$':>8}")
        sep  = "─" * len(hdr)

        rows_text = []
        for r in self.summary.rows:
            flag   = "*" if r.off_chart else " "
            dia    = to_si(r.dia_ft,    FT_TO_M,     us)
            vt     = to_si(r.tipspd_fps,FPS_TO_MS,   us)
            thrust = to_si(r.thrust_lb, LBF_TO_N,    us)
            shp    = to_si(r.shp,       HP_TO_KW,    us)
            torque = to_si(r.torque,    FTLBF_TO_NM, us)
            wt70   = to_si(r.wt70_lb,   LB_TO_KG,    us)
            wt80   = to_si(r.wt80_lb,   LB_TO_KG,    us)
            rows_text.append(
                f"{r.condition:>3} {r.blades:>3.0f} {r.af:>5.0f} {r.cli:>5.3f} "
                f"{dia:>6.2f} {vt:>7.1f} "
                f"{r.j:>6.3f} {r.mach_fs:>6.4f} {r.mach_tip:>6.4f} {r.blade_ang:>7.2f} "
                f"{r.cp:>8.5f} {r.ct:>8.5f} "
                f"{r.ft:>6.4f} {r.eta*100:>7.2f} "
                f"{thrust:>9.0f} {shp:>8.1f} {torque:>10.1f} {r.pnl_db:>7.1f} "
                f"{wt70:>7.1f} {wt80:>7.1f} "
                f"{r.cost70:>8.0f} {r.cost80:>8.0f}{flag}"
            )

            # Add quantity/cost breakdown if present
            if r.qty70 or r.qty80:
                rows_text.append("    ├─ Production Quantities & Unit Costs")
                rows_text.append("    │   Qty70  Cost70($)   Qty80  Cost80($)")
                for i in range(max(len(r.qty70), len(r.qty80))):
                    q70 = r.qty70[i] if i < len(r.qty70) else 0.0
                    c70 = r.cost70_qty[i] if i < len(r.cost70_qty) else 0.0
                    q80 = r.qty80[i] if i < len(r.qty80) else 0.0
                    c80 = r.cost80_qty[i] if i < len(r.cost80_qty) else 0.0
                    rows_text.append(f"    │   {q70:7.0f}  {c70:9.2f}   {q80:7.0f}  {c80:9.2f}")
                rows_text.append("    └─")

        return "\n".join([sep, hdr, units, sep] + rows_text + [sep])

    # ── CSV export ────────────────────────────────────────────────────────

    def as_csv(self) -> str:
        """Return CSV string.

        Values are expressed in the unit system stored in summary.unit_system.
        A comment header line records that unit system.

        If only reverse-thrust rows exist, writes them with REV_CSV_FIELDS columns.
        If only normal rows exist, writes them with CSV_FIELDS columns.
        If both exist, writes normal rows first, then appends reverse-thrust rows
        under their own header (separated by a blank line).
        """
        us  = UnitSystem(self.summary.unit_system)
        buf = io.StringIO()

        # Unit-system comment header
        buf.write(f"# unit_system={self.summary.unit_system}\n")

        # ── Column headers with units for each system ─────────────────────
        # Build a display-name mapping for dimensional columns
        dim_headers = {
            "dia_ft":     unit_label("dia_ft",     "dia_m",   us),
            "tipspd_fps": unit_label("tipspd_fps",  "tipspd_ms", us),
            "thrust_lb":  unit_label("thrust_lbf",  "thrust_N", us),
            "shp":        unit_label("shp_hp",       "shp_kW",  us),
            "wt70_lb":    unit_label("wt70_lb",      "wt70_kg", us),
            "wt80_lb":    unit_label("wt80_lb",      "wt80_kg",      us),
            "torque":     unit_label("torque_ftlbf", "torque_Nm",    us),
            # Rev-thrust specific
            "vk_kts":     "vk_kts",   # always knots
        }

        def _display_fieldnames(fields):
            return [dim_headers.get(f, f) for f in fields]

        # ── Normal performance rows ───────────────────────────────────────
        if self.summary.rows:
            writer = csv.DictWriter(buf,
                                    fieldnames=_display_fieldnames(self.CSV_FIELDS),
                                    extrasaction='ignore', lineterminator='\n')
            writer.writeheader()
            for row in self.summary.rows:
                row_dict = {}
                for k, dk in zip(self.CSV_FIELDS, _display_fieldnames(self.CSV_FIELDS)):
                    val = getattr(row, k)
                    if isinstance(val, list):
                        row_dict[dk] = ";".join(
                            f"{v:.2f}" if isinstance(v, float) else str(v) for v in val)
                    else:
                        # Convert dimensional scalars
                        if k == "dia_ft":
                            val = to_si(val, FT_TO_M,   us)
                        elif k == "tipspd_fps":
                            val = to_si(val, FPS_TO_MS, us)
                        elif k == "thrust_lb":
                            val = to_si(val, LBF_TO_N,  us)
                        elif k == "shp":
                            val = to_si(val, HP_TO_KW,  us)
                        elif k in ("wt70_lb", "wt80_lb"):
                            val = to_si(val, LB_TO_KG,    us)
                        elif k == "torque":
                            val = to_si(val, FTLBF_TO_NM, us)
                        row_dict[dk] = val
                writer.writerow(row_dict)

        # ── Reverse-thrust rows ───────────────────────────────────────────
        if self.summary.rev_rows:
            if self.summary.rows:
                buf.write("\n")   # blank line separator between sections
            rev_display = _display_fieldnames(self.REV_CSV_FIELDS)
            rev_writer = csv.DictWriter(buf, fieldnames=rev_display,
                                        extrasaction='ignore', lineterminator='\n')
            rev_writer.writeheader()
            for row in self.summary.rev_rows:
                row_dict = {}
                for k, dk in zip(self.REV_CSV_FIELDS, rev_display):
                    val = getattr(row, k)
                    if k == "dia_ft":
                        val = to_si(val, FT_TO_M,     us)
                    elif k == "thrust_lb":
                        val = to_si(val, LBF_TO_N,    us)
                    elif k == "shp":
                        val = to_si(val, HP_TO_KW,    us)
                    elif k == "torque":
                        val = to_si(val, FTLBF_TO_NM, us)
                    row_dict[dk] = val
                rev_writer.writerow(row_dict)

        return buf.getvalue()

    # ── JSON export ───────────────────────────────────────────────────────

    def as_json(self) -> str:
        """Return a JSON string of the entire RunSummary.

        Dimensional values are expressed in the unit system recorded in
        summary.unit_system.  The JSON key names reflect that unit system
        (e.g. "dia_m" instead of "dia_ft" when unit_system=="SI").
        """
        us = UnitSystem(self.summary.unit_system)

        def convert_to_native(obj):
            """Recursively convert numpy and other types to native Python types."""
            if isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_to_native(v) for v in obj]
            elif isinstance(obj, (bool, int, float, str, type(None))):
                return obj
            else:
                try:
                    return float(obj) if isinstance(obj, (int, float)) else str(obj)
                except (TypeError, ValueError):
                    return str(obj)

        def _convert_row(r) -> dict:
            d = asdict(r)
            if us == UnitSystem.SI:
                d["dia_m"]         = round(d.pop("dia_ft")     * FT_TO_M,     4)
                d["tipspd_ms"]     = round(d.pop("tipspd_fps") * FPS_TO_MS,   3)
                d["thrust_N"]      = round(d.pop("thrust_lb")  * LBF_TO_N,    2)
                d["shp_kW"]        = round(d.pop("shp")        * HP_TO_KW,    3)
                d["torque_Nm"]     = round(d.pop("torque")     * FTLBF_TO_NM, 2)
                d["wt70_kg"]       = round(d.pop("wt70_lb")    * LB_TO_KG,    3)
                d["wt80_kg"]       = round(d.pop("wt80_lb")    * LB_TO_KG,    3)
            return d

        def _convert_rev_row(r) -> dict:
            d = asdict(r)
            if us == UnitSystem.SI:
                d["dia_m"]      = round(d.pop("dia_ft")    * FT_TO_M,     4)
                d["thrust_N"]   = round(d.pop("thrust_lb") * LBF_TO_N,    2)
                d["shp_kW"]     = round(d.pop("shp")       * HP_TO_KW,    3)
                d["torque_Nm"]  = round(d.pop("torque")    * FTLBF_TO_NM, 2)
            return d

        data = {
            "timestamp":   self.summary.timestamp,
            "program":     self.summary.program,
            "unit_system": self.summary.unit_system,
            "nof":         self.summary.nof,
            "rows":        [_convert_row(r)     for r in self.summary.rows],
            "rev_rows":    [_convert_rev_row(r) for r in self.summary.rev_rows],
            "messages":    self.summary.messages,
        }
        data = convert_to_native(data)
        return json.dumps(data, indent=2)

    # ── File I/O ──────────────────────────────────────────────────────────

    def save_text(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(self.as_text(), encoding="utf-8")
        return p

    def save_csv(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(self.as_csv(), encoding="utf-8")
        return p

    def save_json(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(self.as_json(), encoding="utf-8")
        return p

    def save_all(self, stem: str | Path) -> dict[str, Path]:
        """Save text, CSV, and JSON with the same stem."""
        stem = Path(stem)
        return {
            "text": self.save_text(stem.with_suffix(".txt")),
            "csv":  self.save_csv(stem.with_suffix(".csv")),
            "json": self.save_json(stem.with_suffix(".json")),
        }
