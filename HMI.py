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
from output import ResultsCollector, ResultRow, ReportWriter


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
    entry.insert(0, str(value))


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


# ======================================================================
# Geometry tab
# ======================================================================

class GeometryFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.configure(style="TFrame")
        self._build()

    def _build(self):
        # Two columns of grouped fields
        left  = ttk.Frame(self, style="TFrame")
        right = ttk.Frame(self, style="TFrame")
        left.grid(row=0, column=0, padx=16, pady=12, sticky="n")
        right.grid(row=0, column=1, padx=16, pady=12, sticky="n")

        r = 0
        # ── Diameter sweep ──────────────────────────────────────────
        _sect(left, "Diameter sweep", r); r += 1
        self.D    = _lf(left, "Starting diameter",   r, unit="ft");    r += 1
        self.DD   = _lf(left, "Increment",           r, unit="ft");    r += 1
        self.ND   = _lf(left, "No. of steps",        r);               r += 1

        # ── Activity factor ─────────────────────────────────────────
        _sect(left, "Activity factor sweep", r); r += 1
        self.AF   = _lf(left, "Starting AF",         r);               r += 1
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
        self.XNOE = _lf(right, "No. of engines",     r);               r += 1
        self.WTCON= _lf(right, "Category (1–5)",     r);               r += 1

        # ── Cost / weight ───────────────────────────────────────────
        _sect(right, "Cost / learning curve", r); r += 1
        self.CLF1 = _lf(right, "LC factor 1 (0=def)",r);               r += 1
        self.CLF  = _lf(right, "LC factor 2 (0=def)",r);               r += 1
        self.CK70 = _lf(right, "1970 slope (0=auto)",r);               r += 1
        self.CK80 = _lf(right, "1980 slope (0=auto)",r);               r += 1
        self.CAMT = _lf(right, "Start qty (0=def)",  r);               r += 1
        self.DAMT = _lf(right, "Qty increment",      r);               r += 1
        self.NAMT = _lf(right, "Qty breakpoints",    r);               r += 1

        self._defaults()

    def _defaults(self):
        _set(self.D,     8.0);  _set(self.DD,    0.5);   _set(self.ND,    4)
        _set(self.AF,  100.0);  _set(self.DAF,   0.0);   _set(self.NAF,   1)
        _set(self.BLADN, 3.0);  _set(self.DBLAD, 0.0);   _set(self.NBL,   1)
        _set(self.CLII,  0.5);  _set(self.DCLI,  0.0);   _set(self.ZNCLI, 1)
        _set(self.ZMWT,  0.3);  _set(self.XNOE,  1.0);   _set(self.WTCON, 1.0)
        _set(self.CLF1,  0.0);  _set(self.CLF,   0.0)
        _set(self.CK70,  0.0);  _set(self.CK80,  0.0)
        _set(self.CAMT,  0.0);  _set(self.DAMT,500.0);  _set(self.NAMT,   1)

    def get_geometry(self) -> PropellerGeometry:
        return PropellerGeometry(
            D=_get_float(self.D),   DD=_get_float(self.DD),   ND=_get_int(self.ND),
            AF=_get_float(self.AF), DAF=_get_float(self.DAF), NAF=_get_int(self.NAF),
            BLADN=_get_float(self.BLADN), DBLAD=_get_float(self.DBLAD), NBL=_get_int(self.NBL),
            CLII=_get_float(self.CLII),  DCLI=_get_float(self.DCLI),  ZNCLI=_get_int(self.ZNCLI),
            ZMWT=_get_float(self.ZMWT), XNOE=_get_float(self.XNOE), WTCON=_get_float(self.WTCON),
            CLF1=_get_float(self.CLF1),  CLF=_get_float(self.CLF),
            CK70=_get_float(self.CK70),  CK80=_get_float(self.CK80),
            CAMT=_get_float(self.CAMT),  DAMT=_get_float(self.DAMT), NAMT=_get_int(self.NAMT),
        )

    def set_geometry(self, g: PropellerGeometry):
        _set(self.D, g.D);       _set(self.DD, g.DD);     _set(self.ND, g.ND)
        _set(self.AF, g.AF);     _set(self.DAF, g.DAF);   _set(self.NAF, g.NAF)
        _set(self.BLADN, g.BLADN);_set(self.DBLAD,g.DBLAD);_set(self.NBL,g.NBL)
        _set(self.CLII, g.CLII); _set(self.DCLI, g.DCLI); _set(self.ZNCLI, g.ZNCLI)
        _set(self.ZMWT, g.ZMWT); _set(self.XNOE, g.XNOE); _set(self.WTCON, g.WTCON)
        _set(self.CLF1, g.CLF1); _set(self.CLF, g.CLF)
        _set(self.CK70, g.CK70); _set(self.CK80, g.CK80)
        _set(self.CAMT, g.CAMT); _set(self.DAMT, g.DAMT); _set(self.NAMT, g.NAMT)


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

    def __init__(self, parent, condition: Optional[OperatingCondition] = None):
        super().__init__(parent)
        self.title("Operating Condition")
        self.configure(bg=BG2)
        self.resizable(False, False)
        self.result: Optional[OperatingCondition] = None
        self._build(condition)
        self.grab_set()
        self.wait_window()

    def _build(self, cond):
        f = ttk.Frame(self);  f.pack(padx=16, pady=12, fill="both")

        r = 0
        _sect(f, "Computation mode", r); r += 1
        ttk.Label(f, text="IW (1=HP, 2=Thrust, 3=Reverse)").grid(row=r, column=0, sticky="e", padx=4)
        self.IW = ttk.Combobox(f, values=["1 — Shaft horsepower",
                                           "2 — Thrust specified",
                                           "3 — Reverse thrust"], width=28)
        self.IW.grid(row=r, column=1, padx=4, pady=3, sticky="w"); r += 1

        _sect(f, "Power / thrust", r); r += 1
        self.BHP    = _lf(f, "Shaft HP (IW=1,3)",  r, unit="hp"); r += 1
        self.THRUST = _lf(f, "Thrust (IW=2)",       r, unit="lbf"); r += 1

        _sect(f, "Flight condition", r); r += 1
        self.ALT   = _lf(f, "Altitude",   r, unit="ft");  r += 1
        self.VKTAS = _lf(f, "Airspeed",   r, unit="KTAS"); r += 1
        self.T     = _lf(f, "Temp (0=ISA)",r, unit="°F"); r += 1

        _sect(f, "Tip-speed sweep", r); r += 1
        self.TS   = _lf(f, "Start tip speed", r, unit="ft/s"); r += 1
        self.DTS  = _lf(f, "Increment",       r, unit="ft/s"); r += 1
        self.NDTS = _lf(f, "Steps (1–10)",    r); r += 1

        _sect(f, "Options", r); r += 1
        self.DIST   = _lf(f, "Noise distance (0=skip)", r, unit="ft"); r += 1
        self.STALIT = _lf(f, "Stall flag (>0.5=stall)", r); r += 1
        self.DCOST  = _lf(f, "Cost category (0=skip)",  r); r += 1

        # ── Buttons ─────────────────────────────────────────────────
        bf = ttk.Frame(self); bf.pack(pady=8)
        ttk.Button(bf, text="  OK  ", command=self._ok).pack(side="left", padx=6)
        ttk.Button(bf, text="Cancel", command=self.destroy).pack(side="left", padx=6)

        # ── Pre-fill ─────────────────────────────────────────────────
        if cond:
            iw_map = {1: 0, 2: 1, 3: 2}
            self.IW.current(iw_map.get(cond.IW, 0))
            _set(self.BHP, cond.BHP);    _set(self.THRUST, cond.THRUST)
            _set(self.ALT, cond.ALT);    _set(self.VKTAS, cond.VKTAS)
            _set(self.T, cond.T)
            _set(self.TS, cond.TS);      _set(self.DTS, cond.DTS)
            _set(self.NDTS, cond.NDTS)
            _set(self.DIST, cond.DIST);  _set(self.STALIT, cond.STALIT)
            _set(self.DCOST, cond.DCOST)
        else:
            self.IW.current(0)
            _set(self.BHP, 300.0); _set(self.THRUST, 0.0)
            _set(self.ALT, 0.0);   _set(self.VKTAS, 120.0); _set(self.T, 0.0)
            _set(self.TS, 800.0);  _set(self.DTS, 50.0);    _set(self.NDTS, 5)
            _set(self.DIST, 500.0);_set(self.STALIT, 0.0);  _set(self.DCOST, 0.0)

    def _ok(self):
        iw = self.IW.current() + 1
        try:
            c = OperatingCondition(
                IW=iw,
                BHP=_get_float(self.BHP),       THRUST=_get_float(self.THRUST),
                ALT=_get_float(self.ALT),        VKTAS=_get_float(self.VKTAS),
                T=_get_float(self.T),
                TS=_get_float(self.TS),          DTS=_get_float(self.DTS),
                NDTS=_get_int(self.NDTS),
                DIST=_get_float(self.DIST),      STALIT=_get_float(self.STALIT),
                DCOST=_get_float(self.DCOST),
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
        self._build()

    def _build(self):
        # Listbox-style display
        cols = ("IC", "IW", "BHP/T", "Alt ft", "KTAS", "TS fps", "NDTS", "Dist ft", "Notes")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        widths    = [35, 35, 80, 70, 60, 70, 50, 65, 120]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")
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

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, c in enumerate(self.conditions, 1):
            iw_str  = {1:"HP", 2:"Thrust", 3:"Reverse"}.get(c.IW, "?")
            bhp_str = f"{c.BHP:.0f}hp" if c.IW != 2 else f"{c.THRUST:.0f}lbf"
            notes   = []
            if c.DIST > 0:    notes.append("noise")
            if c.STALIT > 0.5:notes.append("stall-iter")
            if c.DCOST > 0:   notes.append("cost")
            self.tree.insert("", "end", iid=str(i), values=(
                i, iw_str, bhp_str,
                f"{c.ALT:.0f}", f"{c.VKTAS:.1f}", f"{c.TS:.0f}",
                c.NDTS, f"{c.DIST:.0f}", ", ".join(notes)))

    def _add(self):
        dlg = ConditionDialog(self)
        if dlg.result:
            self.conditions.append(dlg.result)
            self._refresh()

    def _edit(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0]) - 1
        dlg = ConditionDialog(self, self.conditions[idx])
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
    "IC", "Blades", "AF", "CLi", "Dia", "Vt",
    "J", "M", "Mt", "BldAng", "CP", "CT", "FT",
    "Thrust", "SHP", "PNL",
    "Qty70", "Wt70", "Cost70", "Qty80", "Wt80", "Cost80",
    "Status",
)
RESULT_WIDTHS = (35, 48, 48, 48, 55, 62,
                 55, 62, 62, 62, 72, 72, 55,
                 72, 66, 60,
                 60, 60, 60, 60, 60, 60,
                 55)


class ResultsFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._summary = None
        self._build()

    def _build(self):
        # Treeview for result table
        self.tree = ttk.Treeview(self, columns=RESULT_COLS,
                                  show="headings", height=20)
        for col, w in zip(RESULT_COLS, RESULT_WIDTHS):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")

        sb_v = ttk.Scrollbar(self, orient="vertical",   command=self.tree.yview)
        sb_h = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        sb_v.grid(row=0, column=1, sticky="ns")
        sb_h.grid(row=1, column=0, sticky="ew")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Tags for off-chart rows
        self.tree.tag_configure("offchart", foreground=RED)
        self.tree.tag_configure("normal",   foreground=FG)

    def populate(self, summary):
        self._summary = summary
        self.tree.delete(*self.tree.get_children())
        for r in summary.rows:
            tag = "offchart" if r.off_chart else "normal"
            pnl = f"{r.pnl_db:.1f}" if r.pnl_db else "—"

            # Get first quantity level costs if available
            qty70_str = f"{r.qty70[0]:.0f}" if r.qty70 else "—"
            qty80_str = f"{r.qty80[0]:.0f}" if r.qty80 else "—"
            cost70_str = f"{r.cost70_qty[0]:.0f}" if r.cost70_qty else "—"
            cost80_str = f"{r.cost80_qty[0]:.0f}" if r.cost80_qty else "—"
            status = "OFF-CHART" if r.off_chart else "OK"

            self.tree.insert("", "end", tags=(tag,), values=(
                r.condition, f"{r.blades:.0f}", f"{r.af:.0f}", f"{r.cli:.3f}",
                f"{r.dia_ft:.2f}", f"{r.tipspd_fps:.0f}",
                f"{r.j:.4f}", f"{r.mach_fs:.4f}", f"{r.mach_tip:.4f}", f"{r.blade_ang:.2f}",
                f"{r.cp:.5f}", f"{r.ct:.5f}", f"{r.ft:.4f}",
                f"{r.thrust_lb:.0f}", f"{r.shp:.0f}", pnl,
                qty70_str, f"{r.wt70_lb:.1f}", cost70_str,
                qty80_str, f"{r.wt80_lb:.1f}", cost80_str,
                status,
            ))

    def clear(self):
        self._summary = None
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

        self._btn_run  = btn("▶  Run",      self._run,       AMBER)
        btn("💾  Save",     self._save)
        btn("📂  Load",     self._load)
        btn("✕  Clear",    self._clear)

        # Logo text on right
        tk.Label(tb, text="H432 · NASA CR-2066", bg=BG3, fg=FG2,
                 font=("TkDefaultFont", 9)).pack(side="right", padx=12)

    def _build_notebook(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=0, pady=0)

        self.tab_geom  = GeometryFrame(self.nb)
        self.tab_conds = ConditionsFrame(self.nb)
        self.tab_res   = ResultsFrame(self.nb)
        self.tab_log   = LogFrame(self.nb)

        self.nb.add(self.tab_geom,  text="⚙  Geometry")
        self.nb.add(self.tab_conds, text="📋  Conditions")
        self.nb.add(self.tab_res,   text="📊  Results")
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
        import MAIN as main_module
        from MAIN import state, main_loop, call_input

        collector = ResultsCollector()

        # Attach the collector so main_loop() fills it directly
        main_module._collector = collector

        try:
            with collector.capture_stdout():
                call_input(conditions, geom)
                main_loop()
        finally:
            # Always detach the collector, even if an exception occurred
            main_module._collector = None

        self._last_summary = collector.summary
        self._last_summary.nof = len(conditions)

        self.after(0, lambda: self._show_results(collector))

    def _show_results(self, collector: ResultsCollector):
        self.tab_res.populate(collector.summary)
        self.nb.select(self.tab_res)

        # Log captured messages
        for msg in collector.summary.messages:
            self.tab_log.append(msg)

        n = len(collector.summary.rows)
        self._status(f"Completed — {n} result row(s).  "
                     f"Use 💾 Save to export.")

    def _run_error(self, msg: str):
        self.tab_log.append(f"ERROR: {msg}")
        self.nb.select(self.tab_log)
        self._status(f"Run failed — see Log tab.")
        messagebox.showerror("Run error", msg)

    # ── Save ───────────────────────────────────────────────────────────

    def _save(self):
        if not self._last_summary:
            messagebox.showinfo("Nothing to save",
                                "Run the computation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text report", "*.txt"),
                       ("CSV",         "*.csv"),
                       ("JSON",        "*.json"),
                       ("All formats (stem)", "*")],
            title="Save results")
        if not path:
            return
        p = Path(path)
        writer = ReportWriter(self._last_summary)
        if p.suffix in (".csv",):
            writer.save_csv(p)
        elif p.suffix in (".json",):
            writer.save_json(p)
        else:
            # Save all three formats with the same stem
            saved = writer.save_all(p.with_suffix(""))
            self.tab_log.append(
                f"Saved:\n" + "\n".join(f"  {v}" for v in saved.values()))
        self._status(f"Results saved → {p}")

    # ── Load / Save session ────────────────────────────────────────────

    def _load(self):
        path = filedialog.askopenfilename(
            filetypes=[("H432 session", "*.h432"),
                       ("JSON",         "*.json")],
            title="Load session")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text())
            g = data["geometry"]
            geom = PropellerGeometry(**g)
            self.tab_geom.set_geometry(geom)
            self.tab_conds.conditions = [
                OperatingCondition(**c) for c in data["conditions"]]
            self.tab_conds._refresh()
            self._status(f"Session loaded from {path}")
        except Exception as e:
            messagebox.showerror("Load error", str(e))

    def _save_session(self):
        """Save current geometry + conditions as a JSON session file."""
        path = filedialog.asksaveasfilename(
            defaultextension=".h432",
            filetypes=[("H432 session", "*.h432")],
            title="Save session")
        if not path:
            return
        import dataclasses
        data = {
            "geometry":   dataclasses.asdict(self.tab_geom.get_geometry()),
            "conditions": [dataclasses.asdict(c)
                           for c in self.tab_conds.conditions],
        }
        Path(path).write_text(json.dumps(data, indent=2))
        self._status(f"Session saved → {path}")

    # ── Clear ──────────────────────────────────────────────────────────

    def _clear(self):
        if messagebox.askyesno("Clear", "Clear all results and log?"):
            self.tab_res.clear()
            self.tab_log.clear()
            self._last_summary = None
            self._status("Cleared.")


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    app = PropellerHMI()
    app.mainloop()
