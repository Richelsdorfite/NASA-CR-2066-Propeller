#!/usr/bin/env python
"""Rerun computation with explicit temperature 32.33°F for Condition N° 2"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from MAIN import call_input, main_loop, _collector
from output import ResultsCollector
from operating_condition import OperatingCondition, PropellerGeometry
import MAIN as main_module

print("="*80)
print("TESTING CONDITIONS N° 1 and N° 2 (with explicit temperature 32.33°F)")
print("="*80)

# Geometry (same for both conditions)
geometry = PropellerGeometry(
    D=6.0, DD=2.0, ND=2,           # Start 6, increment 2, 2 steps → 6, 8
    AF=150.0, DAF=0.0, NAF=1,      # Start 150, no increment, 1 step → 150
    BLADN=4.0, DBLAD=0.0, NBL=1,  # Start 4, no increment, 1 step → 4
    CLII=0.5, DCLI=0.0, ZNCLI=1,   # Start 0.5, no increment, 1 step → 0.5
    ZMWT=0.262,                     # Design Mach = 0.262
    WTCON=2.0,                      # Category 2
    XNOE=1.0,                       # 1 engine
    CAMT=0.0, DAMT=0.0, NAMT=0     # Default cost settings
)

# Condition N° 1
condition1 = OperatingCondition(
    IW=2,                           # Thrust condition
    THRUST=820.0,                   # Thrust = 820 lbf
    ALT=0.0,                        # Altitude = 0
    VKTAS=71.2,                     # Airspeed = 71.2 knots
    TS=850.0,                       # Start tip speed = 850
    DTS=-100.0,                     # Increment = -100
    NDTS=4,                         # 4 steps
    DIST=500.0,                     # Noise distance = 500
    STALIT=0.0,                     # No stall flag
    DCOST=1.0                       # Cost calculation enabled
)

# Condition N° 2 - WITH EXPLICIT TEMPERATURE
condition2 = OperatingCondition(
    IW=2,                           # Thrust condition
    THRUST=370.0,                   # Thrust = 370 lbf
    ALT=7500.0,                     # Altitude = 7500 ft
    VKTAS=163.2,                    # Airspeed = 163.2 knots
    TS=850.0,                       # Start tip speed = 850
    DTS=-100.0,                     # Increment = -100
    NDTS=4,                         # 4 steps
    DIST=0.0,                       # No noise
    STALIT=0.0,                     # No stall flag
    DCOST=0.0,                      # No cost calculation
    T=32.33                         # EXPLICIT TEMPERATURE: 32.33°F = 492°R
)

collector = ResultsCollector()
main_module.set_collector(collector)
call_input([condition1, condition2], geometry)

print("\nRunning main loop...\n")
try:
    main_loop()
finally:
    main_module.set_collector(None)

print("\n" + "="*80)
print("CONDITION N° 1 RESULTS (Verification)")
print("="*80)

if len(collector.summary.rows) >= 4:
    print(f"\nResults for Condition N° 1 (4 tip speeds at D=6 ft):")
    print("-" * 80)
    print(f"{'IC':>3} {'D (ft)':>8} {'Vt (fps)':>10} {'SHP':>10} {'BldAng':>10} {'CP':>12} {'CT':>12}")
    print("-" * 80)

    for i in range(4):
        r = collector.summary.rows[i]
        print(f"{i+1:3d} {r.dia_ft:8.2f} {r.tipspd_fps:10.1f} {r.shp:10.1f} "
              f"{r.blade_ang:10.2f} {r.cp:12.6f} {r.ct:12.6f}")

print("\n" + "="*80)
print("CONDITION N° 2 RESULTS (with T = 32.33°F = 492°R)")
print("="*80)

# Each condition has 2 diameters × 4 tip speeds = 8 results per condition
# Condition 1: rows 0-7
# Condition 2: rows 8-15
if len(collector.summary.rows) >= 16:
    print(f"\nResults for Condition N° 2 (all 8 combinations):")
    print("-" * 80)
    print(f"{'IC':>3} {'D (ft)':>8} {'Vt (fps)':>10} {'SHP':>10} {'BldAng':>10} {'CP':>12} {'CT':>12}")
    print("-" * 80)

    for i in range(8, 16):
        r = collector.summary.rows[i]
        print(f"{i-7:3d} {r.dia_ft:8.2f} {r.tipspd_fps:10.1f} {r.shp:10.1f} "
              f"{r.blade_ang:10.2f} {r.cp:12.6f} {r.ct:12.6f}")

    print("\n" + "="*80)
    print("COMPARISON WITH REFERENCE VALUES (Condition N° 2)")
    print("="*80)

    reference = [
        (6.00, 850.0, 226, 23.5, 0.0919, 0.0739),
        (6.00, 750.0, 213, 26.9, 0.1259, 0.0950),
        (6.00, 650.0, 208, 31.5, 0.1891, 0.1264),
        (6.00, 550.0, 212, 37.8, 0.3179, 0.1766),
        (8.00, 850.0, 262, 22.0, 0.0598, 0.0416),
        (8.00, 750.0, 232, 25.1, 0.0773, 0.0534),
        (8.00, 650.0, 215, 29.1, 0.1098, 0.0711),
        (8.00, 550.0, 207, 34.3, 0.1747, 0.0993),
    ]

    print(f"\n{'IC':>3} {'Param':>8} {'Calculated':>15} {'Reference':>15} {'Error':>10}")
    print("-" * 80)

    for i in range(8):
        r = collector.summary.rows[i + 8]
        ref = reference[i]

        # SHP
        shp_error = ((r.shp - ref[2]) / ref[2]) * 100
        print(f"{i+1:3d} {'SHP':>8} {r.shp:15.1f} {ref[2]:15.0f} {shp_error:9.2f}%")

        # BldAng
        ang_error = ((r.blade_ang - ref[3]) / ref[3]) * 100
        print(f"    {'BldAng':>8} {r.blade_ang:15.2f} {ref[3]:15.1f} {ang_error:9.2f}%")

        # CP
        cp_error = ((r.cp - ref[4]) / ref[4]) * 100
        print(f"    {'CP':>8} {r.cp:15.6f} {ref[4]:15.4f} {cp_error:9.2f}%")

        # CT
        ct_error = ((r.ct - ref[5]) / ref[5]) * 100
        print(f"    {'CT':>8} {r.ct:15.6f} {ref[5]:15.4f} {ct_error:9.2f}%")
        print("-" * 80)

else:
    print(f"ERROR: Expected at least 16 results, got {len(collector.summary.rows)}")
