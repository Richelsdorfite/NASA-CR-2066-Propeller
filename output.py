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
import sys
import textwrap
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, TextIO


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
    # Output (IW-dependent)
    thrust_lb:  float = 0.0   # thrust, lbf
    shp:        float = 0.0   # shaft horsepower
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
class RunSummary:
    """Metadata for one complete program run."""
    timestamp:   str        = field(default_factory=lambda: datetime.now().isoformat(timespec='seconds'))
    program:     str        = "Hamilton Standard H432 – NASA CR-2066"
    nof:         int        = 0      # number of operating conditions
    rows:        List[ResultRow] = field(default_factory=list)
    messages:    List[str]  = field(default_factory=list)   # warnings / errors


# ======================================================================
# Collector – used by MAIN.py to accumulate results
# ======================================================================

class ResultsCollector:
    """
    Accumulates ResultRow objects during a run and captures any textual
    messages (warnings, format lines) that MAIN.py emits via print().

    Usage in MAIN.py
    ----------------
    collector = ResultsCollector()
    with collector.capture_stdout():
        main_loop()          # all print() output is intercepted
    # collector.summary now contains all rows and messages
    """

    def __init__(self):
        self.summary = RunSummary()
        self._stdout_buf: Optional[io.StringIO] = None
        self._old_stdout: Optional[TextIO] = None

    # ── Row accumulation ──────────────────────────────────────────────────

    def add_row(self, row: ResultRow) -> None:
        self.summary.rows.append(row)

    def add_message(self, msg: str) -> None:
        self.summary.messages.append(msg)

    def set_nof(self, nof: int) -> None:
        self.summary.nof = nof

    # ── stdout capture (context manager) ─────────────────────────────────

    def capture_stdout(self):
        return _StdoutCapture(self)

    @property
    def captured_text(self) -> str:
        return self._stdout_buf.getvalue() if self._stdout_buf else ""

    def clear(self) -> None:
        self.summary = RunSummary()
        self._stdout_buf = None


class _StdoutCapture:
    def __init__(self, collector: ResultsCollector):
        self._col = collector

    def __enter__(self):
        self._col._stdout_buf = io.StringIO()
        self._col._old_stdout = sys.stdout
        sys.stdout = self._col._stdout_buf
        return self._col

    def __exit__(self, *_):
        # Restore stdout
        sys.stdout = self._col._old_stdout
        # Parse captured lines into messages
        for line in self._col._stdout_buf.getvalue().splitlines():
            if line.strip():
                self._col.summary.messages.append(line)


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

    # CSV column order (grouped by technology)
    CSV_FIELDS = [
        "condition", "blades", "af", "cli",
        "dia_ft", "tipspd_fps",
        "cp", "ct", "blade_ang", "j", "mach_tip", "mach_fs", "ft",
        "thrust_lb", "shp", "pnl_db",
        "qty70", "wt70_lb", "cost70_qty",
        "qty80", "wt80_lb", "cost80_qty",
        "off_chart",
    ]

    def __init__(self, summary: RunSummary):
        self.summary = summary

    # ── Text report ───────────────────────────────────────────────────────

    def as_text(self) -> str:
        """Return a full plain-text report."""
        lines = [self.HEADER_BANNER]
        lines.append(f"  Run date/time : {self.summary.timestamp}")
        lines.append(f"  Conditions    : {self.summary.nof}")
        lines.append(f"  Result rows   : {len(self.summary.rows)}")
        lines.append("")

        if self.summary.rows:
            lines.append(self._text_table())

        if self.summary.messages:
            lines.append("\n── Messages / Warnings " + "─"*57)
            for msg in self.summary.messages:
                lines.append(f"  {msg}")

        return "\n".join(lines) + "\n"

    def _text_table(self) -> str:
        """Format ResultRow list as a fixed-width table."""
        sep  = "─" * 145
        hdr  = (f"{'IC':>3} {'BL':>3} {'AF':>5} {'CLi':>5} "
                f"{'Dia':>6} {'Vt':>7} "
                f"{'J':>6} {'M':>6} {'Mt':>6} {'BldAng':>7} "
                f"{'CP':>8} {'CT':>8} "
                f"{'FT':>6} "
                f"{'Thrust':>9} {'SHP':>8} {'PNL':>7} "
                f"{'Wt70':>7} {'Wt80':>7} {'$70':>8} {'$80':>8}")
        units = (f"{'':>3} {'':>3} {'':>5} {'':>5} "
                 f"{'ft':>6} {'fps':>7} "
                 f"{'':>6} {'':>6} {'':>6} {'deg':>7} "
                 f"{'':>8} {'':>8} "
                 f"{'':>6} "
                 f"{'lbf':>9} {'hp':>8} {'dB':>7} "
                 f"{'lb':>7} {'lb':>7} {'$':>8} {'$':>8}")

        rows_text = []
        for r in self.summary.rows:
            flag = "*" if r.off_chart else " "
            rows_text.append(
                f"{r.condition:>3} {r.blades:>3.0f} {r.af:>5.0f} {r.cli:>5.3f} "
                f"{r.dia_ft:>6.2f} {r.tipspd_fps:>7.0f} "
                f"{r.j:>6.3f} {r.mach_fs:>6.4f} {r.mach_tip:>6.4f} {r.blade_ang:>7.2f} "
                f"{r.cp:>8.5f} {r.ct:>8.5f} "
                f"{r.ft:>6.4f} "
                f"{r.thrust_lb:>9.0f} {r.shp:>8.0f} {r.pnl_db:>7.1f} "
                f"{r.wt70_lb:>7.1f} {r.wt80_lb:>7.1f} "
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
        """Return CSV string (header + one row per ResultRow)."""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=self.CSV_FIELDS,
                                extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        for row in self.summary.rows:
            row_dict = {}
            for k in self.CSV_FIELDS:
                val = getattr(row, k)
                # Convert list fields to semicolon-separated values for CSV
                if isinstance(val, list):
                    row_dict[k] = ";".join(f"{v:.2f}" if isinstance(v, float) else str(v) for v in val)
                else:
                    row_dict[k] = val
            writer.writerow(row_dict)
        return buf.getvalue()

    # ── JSON export ───────────────────────────────────────────────────────

    def as_json(self) -> str:
        """Return a JSON string of the entire RunSummary."""
        def convert_to_native(obj):
            """Recursively convert numpy and other types to native Python types."""
            if isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_to_native(v) for v in obj]
            elif isinstance(obj, (bool, int, float, str, type(None))):
                return obj
            else:
                # Convert numpy types, bool types, etc.
                try:
                    return float(obj) if isinstance(obj, (int, float)) else str(obj)
                except (TypeError, ValueError):
                    return str(obj)

        data = {
            "timestamp":  self.summary.timestamp,
            "program":    self.summary.program,
            "nof":        self.summary.nof,
            "rows":       [asdict(r) for r in self.summary.rows],
            "messages":   self.summary.messages,
        }
        # Convert all values to native Python types for JSON serialization
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
