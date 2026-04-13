#!/usr/bin/env python
"""Instrument PERFM.py to trace secant method convergence for IW=2"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np

# Read PERFM.py
with open('PERFM.py', 'r') as f:
    perfm_lines = f.readlines()

# Find and instrument the secant iteration section
# Look for the line: CTA1[KJ] = CT - CTA[KJ] * XFFT[KL]
# and add debug output after convergence check

for i, line in enumerate(perfm_lines):
    # Check if this is the convergence check line for IW=2
    if 'if abs(CTA1[KJ-1] - CTA1[KJ]) / CT <= 0.001:' in line:
        # Found it - add debug code after the break statement
        indent = len(line) - len(line.lstrip())

        # Insert debug code that will print iteration details
        debug_code = f"""{' ' * (indent + 4)}# DEBUG: trace secant convergence
{' ' * (indent + 4)}if K == 0 and L == 0 and KL == 2:  # trace only first case (D=6, CLI=0.5)
{' ' * (indent + 4)}    print(f'CONVERGENCE at iteration {{KJ}}: CTA1[{{KJ}}]={{CTA1[KJ]:.6f}} (diff from prev={{abs(CTA1[KJ-1] - CTA1[KJ]):.6f}})')
"""
        perfm_lines.insert(i + 2, debug_code)
        break

# Also add debug at the start of each KJ iteration
for i, line in enumerate(perfm_lines):
    if 'CTA1[KJ] = CT - CTA[KJ] * XFFT[KL]' in line:
        indent = len(line) - len(line.lstrip())
        debug_code = f"""{' ' * (indent+4)}# DEBUG: trace iteration
{' ' * (indent+4)}if K == 0 and L == 0 and KL == 2:
{' ' * (indent+4)}    print(f'  Iter {{KJ}}: CTA[{{KJ}}]={{CTA[KJ]:.6f}} -> CTA1[{{KJ}}]={{CTA1[KJ]:.6f}} XFFT[{{KL}}]={{XFFT[KL]:.6f}}')
"""
        perfm_lines.insert(i + 1, debug_code)
        break

# Write modified version
with open('PERFM_DEBUG.py', 'w') as f:
    f.writelines(perfm_lines)

print("Created PERFM_DEBUG.py with convergence tracing")
print("=" * 80)

# Now test with the debug version
import importlib.util
spec = importlib.util.spec_from_file_location("PERFM_DEBUG", "PERFM_DEBUG.py")
PERFM_DEBUG = importlib.util.module_from_spec(spec)

# Replace PERFM with debug version in sys.modules for the test
sys.modules['PERFM'] = PERFM_DEBUG

from MAIN import call_input, main_loop, _collector
from output import ResultsCollector
from operating_condition import OperatingCondition, PropellerGeometry
import MAIN as main_module

print("\nTesting with D=6.0 ft, Thrust=370 lbf, T=32.33°F (Condition N° 2)")
print("Watch for convergence trace output for first operating point...")
print("=" * 80)

geometry = PropellerGeometry(
    D=6.0, DD=2.0, ND=1,  # Only D=6.0
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
    TS=850.0,
    DTS=-100.0,
    NDTS=1,  # Only first speed (850 fps)
    DIST=0.0,
    STALIT=0.0,
    DCOST=0.0,
    T=32.33
)

collector = ResultsCollector()
main_module._collector = collector
call_input([condition], geometry)

print("\nRunning main loop (look for convergence trace)...\n")
with collector.capture_stdout():
    main_loop()

print("\n" + "=" * 80)
print("Result:")
if len(collector.summary.rows) >= 1:
    r = collector.summary.rows[0]
    print(f"D=6.0, Vt=850 fps: CP={r.cp:.6f} (ref=0.0919), error={((r.cp-0.0919)/0.0919)*100:.2f}%")
