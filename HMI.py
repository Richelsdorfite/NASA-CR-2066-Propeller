"""
HMI.py — Human-Machine Interface for the NASA CR-2066 propeller program.

Replaces the 1970s perf-card (punch-card) INPUT with a modern GUI.

Run:
    python HMI.py

Layout
------
  ┌─ Toolbar ─────────────────────────────────────────────────────────┐
  │  [▶ Run]  [💾 Save]  [📂 Load]  [✕ Clear]          status bar   │
  ├─ Notebook ─────────────────────────────────────────────────────────┤
  │  [⚙ Geometry]  [📋 Conditions]  [📊 Results]  [📝 Log]          │
  └───────────────────────────────────────────────────────────────────┘

Aesthetic: industrial / avionics — dark slate, amber accents, mono data font.
"""

import json
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

# ── Local modules ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from operating_condition import OperatingCondition, PropellerGeometry, load_conditions
from output import ResultsCollector, ResultRow, ReportWriter, RevThrustRow
from units import (UnitSystem, FT_TO_M, FPS_TO_MS, HP_TO_KW, LBF_TO_N, LB_TO_KG,
                   FTLBF_TO_NM, to_si, from_si, unit_label,
                   temp_to_display, temp_from_display)


# ======================================================================
# Palette & style
# ======================================================================
BG       = "#1a1e24"   # dark slate background
BG2      = "#252a33"   # panel background
BG3      = "#2e3440"   # card background
AMBER    = "#f0a500"   # primary accent
AMBER2   = "#c88a00"   # pressed accent
FG       = "#e8eaf0"   # primary text
FG2      = "#9ba3b0"   # secondary text
GREEN    = "#4caf78"   # success / normal values
RED      = "#e05c5c"   # error / off-chart
MONO     = ("Courier New", 10)
MONO_SM  = ("Courier New", 9)
SANS     = ("TkDefaultFont", 10)
TITLE    = ("TkDefaultFont", 11, "bold")

TTK_STYLE = {
    "TFrame":          {"background": BG2},
    "TLabel":          {"background": BG2, "foreground": FG, "font": SANS},
    "TEntry":          {"fieldbackground": BG3, "foreground": FG, "insertcolor": AMBER,
                        "bordercolor": "#444c5c", "lightcolor": "#444c5c",
                        "darkcolor":  "#444c5c"},
    "TButton":         {"background": BG3, "foreground": FG, "bordercolor": "#444c5c",
                        "font": SANS},
    "TCheckbutton":    {"background": BG2, "foreground": FG},
    "TCombobox":       {"fieldbackground": BG3, "foreground": FG, "selectbackground": AMBER},
    "TNotebook":       {"background": BG, "tabmargins": [2, 5, 2, 0]},
    "TNotebook.Tab":   {"background": BG3, "foreground": FG2, "padding": [14, 6],
                        "font": ("TkDefaultFont", 10)},
    "Treeview":        {"background": BG3, "foreground": FG, "fieldbackground": BG3,
                        "rowheight": 22, "font": MONO_SM},
    "Treeview.Heading":{"background": BG2, "foreground": AMBER, "font": MONO_SM},
    "Vertical.TScrollbar": {"background": BG3, "troughcolor": BG2},
}


def apply_style(root: tk.Tk) -> ttk.Style:
    style = ttk.Style(root)
    style.theme_use("clam")
    for widget, opts in TTK_STYLE.items():
        style.configure(widget, **opts)
    style.map("TNotebook.Tab",
              background=[("selected", BG2)],
              foreground=[("selected", AMBER)])
    style.map("TButton",
              background=[("active", BG), ("pressed", AMBER2)],
              foreground=[("active", AMBER)])
    style.map("Treeview",
              background=[("selected", AMBER2)],
              foreground=[("selected", BG)])
    # Real-time validation styles
    style.configure("Error.TEntry",
                    fieldbackground="#3a1212", foreground="#ff8a8a",
                    insertcolor="#ff8a8a")
    return style


# ======================================================================
# Helpers
# ======================================================================

def _lf(parent, label: str, row: int, col: int = 0,
         width: int = 22, unit: str = "") -> ttk.Entry:
    """Label + Entry in a grid. Returns the Entry widget."""
    ttk.Label(parent, text=label, anchor="e", width=width).grid(
        row=row, column=col, padx=(8, 4), pady=3, sticky="e")
    e = ttk.Entry(parent, width=12)
    e.grid(row=row, column=col+1, padx=(0, 4), pady=3, sticky="w")
    if unit:
        ttk.Label(parent, text=unit, foreground=FG2, width=8).grid(
            row=row, column=col+2, padx=0, pady=3, sticky="w")
    return e


def _set(entry: ttk.Entry, value) -> None:
    entry.delete(0, tk.END)
    if isinstance(value, float):
        # Round to 5 decimal places and remove trailing zeros / dot
        text = f"{value:.5f}".rstrip("0").rstrip(".")
    else:
        text = str(value)
    entry.insert(0, text)


def _get_float(entry: ttk.Entry, default: float = 0.0) -> float:
    try:
        return float(entry.get())
    except ValueError:
        return default


def _get_int(entry: ttk.Entry, default: int = 0) -> int:
    try:
        return int(float(entry.get()))
    except ValueError:
        return default


def _attach_validator(entry: ttk.Entry, ok_fn) -> None:
    """Attach real-time visual validation to *entry*.

    *ok_fn(str) -> bool*: return True when the value is acceptable.
    Any exception raised by ok_fn is treated as False (invalid).
    The entry background turns red while the value is invalid; it
    reverts to the normal style as soon as the value becomes valid.
    Validation fires on every keystroke (<KeyRelease>) and on focus loss.
    """
    def _check(*_):
        try:
            valid = bool(ok_fn(entry.get()))
        except Exception:
            valid = False
        entry.configure(style="Error.TEntry" if not valid else "TEntry")

    entry.bind("<KeyRelease>", _check)
    entry.bind("<FocusOut>",   _check)


# ======================================================================
# Tooltip
# ======================================================================

class _ToolTip:
    """Lightweight delayed tooltip for any tkinter widget.

    Usage::
        _ToolTip(widget, "Helpful description")
    """
    _PAD  = 8
    _DELAY = 550   # ms before the tip appears

    def __init__(self, widget: tk.Widget, text: str):
        self._w    = widget
        self._text = text
        self._job  = None
        self._win  = None
        widget.bind("<Enter>",       self._schedule, add="+")
        widget.bind("<Leave>",       self._cancel,   add="+")
        widget.bind("<ButtonPress>", self._cancel,   add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._job = self._w.after(self._DELAY, self._show)

    def _cancel(self, _=None):
        if self._job:
            self._w.after_cancel(self._job)
            self._job = None
        if self._win:
            self._win.destroy()
            self._win = None

    def _show(self):
        self._job = None
        x = self._w.winfo_rootx() + 10
        y = self._w.winfo_rooty() + self._w.winfo_height() + 6
        self._win = tw = tk.Toplevel(self._w)
        tw.wm_overrideredirect(True)          # no window decorations
        tw.wm_attributes("-topmost", True)
        tw.wm_geometry(f"+{x}+{y}")
        # Outer frame provides the border colour
        outer = tk.Frame(tw, bg="#4a5260", padx=1, pady=1)
        outer.pack()
        tk.Label(outer, text=self._text,
                 bg="#252a33", fg="#d8dce6",
                 font=("TkDefaultFont", 9),
                 padx=self._PAD, pady=4,
                 justify="left").pack()


# ======================================================================
# Geometry tab
# ======================================================================

class GeometryFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.configure(style="TFrame")
        self._us = UnitSystem.US
        self._build()

    def _build(self):
        # ── Project name bar ────────────────────────────────────────────
        name_bar = ttk.Frame(self, style="TFrame")
        name_bar.grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 4), sticky="ew")

        ttk.Label(name_bar, text="Project name", foreground=AMBER,
                  font=("TkDefaultFont", 10, "bold"), width=16,
                  anchor="e").pack(side="left", padx=(0, 8))
        self._name_entry = ttk.Entry(name_bar, width=40,
                                     font=("TkDefaultFont", 10))
        self._name_entry.pack(side="left")
        self._name_entry.insert(0, "Untitled")

        ttk.Separator(self, orient="horizontal").grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 4))

        # ── Two columns of grouped fields ───────────────────────────────
        left  = ttk.Frame(self, style="TFrame")
        right = ttk.Frame(self, style="TFrame")
        left.grid(row=2, column=0, padx=16, pady=4, sticky="n")
        right.grid(row=2, column=1, padx=16, pady=4, sticky="n")

        r = 0
        # ── Diameter sweep ──────────────────────────────────────────
        _sect(left, "Diameter sweep", r); r += 1
        # D and DD use StringVar so the unit label updates when units change
        self._d_unit_var  = tk.StringVar(value="ft")
        self._dd_unit_var = tk.StringVar(value="ft")
        ttk.Label(left, text="Starting diameter", anchor="e", width=22).grid(
            row=r, column=0, padx=(8, 4), pady=3, sticky="e")
        self.D = ttk.Entry(left, width=12)
        self.D.grid(row=r, column=1, padx=(0, 4), pady=3, sticky="w")
        ttk.Label(left, textvariable=self._d_unit_var, foreground=FG2, width=8).grid(
            row=r, column=2, padx=0, pady=3, sticky="w"); r += 1
        ttk.Label(left, text="Increment", anchor="e", width=22).grid(
            row=r, column=0, padx=(8, 4), pady=3, sticky="e")
        self.DD = ttk.Entry(left, width=12)
        self.DD.grid(row=r, column=1, padx=(0, 4), pady=3, sticky="w")
        ttk.Label(left, textvariable=self._dd_unit_var, foreground=FG2, width=8).grid(
            row=r, column=2, padx=0, pady=3, sticky="w"); r += 1
        self.ND   = _lf(left, "No. of steps",        r);               r += 1

        # ── Activity factor ─────────────────────────────────────────
        _sect(left, "Blade Activity Factor (BAF) sweep", r); r += 1
        self.AF   = _lf(left, "Starting BAF",        r);               r += 1
        _ToolTip(self.AF,
                 "Blade Activity Factor (BAF) — per individual blade, not per propeller.\n"
                 "TAF (total) = BAF × number of blades.\n\n"
                 "H432 chart range: 80 – 200\n"
                 "  80–100 : light GA propellers\n"
                 " 100–150 : general-purpose / turboprop\n"
                 " 150–200 : high-performance / wide-chord")
        self.DAF  = _lf(left, "Increment",           r);               r += 1
        self.NAF  = _lf(left, "No. of steps",        r);               r += 1

        # ── Blade count ─────────────────────────────────────────────
        _sect(left, "Blade count sweep", r); r += 1
        self.BLADN= _lf(left, "Starting blades",     r);               r += 1
        self.DBLAD= _lf(left, "Increment",           r);               r += 1
        self.NBL  = _lf(left, "No. of steps",        r);               r += 1

        r = 0
        # ── Integrated design CL ────────────────────────────────────
        _sect(right, "Integrated design CLi sweep", r); r += 1
        self.CLII = _lf(right, "Starting CLi",       r, unit="0.3–0.8"); r += 1
        self.DCLI = _lf(right, "Increment",          r);               r += 1
        self.ZNCLI= _lf(right, "No. of steps",       r);               r += 1

        # ── Design conditions ───────────────────────────────────────
        _sect(right, "Design conditions", r); r += 1
        self.ZMWT = _lf(right, "Design Mach no.",    r);               r += 1
        _ToolTip(self.ZMWT,
                 "Design cruise Mach number of the aircraft.\n\n"
                 "Used exclusively in the weight estimation formula (WAIT)\n"
                 "as a structural loading correction factor:\n"
                 "  ZK7 = √(M + 1)\n"
                 "A faster aircraft requires a more robust — heavier — propeller.\n\n"
                 "Why not derived from VKTAS?\n"
                 "• You may define several operating conditions (takeoff, climb,\n"
                 "  cruise…). Weight estimation needs a single design-cruise point.\n"
                 "• Mach ≠ KTAS: the same airspeed gives a different Mach number\n"
                 "  at different altitudes. Blade structural loading is a\n"
                 "  compressibility effect, so Mach is the correct parameter.\n\n"
                 "Has no effect on aerodynamic results (CT, CP, efficiency…).\n"
                 "Ignored when Category = 0 (weight/cost disabled).")
        self.XNOE = _lf(right, "No. of engines",     r);               r += 1
        _ToolTip(self.XNOE,
                 "Number of engines (propellers) on the aircraft.\n\n"
                 "All performance results (Thrust, SHP, Torque, Efficiency,\n"
                 "CT, CP, Weight, Cost) are computed for ONE propeller only.\n"
                 "BHP / Thrust inputs are per-engine values.\n\n"
                 "This parameter affects two outputs only:\n\n"
                 "• Noise (PNL) — sideline noise is a field measurement\n"
                 "  for the whole aircraft. More engines spread the acoustic\n"
                 "  energy, reducing the perceived noise level at the microphone.\n\n"
                 "• Cost — production quantity is multiplied by No. of engines\n"
                 "  (more propellers per airframe → higher production run\n"
                 "  → lower unit cost per propeller).\n\n"
                 "Has no effect on aerodynamic or weight results.")
        self.WTCON= _lf(right, "Category (1–5)",     r);               r += 1
        _ToolTip(self.WTCON,
                 "Aircraft classification (NASA CR-2066 / CR-114289 Table I):\n\n"
                 "1 — Single engine, fixed gear, fixed pitch\n"
                 "      e.g. Piper Cherokee\n"
                 "2 — Single engine, retractable gear, IFR, constant speed\n"
                 "      e.g. Cessna Centurion 210J\n"
                 "3 — Light twin, retractable gear, IFR,\n"
                 "      constant speed + full feather + de-icing\n"
                 "      e.g. Beechcraft Baron 55\n"
                 "4 — Medium twin, retractable gear, IFR,\n"
                 "      constant speed + full feather + de-icing\n"
                 "      e.g. Beechcraft Queen Air\n"
                 "5 — Heavy twin, retractable gear, IFR,\n"
                 "      constant speed + full feather + de-icing + reverse thrust\n"
                 "      e.g. De Havilland Twin Otter\n\n"
                 "Used for weight & cost estimation only (set 0 to skip).")

        # ── Cost / weight ───────────────────────────────────────────
        _sect(right, "Cost / learning curve", r); r += 1
        self.CLF1 = _lf(right, "LC factor 1 (0=def)",r);               r += 1
        self.CLF  = _lf(right, "LC factor 2 (0=def)",r);               r += 1
        self.CK70 = _lf(right, "1970 slope (0=auto)",r);               r += 1
        self.CK80 = _lf(right, "1980 slope (0=auto)",r);               r += 1
        self.CAMT = _lf(right, "Start qty (0=def)",  r);               r += 1
        self.DAMT = _lf(right, "Qty increment",      r);               r += 1
        self.NAMT = _lf(right, "Qty breakpoints",    r);               r += 1

        # ── Real-time validation ─────────────────────────────────────
        _v = _attach_validator   # shorthand
        # Diameter sweep
        _any_float = lambda s: float(s) == float(s)  # accepts any valid number incl. negative
        _v(self.D,     lambda s: float(s) > 0)
        _v(self.DD,    _any_float)                   # increment: negative or positive
        _v(self.ND,    lambda s: int(float(s)) >= 1)
        # Activity factor sweep (80–200)
        _v(self.AF,    lambda s: 80 <= float(s) <= 200)
        _v(self.DAF,   _any_float)                   # increment: negative or positive
        _v(self.NAF,   lambda s: int(float(s)) >= 1)
        # Blade count sweep (2–8)
        _v(self.BLADN, lambda s: 2 <= float(s) <= 8)
        _v(self.DBLAD, _any_float)                   # increment: negative or positive
        _v(self.NBL,   lambda s: int(float(s)) >= 1)
        # Integrated design CLi (0.3–0.8)
        _v(self.CLII,  lambda s: 0.3 <= float(s) <= 0.8)
        _v(self.DCLI,  _any_float)                   # increment: negative or positive
        _v(self.ZNCLI, lambda s: int(float(s)) >= 1)
        # Design conditions
        _v(self.ZMWT,  lambda s: 0 < float(s) < 1)      # design Mach number
        _v(self.XNOE,  lambda s: int(float(s)) >= 1)
        _v(self.WTCON, lambda s: 1 <= float(s) <= 5)
        # Cost / learning curve (0 = built-in default)
        _v(self.CLF1,  lambda s: float(s) >= 0)
        _v(self.CLF,   lambda s: float(s) >= 0)
        _v(self.CK70,  lambda s: float(s) >= 0)
        _v(self.CK80,  lambda s: float(s) >= 0)
        _v(self.CAMT,  lambda s: float(s) >= 0)
        _v(self.DAMT,  _any_float)                   # increment: negative or positive
        _v(self.NAMT,  lambda s: int(float(s)) >= 1)

        # ── Reverse thrust options ──────────────────────────────────
        _sect(right, "Reverse thrust options", r); r += 1
        self.RTC  = _lf(right, "RTC (1=cpt β,2=β in)",  r);           r += 1
        self.ROT  = _lf(right, "ROT (1=recip,2=turb)",   r);           r += 1
        # Reverse thrust flag values (1 or 2)
        _v(self.RTC,   lambda s: 1 <= float(s) <= 2)
        _v(self.ROT,   lambda s: 1 <= float(s) <= 2)

        self._defaults()

    def get_project_name(self) -> str:
        return self._name_entry.get().strip() or "Untitled"

    def set_project_name(self, name: str):
        self._name_entry.delete(0, tk.END)
        self._name_entry.insert(0, name)

    def _defaults(self):
        _set(self.D,     8.0);  _set(self.DD,    0.5);   _set(self.ND,    4)
        _set(self.AF,  100.0);  _set(self.DAF,   0.0);   _set(self.NAF,   1)
        _set(self.BLADN, 3.0);  _set(self.DBLAD, 0.0);   _set(self.NBL,   1)
        _set(self.CLII,  0.5);  _set(self.DCLI,  0.0);   _set(self.ZNCLI, 1)
        _set(self.ZMWT,  0.3);  _set(self.XNOE,  1.0);   _set(self.WTCON, 1.0)
        _set(self.CLF1,  0.0);  _set(self.CLF,   0.0)
        _set(self.CK70,  0.0);  _set(self.CK80,  0.0)
        _set(self.CAMT,  0.0);  _set(self.DAMT,500.0);  _set(self.NAMT,   1)
        _set(self.RTC,   1.0);  _set(self.ROT,   2.0)

    def get_geometry(self) -> PropellerGeometry:
        """Read entry fields and return a PropellerGeometry in US units."""
        d_val  = from_si(_get_float(self.D),  FT_TO_M, self._us)
        dd_val = from_si(_get_float(self.DD), FT_TO_M, self._us)
        return PropellerGeometry(
            D=d_val,  DD=dd_val,  ND=_get_int(self.ND),
            AF=_get_float(self.AF), DAF=_get_float(self.DAF), NAF=_get_int(self.NAF),
            BLADN=_get_float(self.BLADN), DBLAD=_get_float(self.DBLAD), NBL=_get_int(self.NBL),
            CLII=_get_float(self.CLII),  DCLI=_get_float(self.DCLI),  ZNCLI=_get_int(self.ZNCLI),
            ZMWT=_get_float(self.ZMWT), XNOE=_get_float(self.XNOE), WTCON=_get_float(self.WTCON),
            CLF1=_get_float(self.CLF1),  CLF=_get_float(self.CLF),
            CK70=_get_float(self.CK70),  CK80=_get_float(self.CK80),
            CAMT=_get_float(self.CAMT),  DAMT=_get_float(self.DAMT), NAMT=_get_int(self.NAMT),
            RTC=_get_float(self.RTC),    ROT=_get_float(self.ROT),
        )

    def set_geometry(self, g: PropellerGeometry):
        """Populate entry fields from a PropellerGeometry (stored in US units)."""
        _set(self.D,  to_si(g.D,  FT_TO_M, self._us))
        _set(self.DD, to_si(g.DD, FT_TO_M, self._us))
        _set(self.ND, g.ND)
        _set(self.AF, g.AF);     _set(self.DAF, g.DAF);   _set(self.NAF, g.NAF)
        _set(self.BLADN, g.BLADN);_set(self.DBLAD,g.DBLAD);_set(self.NBL,g.NBL)
        _set(self.CLII, g.CLII); _set(self.DCLI, g.DCLI); _set(self.ZNCLI, g.ZNCLI)
        _set(self.ZMWT, g.ZMWT); _set(self.XNOE, g.XNOE); _set(self.WTCON, g.WTCON)
        _set(self.CLF1, g.CLF1); _set(self.CLF, g.CLF)
        _set(self.CK70, g.CK70); _set(self.CK80, g.CK80)
        _set(self.CAMT, g.CAMT); _set(self.DAMT, g.DAMT); _set(self.NAMT, g.NAMT)
        _set(self.RTC,  g.RTC);  _set(self.ROT,  g.ROT)

    def set_unit_system(self, new_us: UnitSystem):
        """Switch unit display for diameter fields; convert current values."""
        if new_us == self._us:
            return
        # Convert the currently displayed D/DD to the new unit
        d_ft  = from_si(_get_float(self.D),  FT_TO_M, self._us)
        dd_ft = from_si(_get_float(self.DD), FT_TO_M, self._us)
        self._us = new_us
        _set(self.D,  to_si(d_ft,  FT_TO_M, self._us))
        _set(self.DD, to_si(dd_ft, FT_TO_M, self._us))
        lbl = unit_label("ft", "m", self._us)
        self._d_unit_var.set(lbl)
        self._dd_unit_var.set(lbl)


def _sect(parent, title: str, row: int):
    """Section separator label."""
    ttk.Label(parent, text=f"── {title} ──",
              foreground=AMBER, font=("TkDefaultFont", 9, "bold"),
              background=BG2).grid(
        row=row, column=0, columnspan=3, padx=8, pady=(10, 2), sticky="w")


# ======================================================================
# Condition editor dialog
# ======================================================================

class ConditionDialog(tk.Toplevel):
    """Modal dialog for adding or editing one OperatingCondition."""

    def __init__(self, parent, condition: Optional[OperatingCondition] = None,
                 unit_system: UnitSystem = UnitSystem.US):
        super().__init__(parent)
        self.title("Operating Condition")
        self.configure(bg=BG2)
        self.resizable(False, False)
        self.result: Optional[OperatingCondition] = None
        self._us = unit_system
        self._build(condition)
        self.grab_set()
        self.wait_window()

    def _build(self, cond):
        f = ttk.Frame(self);  f.pack(padx=16, pady=12, fill="both")
        us = self._us

        # Unit label strings that change with the selected unit system
        pwr_u  = unit_label("hp",   "kW",  us)
        thr_u  = unit_label("lbf",  "N",   us)
        alt_u  = unit_label("ft",   "m",   us)
        ts_u   = unit_label("ft/s", "m/s", us)
        dist_u = unit_label("ft",   "m",   us)
        temp_u = unit_label("°F",   "°C",  us)

        r = 0
        _sect(f, "Computation mode", r); r += 1
        ttk.Label(f, text="IW (1=HP, 2=Thrust, 3=Reverse)").grid(row=r, column=0, sticky="e", padx=4)
        self.IW = ttk.Combobox(f, values=["1 — Shaft horsepower",
                                           "2 — Thrust specified",
                                           "3 — Reverse thrust"], width=28)
        self.IW.grid(row=r, column=1, padx=4, pady=3, sticky="w"); r += 1

        _sect(f, "Power / thrust", r); r += 1
        # Dynamic label: "Shaft HP/kW" for IW=1/2, "Full-throttle SHP/kW" for IW=3
        self._bhp_label_var = tk.StringVar(value=f"Shaft {pwr_u} (IW=1,3)")
        self._bhp_pwr_u = pwr_u   # remember for _update_mode
        ttk.Label(f, textvariable=self._bhp_label_var, anchor="e", width=22).grid(
            row=r, column=0, padx=(8, 4), pady=3, sticky="e")
        self.BHP = ttk.Entry(f, width=12)
        self.BHP.grid(row=r, column=1, padx=(0, 4), pady=3, sticky="w")
        ttk.Label(f, text=pwr_u, foreground=FG2, width=8).grid(
            row=r, column=2, padx=0, pady=3, sticky="w")
        r += 1
        self.THRUST = _lf(f, "Thrust (IW=2)",       r, unit=thr_u); r += 1

        _sect(f, "Flight condition", r); r += 1
        self.ALT   = _lf(f, "Altitude",    r, unit=alt_u);  r += 1
        self.VKTAS = _lf(f, "Airspeed",    r, unit="KTAS"); r += 1
        self.T     = _lf(f, "Temp (0=ISA)", r, unit=temp_u); r += 1
        self.DT_ISA = _lf(f, "ISA offset", r, unit="°F"); r += 1
        _ToolTip(self.DT_ISA,
                 "ISA temperature deviation (°F).\n\n"
                 " +value → hot day (temperature above standard)\n"
                 " −value → cold day (temperature below standard)\n\n"
                 "Applied only when Temp = 0 (ISA standard day).\n"
                 "Ignored when a specific temperature is entered above.")

        _sect(f, "Tip-speed sweep", r); r += 1
        self.TS   = _lf(f, "Start tip speed", r, unit=ts_u); r += 1
        self.DTS  = _lf(f, "Increment",       r, unit=ts_u); r += 1
        self.NDTS = _lf(f, "Steps (1–10)",    r); r += 1

        _sect(f, "Options", r); r += 1
        self.DIST   = _lf(f, "Noise distance (0=skip)", r, unit=dist_u); r += 1
        self.STALIT = _lf(f, "Stall flag (>0.5=stall)", r); r += 1
        self.DCOST  = _lf(f, "Cost category (0=skip)",  r); r += 1

        _sect(f, "Reverse thrust (IW=3 only)", r); r += 1
        self.RPMC  = _lf(f, "Full-throttle RPM",     r, unit="RPM"); r += 1
        self.ANDVK = _lf(f, "Touch-down speed",      r, unit="kts"); r += 1
        self.PCPW  = _lf(f, "Power setting",         r, unit="%");   r += 1
        self.NPCPW = _lf(f, "No. of pwr steps",      r);              r += 1
        self.DPCPW = _lf(f, "Power increment",       r, unit="%");   r += 1
        self.BETA  = _lf(f, "Blade angle β (RTC=2)", r, unit="°");   r += 1

        # Bind mode toggle: IW selection and STALIT changes both affect enabled fields
        self.IW.bind("<<ComboboxSelected>>", self._update_mode)
        self.STALIT.bind("<FocusOut>", self._update_mode)
        self.STALIT.bind("<Return>",   self._update_mode)

        # ── Buttons ─────────────────────────────────────────────────
        bf = ttk.Frame(self); bf.pack(pady=8)
        ttk.Button(bf, text="  OK  ", command=self._ok).pack(side="left", padx=6)
        ttk.Button(bf, text="Cancel", command=self.destroy).pack(side="left", padx=6)

        # ── Pre-fill ─────────────────────────────────────────────────
        if cond:
            iw_map = {1: 0, 2: 1, 3: 2}
            self.IW.current(iw_map.get(cond.IW, 0))
            # Conditions are stored in US units; convert to display units
            _set(self.BHP,    to_si(cond.BHP,    HP_TO_KW,  us))
            _set(self.THRUST, to_si(cond.THRUST, LBF_TO_N,  us))
            _set(self.ALT,    to_si(cond.ALT,    FT_TO_M,   us))
            _set(self.VKTAS,  cond.VKTAS)   # always knots
            _set(self.T,      temp_to_display(cond.T, us))
            _set(self.DT_ISA, cond.DT_ISA)           # always °F (temperature difference)
            _set(self.TS,     to_si(cond.TS,  FPS_TO_MS, us))
            _set(self.DTS,    to_si(cond.DTS, FPS_TO_MS, us))
            _set(self.NDTS,   cond.NDTS)
            _set(self.DIST,   to_si(cond.DIST, FT_TO_M, us))
            _set(self.STALIT, cond.STALIT)
            _set(self.DCOST,  cond.DCOST)
            _set(self.RPMC,   cond.RPMC);    _set(self.ANDVK, cond.ANDVK)
            _set(self.PCPW,   cond.PCPW);    _set(self.NPCPW, cond.NPCPW)
            _set(self.DPCPW,  cond.DPCPW);   _set(self.BETA, cond.BETA)
        else:
            self.IW.current(0)
            # Default values — convert from US to display units
            _set(self.BHP,    to_si(300.0, HP_TO_KW,  us))
            _set(self.THRUST, to_si(0.0,   LBF_TO_N,  us))
            _set(self.ALT,    to_si(0.0,   FT_TO_M,   us))
            _set(self.VKTAS,  120.0); _set(self.T, 0.0)
            _set(self.TS,     to_si(800.0, FPS_TO_MS, us))
            _set(self.DTS,    to_si(50.0,  FPS_TO_MS, us)); _set(self.NDTS, 5)
            _set(self.DIST,   to_si(500.0, FT_TO_M,   us))
            _set(self.STALIT, 0.0);  _set(self.DCOST, 0.0)
            _set(self.RPMC,   0.0);  _set(self.ANDVK, 0.0)
            _set(self.PCPW,   100.0); _set(self.NPCPW, 1)
            _set(self.DPCPW,  0.0);  _set(self.BETA, 0.0)

        # ── Real-time validation ─────────────────────────────────────
        si  = (self._us == UnitSystem.SI)
        alt_max = 30_480.0 if si else 100_000.0  # ft or m
        _v  = _attach_validator
        # Any finite float (sign OK — e.g. temperature, blade angle)
        _any = lambda s: s.strip() != "" and float(s) == float(s)
        # Power / thrust
        _v(self.BHP,    lambda s: float(s) >= 0)
        _v(self.THRUST, lambda s: float(s) >= 0)
        # Flight condition
        _v(self.ALT,    lambda s: 0 <= float(s) <= alt_max)
        _v(self.VKTAS,  lambda s: float(s) >= 0)
        _v(self.T,      _any)                        # 0 = ISA; any °F/°C valid
        _v(self.DT_ISA, _any)                        # ISA offset: any °F valid
        # Tip-speed sweep
        _v(self.TS,     lambda s: float(s) > 0)
        _v(self.DTS,    _any)                        # increment: negative or positive
        _v(self.NDTS,   lambda s: 1 <= int(float(s)) <= 10)
        # Options
        _v(self.DIST,   lambda s: float(s) >= 0)
        _v(self.STALIT, lambda s: float(s) >= 0)
        _v(self.DCOST,  lambda s: float(s) >= 0)
        # Reverse-thrust fields
        _v(self.RPMC,   lambda s: float(s) >= 0)
        _v(self.ANDVK,  lambda s: float(s) >= 0)
        _v(self.PCPW,   lambda s: 0 <= float(s) <= 100)
        _v(self.NPCPW,  lambda s: int(float(s)) >= 1)
        _v(self.DPCPW,  _any)                        # increment: negative or positive
        _v(self.BETA,   _any)                        # any blade angle valid

        # Apply initial field-enable state based on IW and STALIT
        self._update_mode()

    def _update_mode(self, *_):
        """Enable/disable fields based on the selected IW mode and STALIT flag.

        - BHP label: "Full-throttle SHP" for IW=3, "Shaft HP (IW=1,3)" otherwise.
        - Reverse thrust fields (RPMC…BETA): enabled only for IW=3.
        - Tip-speed sweep fields (TS, DTS, NDTS): disabled for IW=3 or when
          STALIT > 0.5 (solver overrides them anyway in stall-iteration mode).
        """
        iw    = self.IW.current() + 1      # 1, 2, or 3
        stall = _get_float(self.STALIT) > 0.5
        rev   = (iw == 3)

        # Relabel BHP to make its role explicit for IW=3
        p = self._bhp_pwr_u
        self._bhp_label_var.set(
            f"Full-throttle S{p}" if rev else f"Shaft {p} (IW=1,3)")

        # Tip-speed fields: irrelevant for reverse thrust and for stall iteration
        if stall and not rev:
            _set(self.TS, 700.0); _set(self.DTS, 0.0); _set(self.NDTS, 1)
        for w in (self.TS, self.DTS, self.NDTS):
            w.configure(state="disabled" if (stall or rev) else "normal")

        # Reverse-thrust fields: only active when IW=3
        for w in (self.RPMC, self.ANDVK, self.PCPW, self.NPCPW, self.DPCPW, self.BETA):
            w.configure(state="normal" if rev else "disabled")

    def _ok(self):
        iw = self.IW.current() + 1
        us = self._us
        try:
            # Re-enable all potentially-disabled fields so _get_* can read them
            for w in (self.TS, self.DTS, self.NDTS,
                      self.RPMC, self.ANDVK, self.PCPW,
                      self.NPCPW, self.DPCPW, self.BETA):
                w.configure(state="normal")
            # Convert display values back to US customary before storing
            c = OperatingCondition(
                IW=iw,
                BHP=from_si(_get_float(self.BHP),    HP_TO_KW,  us),
                THRUST=from_si(_get_float(self.THRUST), LBF_TO_N, us),
                ALT=from_si(_get_float(self.ALT),    FT_TO_M,   us),
                VKTAS=_get_float(self.VKTAS),        # always knots
                T=temp_from_display(_get_float(self.T), us),
                DT_ISA=_get_float(self.DT_ISA),      # always °F (temperature difference)
                TS=from_si(_get_float(self.TS),   FPS_TO_MS, us),
                DTS=from_si(_get_float(self.DTS), FPS_TO_MS, us),
                NDTS=_get_int(self.NDTS),
                DIST=from_si(_get_float(self.DIST), FT_TO_M, us),
                STALIT=_get_float(self.STALIT),
                DCOST=_get_float(self.DCOST),
                RPMC=_get_float(self.RPMC),      ANDVK=_get_float(self.ANDVK),
                PCPW=_get_float(self.PCPW),      NPCPW=_get_int(self.NPCPW),
                DPCPW=_get_float(self.DPCPW),    BETA=_get_float(self.BETA),
            )
            c.validate()
            self.result = c
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Validation error", str(e), parent=self)


# ======================================================================
# Conditions tab
# ======================================================================

class ConditionsFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.conditions: List[OperatingCondition] = []
        self._us = UnitSystem.US
        self._build()

    def _build(self):
        # Listbox-style display — column IDs are fixed; headings update with units
        cols   = ("IC", "IW", "BHP/T", "Alt", "KTAS", "TS", "NDTS", "Dist", "Notes")
        widths = [35, 35, 80, 70, 60, 70, 50, 65, 120]
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")
        self._update_col_headings()
        self.tree.grid(row=0, column=0, columnspan=4, padx=10, pady=8, sticky="nsew")

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=4, pady=8, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)

        # Buttons
        ttk.Button(self, text="➕  Add",    command=self._add).grid(row=1, column=0, padx=6, pady=4)
        ttk.Button(self, text="✏  Edit",   command=self._edit).grid(row=1, column=1, padx=6, pady=4)
        ttk.Button(self, text="❌  Remove", command=self._remove).grid(row=1, column=2, padx=6, pady=4)
        ttk.Button(self, text="⬆⬇  Clone", command=self._clone).grid(row=1, column=3, padx=6, pady=4)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def _update_col_headings(self):
        alt_u  = unit_label("ft",   "m",   self._us)
        ts_u   = unit_label("fps",  "m/s", self._us)
        dist_u = unit_label("ft",   "m",   self._us)
        pwr_u  = unit_label("hp",   "kW",  self._us)
        thr_u  = unit_label("lbf",  "N",   self._us)
        self.tree.heading("Alt",  text=f"Alt {alt_u}")
        self.tree.heading("TS",   text=f"TS {ts_u}")
        self.tree.heading("Dist", text=f"Dist {dist_u}")
        self.tree.heading("BHP/T",text=f"{pwr_u}/{thr_u}")

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        us = self._us
        for i, c in enumerate(self.conditions, 1):
            iw_str  = {1:"HP", 2:"Thrust", 3:"Reverse"}.get(c.IW, "?")
            if c.IW != 2:
                bhp_disp = to_si(c.BHP, HP_TO_KW, us)
                pwr_u    = unit_label("hp", "kW", us)
                bhp_str  = f"{bhp_disp:.1f}{pwr_u}"
            else:
                thr_disp = to_si(c.THRUST, LBF_TO_N, us)
                thr_u    = unit_label("lbf", "N", us)
                bhp_str  = f"{thr_disp:.0f}{thr_u}"
            alt_disp  = to_si(c.ALT,  FT_TO_M,   us)
            ts_disp   = to_si(c.TS,   FPS_TO_MS, us)
            dist_disp = to_si(c.DIST, FT_TO_M,   us)
            notes   = []
            if c.DIST > 0:    notes.append("noise")
            if c.STALIT > 0.5:notes.append("stall-iter")
            if c.DCOST > 0:   notes.append("cost")
            self.tree.insert("", "end", iid=str(i), values=(
                i, iw_str, bhp_str,
                f"{alt_disp:.0f}", f"{c.VKTAS:.1f}", f"{ts_disp:.0f}",
                c.NDTS, f"{dist_disp:.0f}", ", ".join(notes)))

    def set_unit_system(self, new_us: UnitSystem):
        self._us = new_us
        self._update_col_headings()
        self._refresh()

    def _add(self):
        dlg = ConditionDialog(self, unit_system=self._us)
        if dlg.result:
            self.conditions.append(dlg.result)
            self._refresh()

    def _edit(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0]) - 1
        dlg = ConditionDialog(self, self.conditions[idx], unit_system=self._us)
        if dlg.result:
            self.conditions[idx] = dlg.result
            self._refresh()

    def _remove(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0]) - 1
        del self.conditions[idx]
        self._refresh()

    def _clone(self):
        sel = self.tree.selection()
        if not sel:
            return
        import copy
        idx = int(sel[0]) - 1
        self.conditions.append(copy.deepcopy(self.conditions[idx]))
        self._refresh()


# ======================================================================
# Results tab
# ======================================================================

RESULT_COLS = (
    "IC", "Blades", "BAF", "CLi", "Dia", "Vt",
    "J", "M", "Mt", "BldAng", "CP", "CT", "FT", "Eff%",
    "Thrust", "SHP", "Torque", "PNL",
    "Qty70", "Wt70", "Cost70", "Qty80", "Wt80", "Cost80",
    "Status",
)
RESULT_WIDTHS = (35, 48, 48, 48, 55, 62,
                 55, 62, 62, 62, 72, 72, 55, 55,
                 72, 66, 80, 60,
                 60, 60, 60, 60, 60, 60,
                 55)

# Column visibility groups  (core columns IC…Vt and Status are always visible)
RESULT_GROUPS = {
    "Aero coeff":  ("J", "M", "Mt", "BldAng", "CP", "CT", "FT", "Eff%"),
    "Performance": ("Thrust", "SHP", "Torque"),
    "Noise":       ("PNL",),
    "Cost 70":     ("Qty70", "Wt70", "Cost70"),
    "Cost 80":     ("Qty80", "Wt80", "Cost80"),
}


class ResultsFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._summary = None
        self._us = UnitSystem.US
        self._build()

    def _build(self):
        # ── Visibility bar ─────────────────────────────────────────────
        vis = tk.Frame(self, bg=BG2)
        vis.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 2))

        tk.Label(vis, text="Show:", bg=BG2, fg=FG2,
                 font=("TkDefaultFont", 9)).pack(side="left", padx=(4, 8))

        self._group_vars: dict[str, tk.BooleanVar] = {}
        for group_name in RESULT_GROUPS:
            var = tk.BooleanVar(value=True)
            self._group_vars[group_name] = var
            tk.Checkbutton(vis, text=group_name, variable=var,
                           command=self._apply_visibility,
                           bg=BG2, fg=FG, selectcolor=BG3,
                           activebackground=BG2, activeforeground=AMBER,
                           font=("TkDefaultFont", 9),
                           bd=0, highlightthickness=0).pack(side="left", padx=6)

        # ── Treeview ───────────────────────────────────────────────────
        self.tree = ttk.Treeview(self, columns=RESULT_COLS,
                                  show="headings", height=20)
        for col, w in zip(RESULT_COLS, RESULT_WIDTHS):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, minwidth=w, anchor="center")
        self._update_headings()

        sb_v = ttk.Scrollbar(self, orient="vertical",   command=self.tree.yview)
        sb_h = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        self.tree.grid(row=1, column=0, sticky="nsew")
        sb_v.grid(row=1, column=1, sticky="ns")
        sb_h.grid(row=2, column=0, sticky="ew")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Tags for off-chart rows
        self.tree.tag_configure("offchart", foreground=RED)
        self.tree.tag_configure("normal",   foreground=FG)

    def _apply_visibility(self):
        """Update displaycolumns based on the current checkbox state."""
        hidden: set[str] = set()
        for group_name, cols in RESULT_GROUPS.items():
            if not self._group_vars[group_name].get():
                hidden.update(cols)
        self.tree["displaycolumns"] = [c for c in RESULT_COLS if c not in hidden]

    def _update_headings(self):
        """Update column headings to show the active unit labels."""
        si = self._us == UnitSystem.SI
        overrides = {
            "Dia":    "Dia(m)"       if si else "Dia(ft)",
            "Vt":     "Vt(m/s)"     if si else "Vt(fps)",
            "Thrust": "Thr(N)"      if si else "Thr(lbf)",
            "SHP":    "SHP(kW)"     if si else "SHP(hp)",
            "Torque": "Torque(N·m)" if si else "Torque(ft·lbf)",
            "Wt70":   "Wt70(kg)"    if si else "Wt70(lb)",
            "Wt80":   "Wt80(kg)"    if si else "Wt80(lb)",
        }
        for col in RESULT_COLS:
            self.tree.heading(col, text=overrides.get(col, col))

    def set_unit_system(self, new_us: UnitSystem):
        self._us = new_us
        self._update_headings()
        if self._summary is not None:
            self.populate(self._summary)

    def populate(self, summary):
        self._summary = summary
        us = self._us
        self.tree.delete(*self.tree.get_children())
        for r in summary.rows:
            tag    = "offchart" if r.off_chart else "normal"
            pnl    = f"{r.pnl_db:.1f}" if r.pnl_db else "—"
            status = "OFF-CHART" if r.off_chart else "OK"

            # Convert dimensional values for display
            dia    = to_si(r.dia_ft,     FT_TO_M,     us)
            vt     = to_si(r.tipspd_fps, FPS_TO_MS,   us)
            thrust = to_si(r.thrust_lb,  LBF_TO_N,    us)
            shp    = to_si(r.shp,        HP_TO_KW,    us)
            torque = to_si(r.torque,     FTLBF_TO_NM, us)
            wt70   = to_si(r.wt70_lb,    LB_TO_KG,    us)
            wt80   = to_si(r.wt80_lb,    LB_TO_KG,    us)

            # One table row per quantity breakpoint (matches Fortran FORMAT 575/587).
            # If there are no cost data, emit a single row with "—" for cost columns.
            n_qty = max(len(r.qty70), len(r.qty80), 1)
            for qi in range(n_qty):
                qty70_str  = f"{r.qty70[qi]:.0f}"      if qi < len(r.qty70)      else "—"
                qty80_str  = f"{r.qty80[qi]:.0f}"      if qi < len(r.qty80)      else "—"
                cost70_str = f"{r.cost70_qty[qi]:.0f}" if qi < len(r.cost70_qty) else "—"
                cost80_str = f"{r.cost80_qty[qi]:.0f}" if qi < len(r.cost80_qty) else "—"

                if qi == 0:
                    # First qty level: show all performance + cost fields
                    eff = f"{r.eta*100:.2f}" if r.eta > 0.0 else "—"
                    self.tree.insert("", "end", tags=(tag,), values=(
                        r.condition, f"{r.blades:.0f}", f"{r.af:.0f}", f"{r.cli:.3f}",
                        f"{dia:.2f}", f"{vt:.1f}",
                        f"{r.j:.4f}", f"{r.mach_fs:.4f}", f"{r.mach_tip:.4f}",
                        f"{r.blade_ang:.2f}",
                        f"{r.cp:.5f}", f"{r.ct:.5f}", f"{r.ft:.4f}", eff,
                        f"{thrust:.0f}", f"{shp:.1f}", f"{torque:.1f}", pnl,
                        qty70_str, f"{wt70:.1f}", cost70_str,
                        qty80_str, f"{wt80:.1f}", cost80_str,
                        status,
                    ))
                else:
                    # Subsequent qty levels: blank performance columns, show wt
                    self.tree.insert("", "end", tags=(tag,), values=(
                        "", "", "", "",
                        "", "",
                        "", "", "", "",
                        "", "", "", "",
                        "", "", "", "",
                        qty70_str, f"{wt70:.1f}", cost70_str,
                        qty80_str, f"{wt80:.1f}", cost80_str,
                        "",
                    ))

    def clear(self):
        self._summary = None
        self.tree.delete(*self.tree.get_children())


# ======================================================================
# Reverse-thrust results tab  (IW=3)
# ======================================================================

REV_COLS   = ("IC", "BL", "BAF", "CLi", "Dia", "PCPW%", "Theta", "VK", "Thrust", "SHP", "Torque", "RPM")
REV_WIDTHS = (  40,   40,   50,    50,    55,      55,     60,    60,      72,     65,       80,    65)


class RevThrustFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._us = UnitSystem.US
        self._rev_rows: list = []
        self._build()

    def _build(self):
        self.tree = ttk.Treeview(self, columns=REV_COLS, show="headings", height=20)
        for col, w in zip(REV_COLS, REV_WIDTHS):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")
        self._update_headings()

        sb_v = ttk.Scrollbar(self, orient="vertical",   command=self.tree.yview)
        sb_h = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb_v.grid(row=0, column=1, sticky="ns")
        sb_h.grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.tree.tag_configure("a", foreground=FG)
        self.tree.tag_configure("b", foreground=FG2)

    def _update_headings(self):
        si = self._us == UnitSystem.SI
        overrides = {
            "Dia":    f"Dia({'m' if si else 'ft'})",
            "Thrust": f"Thrust({'N' if si else 'lbf'})",
            "SHP":    f"SHP({'kW' if si else 'hp'})",
            "Torque": f"Torque({'N·m' if si else 'ft·lbf'})",
            "VK":     "VK(kts)",
            "PCPW%":  "PCPW%",
            "Theta":  "Theta(°)",
            "RPM":    "RPM",
        }
        for col in REV_COLS:
            self.tree.heading(col, text=overrides.get(col, col))

    def set_unit_system(self, new_us: UnitSystem):
        self._us = new_us
        self._update_headings()
        if self._rev_rows:
            self.populate(self._rev_rows)

    def populate(self, rev_rows):
        self._rev_rows = rev_rows
        us = self._us
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rev_rows):
            tag = "a" if i % 2 == 0 else "b"
            dia    = to_si(r.dia_ft,    FT_TO_M,     us)
            thrust = to_si(r.thrust_lb, LBF_TO_N,    us)
            shp    = to_si(r.shp,       HP_TO_KW,    us)
            torque = to_si(r.torque,    FTLBF_TO_NM, us)
            self.tree.insert("", "end", tags=(tag,), values=(
                r.condition,
                f"{r.blades:.0f}",
                f"{r.af:.0f}",
                f"{r.cli:.3f}",
                f"{dia:.2f}",
                f"{r.pcpw:.0f}",
                f"{r.theta_deg:.1f}",
                f"{r.vk_kts:.1f}",
                f"{thrust:.0f}",
                f"{shp:.1f}",
                f"{torque:.1f}",
                f"{r.rpm:.0f}",
            ))

    def clear(self):
        self._rev_rows = []
        self.tree.delete(*self.tree.get_children())


# ======================================================================
# Log tab
# ======================================================================

class LogFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.text = tk.Text(self, bg=BG3, fg=FG2, font=MONO_SM,
                            insertbackground=AMBER,
                            selectbackground=AMBER2,
                            state="disabled", wrap="none")
        sb_v = ttk.Scrollbar(self, orient="vertical",   command=self.text.yview)
        sb_h = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        sb_v.grid(row=0, column=1, sticky="ns")
        sb_h.grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def append(self, text: str):
        self.text.configure(state="normal")
        self.text.insert("end", text + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


# ======================================================================
# Plot tab
# ======================================================================

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    _MPL_OK = True
except ImportError:
    _MPL_OK = False

# Dark-theme colours for matplotlib
_MPL_BG   = "#1e2229"   # axes background
_MPL_FG   = "#c8cdd6"   # text / ticks
_MPL_GRID = "#2e3440"   # grid lines
_MPL_PALETTE = [
    "#f0a500", "#4caf78", "#5b9bd5", "#e05c5c",
    "#a078c8", "#f08050", "#50c8c8", "#c8c850",
]


class PlotFrame(ttk.Frame):
    """📈 Plot tab — embeds a matplotlib figure with selectable curve type."""

    # (label, x_field, y_field, x_label, y_label, source)
    #   source = "rows" | "rev_rows"
    CURVES = [
        ("η vs J  (Efficiency)",          "j",          "eta",       "Advance ratio J",    "Efficiency η",      "rows"),
        ("CT vs J  (Thrust coeff.)",       "j",          "ct",        "Advance ratio J",    "CT",                "rows"),
        ("CP vs J  (Power coeff.)",        "j",          "cp",        "Advance ratio J",    "CP",                "rows"),
        ("Thrust vs Diameter",             "dia_ft",     "thrust_lb", "Diameter (ft)",      "Thrust (lbf)",      "rows"),
        ("SHP vs Tip Speed",               "tipspd_fps", "shp",       "Tip speed (ft/s)",   "SHP",               "rows"),
        ("SHP vs Diameter",                "dia_ft",     "shp",       "Diameter (ft)",      "SHP",               "rows"),
        ("Weight (70) vs Diameter",        "dia_ft",     "wt70_lb",   "Diameter (ft)",      "Weight 70 (lb)",    "rows"),
        ("Weight (80) vs Diameter",        "dia_ft",     "wt80_lb",   "Diameter (ft)",      "Weight 80 (lb)",    "rows"),
        ("Rev Thrust vs Airspeed",         "vk_kts",     "thrust_lb", "Airspeed (kts)",     "Rev Thrust (lbf)",  "rev_rows"),
    ]
    # SI overrides for axis labels when unit system is SI
    _SI_LABELS = {
        "Diameter (ft)":    "Diameter (m)",
        "Thrust (lbf)":     "Thrust (N)",
        "Rev Thrust (lbf)": "Rev Thrust (N)",
        "Tip speed (ft/s)": "Tip speed (m/s)",
        "SHP":              "Power (kW)",
        "Weight 70 (lb)":   "Weight 70 (kg)",
        "Weight 80 (lb)":   "Weight 80 (kg)",
    }

    def __init__(self, parent):
        super().__init__(parent)
        self._summary = None
        self._us = UnitSystem.US
        self._build()

    def _build(self):
        if not _MPL_OK:
            ttk.Label(self, text="matplotlib not installed — run:  pip install matplotlib",
                      foreground=RED).pack(pady=40)
            return

        # ── Controls bar ───────────────────────────────────────────────
        ctrl = ttk.Frame(self)
        ctrl.pack(fill="x", padx=8, pady=(6, 0))

        ttk.Label(ctrl, text="Plot:").pack(side="left", padx=(0, 6))
        self._curve_var = tk.StringVar(value=self.CURVES[0][0])
        cb = ttk.Combobox(ctrl, textvariable=self._curve_var, state="readonly",
                          values=[c[0] for c in self.CURVES], width=34)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _: self._redraw())

        self._group_var = tk.StringVar(value="condition")
        ttk.Label(ctrl, text="   Group by:").pack(side="left", padx=(18, 4))
        for val, lbl in (("condition", "Condition"), ("blades", "# Blades"),
                         ("af", "BAF"), ("cli", "CLi")):
            ttk.Radiobutton(ctrl, text=lbl, variable=self._group_var,
                            value=val, command=self._redraw).pack(side="left", padx=2)

        # ── Figure ─────────────────────────────────────────────────────
        self._fig = Figure(figsize=(8, 4.5), dpi=96, facecolor=_MPL_BG)
        self._ax  = self._fig.add_subplot(111)
        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
        self._style_axes()

    def _style_axes(self):
        ax = self._ax
        ax.set_facecolor(_MPL_BG)
        for spine in ax.spines.values():
            spine.set_edgecolor(_MPL_GRID)
        ax.tick_params(colors=_MPL_FG, which="both")
        ax.xaxis.label.set_color(_MPL_FG)
        ax.yaxis.label.set_color(_MPL_FG)
        ax.title.set_color(_MPL_FG)
        ax.grid(True, color=_MPL_GRID, linewidth=0.6, linestyle="--")
        self._fig.tight_layout(pad=1.4)

    def populate(self, summary):
        """Called from _show_results() after a run."""
        self._summary = summary
        self._redraw()

    def set_unit_system(self, us: UnitSystem):
        self._us = us
        self._redraw()

    def clear(self):
        self._summary = None
        if not _MPL_OK:
            return
        self._ax.clear()
        self._style_axes()
        self._canvas.draw()

    def _redraw(self):
        if not _MPL_OK or self._summary is None:
            return

        curve_name = self._curve_var.get()
        curve = next((c for c in self.CURVES if c[0] == curve_name), self.CURVES[0])
        _, x_field, y_field, x_lbl, y_lbl, source = curve
        group_by = self._group_var.get()

        rows = (self._summary.rows if source == "rows"
                else self._summary.rev_rows)
        if not rows:
            self._ax.clear()
            self._style_axes()
            self._ax.set_title("No data", color=_MPL_FG)
            self._canvas.draw()
            return

        si = (self._us == UnitSystem.SI)

        # ── Conversion lambdas ──────────────────────────────────────
        def convert_x(v):
            if x_field == "dia_ft":      return v * FT_TO_M if si else v
            if x_field == "tipspd_fps":  return v * FPS_TO_MS if si else v
            return v

        def convert_y(v):
            if y_field == "thrust_lb":   return v * LBF_TO_N if si else v
            if y_field == "shp":         return v * HP_TO_KW if si else v
            if y_field in ("wt70_lb", "wt80_lb"):
                                         return v * LB_TO_KG if si else v
            return v

        x_lbl_disp = self._SI_LABELS.get(x_lbl, x_lbl) if si else x_lbl
        y_lbl_disp = self._SI_LABELS.get(y_lbl, y_lbl) if si else y_lbl

        # ── Group rows ──────────────────────────────────────────────
        groups: dict = {}
        for r in rows:
            key = getattr(r, group_by, 0)
            groups.setdefault(key, []).append(r)

        # ── Draw ────────────────────────────────────────────────────
        self._ax.clear()
        for i, (key, grp) in enumerate(sorted(groups.items())):
            xs = [convert_x(getattr(r, x_field, 0.0)) for r in grp]
            ys = [convert_y(getattr(r, y_field, 0.0)) for r in grp]
            color = _MPL_PALETTE[i % len(_MPL_PALETTE)]
            label = f"{group_by}={key}"
            self._ax.plot(xs, ys, "o-", color=color, label=label,
                          linewidth=1.5, markersize=4)

        self._ax.set_xlabel(x_lbl_disp)
        self._ax.set_ylabel(y_lbl_disp)
        self._ax.set_title(curve_name, pad=8)
        if len(groups) > 1:
            self._ax.legend(fontsize=8, facecolor=_MPL_BG,
                            edgecolor=_MPL_GRID, labelcolor=_MPL_FG)
        self._style_axes()
        self._canvas.draw()


# ======================================================================
# Map tab
# ======================================================================

class MapFrame(ttk.Frame):
    """🗺 Map tab — propeller characteristic map (CP, CT, η vs J)."""

    _PLOTS  = [("η vs J", "eta"), ("CT vs J", "ct"),
               ("CP vs J", "cp"), ("All",     "all")]
    _GROUPS = [("blades", "Blades"), ("af", "BAF"),
               ("cli", "CLi"), ("dia_ft", "Dia"), ("vt_fps", "Vt")]

    def __init__(self, parent, get_conditions, get_geometry):
        super().__init__(parent)
        self._get_conditions = get_conditions
        self._get_geometry   = get_geometry
        self._map_result     = None
        self._us             = UnitSystem.US
        self._build()

    def _build(self):
        if not _MPL_OK:
            ttk.Label(self,
                      text="matplotlib not installed — run:  pip install matplotlib",
                      foreground=RED).pack(pady=40)
            return

        # ── Controls bar ─────────────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG3)
        ctrl.pack(fill="x", padx=6, pady=(6, 0))

        def _lbl(parent, text, **kw):
            return tk.Label(parent, text=text, bg=BG3, fg=FG2,
                            font=("TkDefaultFont", 9), **kw)

        def _ent(parent, default, width=5):
            e = ttk.Entry(parent, width=width)
            e.insert(0, default)
            return e

        # J sweep
        _lbl(ctrl, "J from").pack(side="left", padx=(4, 2))
        self._j_start = _ent(ctrl, "0.0", 5);  self._j_start.pack(side="left")
        _lbl(ctrl, "to").pack(side="left", padx=3)
        self._j_end   = _ent(ctrl, "1.4", 5);  self._j_end.pack(side="left")
        _lbl(ctrl, "in").pack(side="left", padx=3)
        self._nj      = _ent(ctrl, "30",  4);  self._nj.pack(side="left")
        _lbl(ctrl, "steps").pack(side="left", padx=(2, 10))

        # Condition selector
        _lbl(ctrl, "Condition:").pack(side="left", padx=(0, 4))
        self._ic_var   = tk.StringVar(value="IC 1")
        self._ic_combo = ttk.Combobox(ctrl, textvariable=self._ic_var,
                                      state="readonly", width=7)
        self._ic_combo["values"] = ["IC 1"]
        self._ic_combo.pack(side="left", padx=(0, 14))

        # Plot type radio buttons
        _lbl(ctrl, "Plot:").pack(side="left", padx=(0, 4))
        self._plot_var = tk.StringVar(value=self._PLOTS[0][0])
        for lbl, _ in self._PLOTS:
            ttk.Radiobutton(ctrl, text=lbl, variable=self._plot_var,
                            value=lbl, command=self._redraw).pack(side="left", padx=2)

        # Group-by radio buttons
        _lbl(ctrl, "   Group by:").pack(side="left", padx=(10, 4))
        self._group_var = tk.StringVar(value="blades")
        for val, lbl in self._GROUPS:
            ttk.Radiobutton(ctrl, text=lbl, variable=self._group_var,
                            value=val, command=self._redraw).pack(side="left", padx=2)

        # Action buttons
        def _btn(parent, text, cmd, fg=FG):
            b = tk.Button(parent, text=text, command=cmd,
                          bg=BG3, fg=fg, activebackground=AMBER2,
                          activeforeground=BG, relief="flat",
                          font=("TkDefaultFont", 10, "bold"),
                          padx=10, pady=4, cursor="hand2",
                          bd=0, highlightthickness=0)
            b.pack(side="left", padx=3)
            return b

        _lbl(ctrl, "  ").pack(side="left")
        _btn(ctrl, "▶  Run Map",   self._run_map,  AMBER)
        _btn(ctrl, "✕  Clear",     self.clear)
        _btn(ctrl, "📤  Export CSV", self._export)

        # ── Figure ───────────────────────────────────────────────────
        self._fig    = Figure(figsize=(8, 5.0), dpi=96, facecolor=_MPL_BG)
        self._axes   = []
        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
        self._init_axes(1)

    # ── Figure helpers ────────────────────────────────────────────────

    def _init_axes(self, n: int):
        """(Re)build n stacked subplots in the figure."""
        self._fig.clf()
        self._axes = []
        for i in range(n):
            ax = self._fig.add_subplot(n, 1, i + 1)
            ax.set_facecolor(_MPL_BG)
            for sp in ax.spines.values():
                sp.set_edgecolor(_MPL_GRID)
            ax.tick_params(colors=_MPL_FG, which="both")
            ax.xaxis.label.set_color(_MPL_FG)
            ax.yaxis.label.set_color(_MPL_FG)
            ax.title.set_color(_MPL_FG)
            ax.grid(True, color=_MPL_GRID, linewidth=0.6, linestyle="--")
            self._axes.append(ax)
        self._fig.tight_layout(pad=1.4)

    # ── Public API ────────────────────────────────────────────────────

    def refresh_conditions(self, conditions):
        """Rebuild the IC combobox whenever the conditions list changes."""
        vals = [f"IC {i + 1}" for i in range(len(conditions))]
        self._ic_combo["values"] = vals if vals else ["IC 1"]
        if vals and self._ic_var.get() not in vals:
            self._ic_var.set(vals[0])

    def set_unit_system(self, us: UnitSystem):
        self._us = us
        self._redraw()

    def clear(self):
        self._map_result = None
        if _MPL_OK:
            self._init_axes(1)
            self._canvas.draw()

    # ── Internal ──────────────────────────────────────────────────────

    def _get_ic(self) -> int:
        try:
            return int(self._ic_var.get().split()[-1]) - 1
        except (ValueError, IndexError):
            return 0

    def _run_map(self):
        import threading
        try:
            conditions = self._get_conditions()
            geometry   = self._get_geometry()
            geometry.validate()
        except Exception as e:
            messagebox.showerror("Map Error", str(e), parent=self)
            return
        # Keep combobox in sync with current condition list
        self.refresh_conditions(conditions)
        if not conditions:
            messagebox.showwarning("Map", "Add at least one operating condition.", parent=self)
            return

        ic = min(self._get_ic(), len(conditions) - 1)
        if conditions[ic].IW == 3:
            messagebox.showwarning("Map",
                                   "Propeller map is not available for reverse-thrust "
                                   "conditions (IW=3).\nSelect a different condition.",
                                   parent=self)
            return

        try:
            j_start = float(self._j_start.get())
            j_end   = float(self._j_end.get())
            nj      = int(float(self._nj.get()))
        except ValueError:
            messagebox.showerror("Map Error", "Invalid J sweep parameters.", parent=self)
            return
        if nj < 2:
            messagebox.showerror("Map Error", "N steps must be ≥ 2.", parent=self)
            return
        if j_end <= j_start:
            messagebox.showerror("Map Error", "J end must be > J start.", parent=self)
            return

        def _worker():
            import MAIN
            try:
                res = MAIN.run_map(conditions, geometry,
                                   ic_index=ic,
                                   j_start=j_start, j_end=j_end, nj=nj)
                self.after(0, lambda: self._on_done(res))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror(
                    "Map Error", str(e), parent=self))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_done(self, result):
        self._map_result = result
        self._redraw()

    def _redraw(self):
        if not _MPL_OK or self._map_result is None:
            return
        curves = [c for c in self._map_result.curves
                  if any(not p.off_chart for p in c.points)]
        if not curves:
            self._init_axes(1)
            self._axes[0].set_title("No valid data", color=_MPL_FG)
            self._canvas.draw()
            return

        plot_name  = self._plot_var.get()
        group_field = self._group_var.get()
        all_mode   = (plot_name == "All")

        # Build groups
        groups: dict = {}
        for c in curves:
            key = getattr(c, group_field, "?")
            groups.setdefault(key, []).append(c)

        # Subplot layout
        specs = ([("η vs J", "eta"), ("CT vs J", "ct"), ("CP vs J", "cp")]
                 if all_mode else
                 [next(s for s in self._PLOTS if s[0] == plot_name)])
        self._init_axes(len(specs))

        for ax_idx, (title, field) in enumerate(specs):
            ax = self._axes[ax_idx]
            for i, (key, grp) in enumerate(sorted(groups.items())):
                color = _MPL_PALETTE[i % len(_MPL_PALETTE)]
                first = True
                for c in grp:
                    xs = [p.j for p in c.points if not p.off_chart]
                    ys = [getattr(p, field) for p in c.points if not p.off_chart]
                    if not xs:
                        continue
                    lbl = f"{group_field}={key}" if first else None
                    ax.plot(xs, ys, "o-", color=color, label=lbl,
                            linewidth=1.5, markersize=3)
                    first = False
            ax.set_xlabel("Advance ratio  J")
            if field == "eta":
                ax.set_ylabel("Efficiency  η")
            else:
                ax.set_ylabel(field.upper())
            ax.set_title(title, pad=6)
            if ax_idx == 0 and len(groups) > 1:
                ax.legend(fontsize=8, facecolor=_MPL_BG,
                          edgecolor=_MPL_GRID, labelcolor=_MPL_FG)

        self._fig.tight_layout(pad=1.4)
        self._canvas.draw()

    def _export(self):
        if self._map_result is None or not self._map_result.curves:
            messagebox.showwarning("Export", "No map data to export.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="Export Map CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            parent=self)
        if not path:
            return
        try:
            Path(path).write_text(self._map_result.as_csv(), encoding="utf-8")
        except Exception as e:
            messagebox.showerror("Export Error", str(e), parent=self)


# ======================================================================
# Main application window
# ======================================================================

class PropellerHMI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hamilton Standard H432 — Propeller Design Tool")
        self.configure(bg=BG)
        self.geometry("1100x720")
        self.minsize(900, 600)

        apply_style(self)
        self._collector: Optional[ResultsCollector] = None
        self._last_summary = None
        self._us = UnitSystem.US            # active unit system
        self._current_project_path: Optional[Path] = None  # last saved/loaded .h432

        self._build_toolbar()
        self._build_notebook()
        self._build_statusbar()
        self._status("Ready.  Add operating conditions, then click  ▶ Run.")

    # ── Layout ─────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = tk.Frame(self, bg=BG3, height=46)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        def btn(text, cmd, fg=FG):
            b = tk.Button(tb, text=text, command=cmd,
                          bg=BG3, fg=fg, activebackground=AMBER2,
                          activeforeground=BG, relief="flat",
                          font=("TkDefaultFont", 10, "bold"),
                          padx=14, pady=6, cursor="hand2",
                          bd=0, highlightthickness=0)
            b.pack(side="left", padx=2, pady=4)
            return b

        self._btn_run  = btn("▶  Run",      self._run,         AMBER)
        _btn_save   = btn("💾  Save",     self._save_project)
        _btn_load   = btn("📂  Load",     self._load)
        _btn_export = btn("📤  Export",   self._export_results)
        _btn_clear  = btn("✕  Clear",    self._clear)

        # ── Tooltips ───────────────────────────────────────────────────
        _ToolTip(self._btn_run,
                 "Run the propeller computation\n"
                 "for all geometry / condition combinations.")
        _ToolTip(_btn_save,
                 "Save geometry and conditions to a .h432 project file.\n"
                 "A file-chooser dialog always appears so you can pick\n"
                 "the destination folder and filename.")
        _ToolTip(_btn_load,
                 "Load a previously saved .h432 project file.\n"
                 "Restores geometry, conditions and unit system.")
        _ToolTip(_btn_export,
                 "Export the last computation results to a file.\n"
                 "Supported formats: TXT (report), CSV, JSON.")
        _ToolTip(_btn_clear,
                 "Clear all results, plots and log output.\n"
                 "Geometry and conditions are not affected.")

        # ── Unit system toggle ─────────────────────────────────────────
        tk.Label(tb, text="Units:", bg=BG3, fg=FG2,
                 font=("TkDefaultFont", 9)).pack(side="left", padx=(18, 2))
        self._btn_us = tk.Button(tb, text="US",
                                  command=self._toggle_units,
                                  bg=AMBER2, fg=BG,
                                  activebackground=AMBER, activeforeground=BG,
                                  relief="flat",
                                  font=("TkDefaultFont", 9, "bold"),
                                  padx=10, pady=6, cursor="hand2",
                                  bd=0, highlightthickness=0, width=4)
        self._btn_us.pack(side="left", padx=2, pady=4)
        _ToolTip(self._btn_us,
                 "Toggle unit system.\n"
                 "US: ft, hp, lbf, ft/s, ft·lbf, lb\n"
                 "SI:  m, kW,  N, m/s,  N·m,  kg")

        # ── Right-side container: progress bar + branding ─────────────────
        right = tk.Frame(tb, bg=BG3)
        right.pack(side="right", padx=12)

        tk.Label(right, text="H432 · NASA CR-2066", bg=BG3, fg=FG2,
                 font=("TkDefaultFont", 9)).grid(row=0, column=1, padx=(12, 0))

        # Progress widgets — column 0, hidden until a run starts
        self._prog_frame = tk.Frame(right, bg=BG3)
        self._prog_frame.grid(row=0, column=0)
        self._prog_frame.grid_remove()   # hidden initially

        self._prog_bar = ttk.Progressbar(
            self._prog_frame, orient="horizontal", length=200, mode="determinate")
        self._prog_bar.pack(side="left", padx=(0, 6))

        self._prog_label = tk.Label(
            self._prog_frame, text="", bg=BG3, fg=FG2,
            font=("TkDefaultFont", 9), width=11, anchor="w")
        self._prog_label.pack(side="left")

    def _build_notebook(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=0, pady=0)

        self.tab_geom  = GeometryFrame(self.nb)
        self.tab_conds = ConditionsFrame(self.nb)
        self.tab_res   = ResultsFrame(self.nb)
        self.tab_rev   = RevThrustFrame(self.nb)
        self.tab_plot  = PlotFrame(self.nb)
        self.tab_map   = MapFrame(self.nb,
                                  get_conditions=lambda: self.tab_conds.conditions,
                                  get_geometry=lambda: self.tab_geom.get_geometry())
        self.tab_log   = LogFrame(self.nb)

        self.nb.add(self.tab_geom,  text="⚙  Geometry")
        self.nb.add(self.tab_conds, text="📋  Conditions")
        self.nb.add(self.tab_res,   text="📊  Results")
        self.nb.add(self.tab_rev,   text="🔁  Rev. Thrust")
        self.nb.add(self.tab_plot,  text="📈  Plot")
        self.nb.add(self.tab_map,   text="🗺  Map")
        self.nb.add(self.tab_log,   text="📝  Log")

    def _build_statusbar(self):
        self._status_var = tk.StringVar()
        sb = tk.Label(self, textvariable=self._status_var,
                      bg=BG, fg=FG2, anchor="w",
                      font=("TkDefaultFont", 9), padx=8)
        sb.pack(fill="x", side="bottom")

    def _status(self, msg: str):
        self._status_var.set(msg)
        self.update_idletasks()

    # ── Unit toggle ────────────────────────────────────────────────────

    def _toggle_units(self):
        """Switch between US and SI unit systems across all tabs."""
        self._us = UnitSystem.SI if self._us == UnitSystem.US else UnitSystem.US
        label = "SI" if self._us == UnitSystem.SI else "US"
        self._btn_us.configure(text=label)
        # Propagate to all components
        self.tab_geom.set_unit_system(self._us)
        self.tab_conds.set_unit_system(self._us)
        self.tab_res.set_unit_system(self._us)
        self.tab_rev.set_unit_system(self._us)
        self.tab_plot.set_unit_system(self._us)
        self.tab_map.set_unit_system(self._us)
        self._status(f"Unit system switched to {label}.")

    # ── Run ────────────────────────────────────────────────────────────

    def _run(self):
        conditions = self.tab_conds.conditions
        if not conditions:
            messagebox.showwarning("No conditions",
                                   "Add at least one Operating Condition first.")
            return

        try:
            geom = self.tab_geom.get_geometry()
            geom.validate()
        except ValueError as e:
            messagebox.showerror("Geometry error", str(e))
            return

        self._btn_run.configure(state="disabled", text="⏳  Running…")
        self._status("Running computation…")
        self.tab_log.clear()
        self.tab_res.clear()
        self.tab_rev.clear()

        # ── Progress bar setup ─────────────────────────────────────────────
        self._progress_count = 0
        self._progress_total = self._compute_total_points(conditions, geom)
        self._run_active     = True
        self._prog_bar.configure(maximum=self._progress_total, value=0)
        self._prog_label.configure(text=f"0 / {self._progress_total}")
        self._prog_frame.grid()          # show progress widgets
        self.after(120, self._poll_progress)

        def worker():
            try:
                self._run_computation(conditions, geom)
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda m=err_msg: self._run_error(m))
            finally:
                self.after(0, lambda: self._btn_run.configure(
                    state="normal", text="▶  Run"))

        threading.Thread(target=worker, daemon=True).start()

    def _run_computation(self, conditions, geom):
        """Runs in a background thread; posts results back to GUI thread."""
        from MAIN import call_input, main_loop

        collector = ResultsCollector()
        collector._tick_fn = self._progress_tick   # increment counter from bg thread

        state = call_input(conditions, geom)
        main_loop(state, collector=collector, unit_system=self._us.value)

        self._last_summary = collector.summary
        self._last_summary.nof         = len(conditions)
        self._last_summary.unit_system = self._us.value

        self.after(0, lambda: self._show_results(collector))

    def _show_results(self, collector: ResultsCollector):
        # Stop poll, do a final bar update, then hide after 2 s
        self._run_active = False
        n = self._progress_count
        self._prog_bar.configure(value=min(n, self._progress_total))
        self._prog_label.configure(text=f"{n} / {self._progress_total}")
        self.after(2000, self._hide_progress)

        self.tab_res._us = self._us   # ensure correct unit system before populate
        self.tab_rev._us = self._us
        self.tab_plot._us = self._us
        self.tab_res.populate(collector.summary)
        self.tab_rev.populate(collector.summary.rev_rows)
        self.tab_plot.populate(collector.summary)

        # Switch to the most relevant tab
        if collector.summary.rev_rows and not collector.summary.rows:
            self.nb.select(self.tab_rev)
        else:
            self.nb.select(self.tab_res)

        # Log captured messages
        for msg in collector.summary.messages:
            self.tab_log.append(msg)

        n_perf = len(collector.summary.rows)
        n_rev  = len(collector.summary.rev_rows)
        if n_rev and not n_perf:
            self._status(f"Completed — {n_rev} reverse-thrust row(s).  "
                         f"Use 📤 Export to save results.")
        else:
            self._status(f"Completed — {n_perf} result row(s).  "
                         f"Use 📤 Export to save results.")

    def _run_error(self, msg: str):
        self._run_active = False
        self._hide_progress()
        self.tab_log.append(f"ERROR: {msg}")
        self.nb.select(self.tab_log)
        self._status(f"Run failed — see Log tab.")
        messagebox.showerror("Run error", msg)

    # ── Progress helpers ───────────────────────────────────────────────

    @staticmethod
    def _compute_total_points(conditions, geom) -> int:
        """Estimate the total number of result rows for the progress bar."""
        total = 0
        for c in conditions:
            if int(c.IW) in (1, 2):
                total += (int(geom.NAF) * int(geom.ZNCLI) *
                          int(geom.NBL) * int(geom.ND) * int(c.NDTS))
            else:   # IW=3 reverse thrust: NAF × NBL × ND × NPCPW VK-table rows
                nount = int(c.ANDVK / 10.0) + 2   # rows per REVTHT call
                total += int(geom.NAF) * int(geom.NBL) * int(geom.ND) * int(c.NPCPW) * nount
        return max(total, 1)

    def _progress_tick(self) -> None:
        """Called from the background thread after each result row is emitted."""
        self._progress_count += 1   # GIL makes single-int increment safe

    def _poll_progress(self) -> None:
        """Periodic GUI-thread poll that updates the progress bar."""
        if not self._run_active:
            return
        n = self._progress_count
        total = self._progress_total
        self._prog_bar.configure(maximum=total, value=min(n, total))
        self._prog_label.configure(text=f"{n} / {total}")
        self.after(120, self._poll_progress)

    def _hide_progress(self) -> None:
        """Reset and hide the progress bar."""
        self._prog_bar.configure(value=0)
        self._prog_frame.grid_remove()

    # ── Save project (.h432) ───────────────────────────────────────────

    def _save_project(self):
        """Save geometry + conditions + unit system to a .h432 project file."""
        import dataclasses, datetime, re

        project_name = self.tab_geom.get_project_name()
        # Build a safe default filename from the project name
        safe = re.sub(r'[\\/:*?"<>|]+', "_", project_name).strip()
        initial_dir  = (str(self._current_project_path.parent)
                        if self._current_project_path else str(Path.home()))
        p = filedialog.asksaveasfilename(
            defaultextension=".h432",
            filetypes=[("H432 project", "*.h432")],
            initialdir=initial_dir,
            initialfile=safe,
            title="Save project")
        if not p:
            return
        path = Path(p)

        data = {
            "program":      "H432",
            "file_version": 1,
            "saved_at":     datetime.datetime.now().isoformat(timespec="seconds"),
            "unit_system":  self._us.value,
            "project_name": project_name,
            "geometry":     dataclasses.asdict(self.tab_geom.get_geometry()),
            "conditions":   [dataclasses.asdict(c)
                             for c in self.tab_conds.conditions],
        }
        path.write_text(json.dumps(data, indent=2))
        self._current_project_path = path
        self.title(f"H432 — {project_name}")
        self._status(f"Project saved → {path}")

    # ── Export results ─────────────────────────────────────────────────

    def _export_results(self):
        """Export last computation results to txt / csv / json."""
        if not self._last_summary:
            messagebox.showinfo("Nothing to export",
                                "Run the computation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text report", "*.txt"),
                       ("CSV",         "*.csv"),
                       ("JSON",        "*.json"),
                       ("All formats (stem)", "*")],
            title="Export results")
        if not path:
            return
        p = Path(path)
        writer = ReportWriter(self._last_summary)
        if p.suffix == ".csv":
            writer.save_csv(p)
        elif p.suffix == ".json":
            writer.save_json(p)
        else:
            saved = writer.save_all(p.with_suffix(""))
            self.tab_log.append(
                "Exported:\n" + "\n".join(f"  {v}" for v in saved.values()))
        self._status(f"Results exported → {p}")

    # ── Load project (.h432) ───────────────────────────────────────────

    def _load(self):
        path = filedialog.askopenfilename(
            filetypes=[("H432 project", "*.h432"),
                       ("JSON",         "*.json")],
            title="Load project")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text())
            # Restore geometry (always stored in US units)
            geom = PropellerGeometry(**data["geometry"])
            self.tab_geom.set_geometry(geom)
            # Restore conditions (always stored in US units)
            self.tab_conds.conditions = [
                OperatingCondition(**c) for c in data["conditions"]]
            self.tab_conds._refresh()
            self.tab_map.refresh_conditions(self.tab_conds.conditions)
            # Restore unit system
            us_str = data.get("unit_system", "US")
            new_us = UnitSystem(us_str)
            if new_us != self._us:
                self._us = new_us
                self._btn_us.config(text=self._us.value)
                self.tab_geom.set_unit_system(self._us)
                self.tab_conds.set_unit_system(self._us)
                self.tab_res.set_unit_system(self._us)
                self.tab_rev.set_unit_system(self._us)
            # Restore project name
            project_name = data.get("project_name", Path(path).stem)
            self.tab_geom.set_project_name(project_name)
            # Remember path and update title
            self._current_project_path = Path(path)
            self.title(f"H432 — {project_name}")
            self._status(f"Project loaded ← {path}")
        except Exception as e:
            messagebox.showerror("Load error", str(e))

    # ── Clear ──────────────────────────────────────────────────────────

    def _clear(self):
        if messagebox.askyesno("Clear", "Clear all results and log?"):
            self.tab_res.clear()
            self.tab_rev.clear()
            self.tab_plot.clear()
            self.tab_map.clear()
            self.tab_log.clear()
            self._last_summary = None
            self._status("Cleared.")


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    app = PropellerHMI()
    app.mainloop()
