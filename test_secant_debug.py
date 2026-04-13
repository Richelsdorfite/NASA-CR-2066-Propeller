#!/usr/bin/env python
"""Capture actual secant method iterations from PERFM for IW=2 failing case"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from MAIN import call_input, main_loop, _collector
from output import ResultsCollector
from operating_condition import OperatingCondition, PropellerGeometry
import MAIN as main_module

# Failing test case from Condition N° 2: D=6.0, TS=750, yields 2.17% SHP error
geometry = PropellerGeometry(
    D=6.0, DD=2.0, ND=2,
    AF=150.0, DAF=0.0, NAF=1,
    BLADN=4.0, DBLAD=0.0, NBL=1,
    CLII=0.5, DCLI=0.0, ZNCLI=1,
    ZMWT=0.262,
    WTCON=2.0,
    XNOE=1.0,
    CAMT=0.0, DAMT=0.0, NAMT=0
)

condition = OperatingCondition(
    IW=2,
    THRUST=370.0,
    ALT=7500.0,
    VKTAS=163.2,
    TS=850.0,      # Start from 850
    DTS=-100.0,
    NDTS=2,        # Only first 2 speeds: 850, 750 fps
    DIST=0.0,
    STALIT=0.0,
    DCOST=0.0,
    T=32.33
)

# Instrument PERFM to output debug info
import PERFM

# Save original perfm function
original_perfm = PERFM.perfm

def perfm_instrumented(CT, CP, THRUST, ALT, VS, XFFT, IW, K, L, ZJI, state):
    """Wrapper to capture secant iterations"""

    # Call original but inject debug before/after
    result = original_perfm(CT, CP, THRUST, ALT, VS, XFFT, IW, K, L, ZJI, state)

    # This won't work because PERFM doesn't expose internal variables
    # We need to modify PERFM.py directly
    return result

# Instead, let's modify PERFM by patching it
original_code = None

# Read PERFM to understand the structure better
with open('PERFM.py', 'r') as f:
    perfm_content = f.read()

# Check if instrumentation is already in place
if 'SECANT_DEBUG' not in perfm_content:
    print("Adding instrumentation to PERFM.py...")

    # Find the secant loop and add debug output
    # Look for the line with CTA1[KJ] = CT - CTA[KJ] * XFFT[KL]
    lines = perfm_content.split('\n')

    modified_lines = []
    for i, line in enumerate(lines):
        modified_lines.append(line)

        # Add debug after CTA1[KJ] computation (around line 385)
        if 'CTA1[KJ] = CT - CTA[KJ] * XFFT[KL]' in line:
            indent = len(line) - len(line.lstrip())
            # Add conditional debug output for IW==2
            debug_code = f"""{' ' * indent}# SECANT_DEBUG: capture convergence data
{' ' * indent}if IW == 2 and False:  # Set True to enable debug output
{' ' * indent}    print(f'DEBUG: KJ={{KJ}} CTA[{{KJ}}]={{CTA[KJ]:.6f}} CTA1[{{KJ}}]={{CTA1[KJ]:.6f}} XFFT[{{KL}}]={{XFFT[KL]:.6f}}'"""
            modified_lines.append(debug_code)

    modified_content = '\n'.join(modified_lines)

    with open('PERFM.py', 'w') as f:
        f.write(modified_content)

    print("Instrumentation added (set if condition to True to enable)")

print("\nRunning single test case to analyze secant convergence...")
print("="*80)

collector = ResultsCollector()
main_module._collector = collector
call_input([condition], geometry)

with collector.capture_stdout():
    main_loop()

print("\nResults for D=6.0 ft (should have 2 rows with speeds 850 and 750 fps):")
print("-" * 80)
if len(collector.summary.rows) >= 2:
    for i in range(2):
        r = collector.summary.rows[i]
        print(f"Row {i}: D={r.dia_ft:.2f}, Vt={r.tipspd_fps:.1f}, SHP={r.shp:.1f}, CP={r.cp:.6f}")

    # Compare with reference
    ref_shp = [226, 213]
    ref_cp  = [0.0919, 0.1259]

    print("\n" + "-" * 80)
    print("Errors vs reference:")
    for i in range(2):
        r = collector.summary.rows[i]
        shp_err = ((r.shp - ref_shp[i]) / ref_shp[i]) * 100
        cp_err = ((r.cp - ref_cp[i]) / ref_cp[i]) * 100
        print(f"  Case {i}: SHP error = {shp_err:+.2f}%, CP error = {cp_err:+.2f}%")
