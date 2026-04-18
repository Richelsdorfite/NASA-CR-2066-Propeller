#!/usr/bin/env python
"""
test_stall_cost.py
------------------
50% Stall Iteration with noise and cost over a range of production quantities.

Inputs
------
  Geometry:
    D=8 ft, DD=0, ND=1
    AF=200, DAF=0, NAF=1
    BLADN=6 blades, DBLAD=2, NBL=2  →  6 and 8 blades
    CLII=0.6, DCLI=0, ZNCLI=1
    Design Mach  = 0.327
    Nb engines   = 2
    A/C category = 4
    Qty start=1, increment=1000, steps=5

  Operating condition (IW=1, stall iteration):
    BHP    = 340 hp
    ALT    = 0 ft
    VKTAS  = 77.5 ktas
    T      = 0 (standard ISA atmosphere)
    STALIT = 1.0  →  50% stall tip-speed iteration
    DIST   = 500 ft (noise sideline)
    DCOST  = 4.0  →  cost calculation enabled, category 4
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from MAIN import call_input, main_loop
from output import ResultsCollector
from operating_condition import OperatingCondition, PropellerGeometry
import MAIN as main_module

# ── Geometry ──────────────────────────────────────────────────────────────────
geometry = PropellerGeometry(
    D=8.0,   DD=0.0,  ND=1,        # one diameter: 8 ft
    AF=200.0, DAF=0.0, NAF=1,      # activity factor: 200
    BLADN=4.0, DBLAD=2.0, NBL=2,  # blade counts: 4 and 6
    CLII=0.6,  DCLI=0.0, ZNCLI=1, # integrated design CL: 0.6
    ZMWT=0.327,                    # design flight Mach
    WTCON=4.0,                     # aircraft category 4
    XNOE=2.0,                      # 2 engines
    CAMT=1.0,                      # starting production quantity
    DAMT=1000.0,                   # quantity increment
    NAMT=5,                        # 5 quantity breakpoints → 1, 1001, 2001, 3001, 4001
)

# ── Operating condition ───────────────────────────────────────────────────────
condition = OperatingCondition(
    IW=1,           # shaft horsepower specified
    BHP=340.0,      # 340 shp
    ALT=0.0,        # sea level
    VKTAS=77.5,     # 77.5 knots true airspeed
    T=0.0,          # standard ISA temperature
    # Tip-speed sweep fields are ignored when STALIT > 0.5
    # (solver forces DTS=0, NTS=10, starts from 700 fps internally)
    TS=700.0, DTS=0.0, NDTS=1,
    DIST=500.0,     # noise sideline distance: 500 ft
    STALIT=1.0,     # 50% stall tip-speed iteration
    DCOST=1.0,      # 1 = enable cost calculation (aircraft category comes from WTCON=4 in geometry)
)

# ── Run ───────────────────────────────────────────────────────────────────────
print("=" * 72)
print("  50% STALL ITERATION + NOISE + COST")
print("  BHP=340  ALT=0  VKTAS=77.5 ktas  D=8 ft  AF=200  CLi=0.6")
print("  Blades: 4 and 6   |   A/C category 4   |   2 engines")
print("=" * 72)

collector = ResultsCollector()
main_module.set_collector(collector)
call_input([condition], geometry)

try:
    main_loop()
finally:
    main_module.set_collector(None)

rows = collector.summary.rows
if not rows:
    print("\nERROR: no results returned — check inputs or solver log.")
    sys.exit(1)

# ── Raw solver output ─────────────────────────────────────────────────────────
print("\n" + "=" * 72)
print("  SOLVER OUTPUT")
print("=" * 72)
for msg in collector.summary.messages:
    print(msg.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))

# ── Performance summary ───────────────────────────────────────────────────────
print(f"\n{'Blades':>7} {'D (ft)':>7} {'Vt (fps)':>10} {'SHP':>8} "
      f"{'Thrust':>9} {'BldAng':>8} {'CP':>11} {'CT':>11} "
      f"{'J':>7} {'Mt':>7} {'PNL (dB)':>10}")
print("-" * 97)

for r in rows:
    pnl_str = f"{r.pnl_db:10.1f}" if r.pnl_db > 0.0 else "     (skip)"
    print(f"{r.blades:7.0f} {r.dia_ft:7.2f} {r.tipspd_fps:10.1f} {r.shp:8.1f} "
          f"{r.thrust_lb:9.1f} {r.blade_ang:8.2f} {r.cp:11.6f} {r.ct:11.6f} "
          f"{r.j:7.4f} {r.mach_tip:7.4f} {pnl_str}")

# ── Weight & cost ─────────────────────────────────────────────────────────────
has_cost = any(r.wt70_lb > 0 or r.wt80_lb > 0 for r in rows)

if has_cost:
    print("\n" + "=" * 72)
    print("  WEIGHT & COST BY PRODUCTION QUANTITY")
    print("=" * 72)

    for r in rows:
        print(f"\n  {r.blades:.0f} blades  |  D={r.dia_ft:.1f} ft  |  Vt={r.tipspd_fps:.1f} fps")
        print(f"  {'-'*88}")
        print(f"  {'Qty':>8}  {'Mt':>7}  {'J':>7}  {'CP':>11}  {'CT':>11}  "
              f"{'Wt70 (lb)':>10}  {'Cost70 ($)':>12}  {'Wt80 (lb)':>10}  {'Cost80 ($)':>12}")
        print(f"  {'-'*8}  {'-'*7}  {'-'*7}  {'-'*11}  {'-'*11}  "
              f"{'-'*10}  {'-'*12}  {'-'*10}  {'-'*12}")

        n = max(len(r.qty70), len(r.qty80))
        if n > 0:
            for i in range(n):
                q   = r.qty70[i]      if i < len(r.qty70)      else 0.0
                c70 = r.cost70_qty[i] if i < len(r.cost70_qty) else 0.0
                c80 = r.cost80_qty[i] if i < len(r.cost80_qty) else 0.0
                print(f"  {q:8.0f}  {r.mach_tip:7.4f}  {r.j:7.4f}  {r.cp:11.6f}  {r.ct:11.6f}  "
                      f"{r.wt70_lb:10.1f}  {c70:12.0f}  {r.wt80_lb:10.1f}  {c80:12.0f}")
        else:
            # No quantity breakdown — print single weight/cost line
            print(f"  {'—':>8}  {r.mach_tip:7.4f}  {r.j:7.4f}  {r.cp:11.6f}  {r.ct:11.6f}  "
                  f"{r.wt70_lb:10.1f}  {r.cost70:12.0f}  {r.wt80_lb:10.1f}  {r.cost80:12.0f}")
else:
    print("\n  (no weight/cost data — check DCOST and WTCON settings)")
