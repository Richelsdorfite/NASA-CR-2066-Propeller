#!/usr/bin/env python
"""Analyze cost formula and verify correctness"""

import numpy as np

# Standard test case
WTCON = 1.0       # Category 1
BLADT = 2.0       # 2 blades
CCLF1 = 3.2178    # Default learning curve factor 1
CCLF  = 1.02      # Default learning curve factor 2
WT70  = 35.71     # Weight 1970 (from previous calculation)
CQUAN_quantity = 1910.0  # First quantity level
DAMT = 100.0      # Quantity increment

# From COST.py line 67 (for ICON=1, WTCON=1)
_ZFFAC = np.array([3.5, 3.5, 3.7, 3.7, 3.2, 3.2, 2.6, 3.5, 2.0, 3.4],
                  dtype=float).reshape(5, 2).T
CCK70 = _ZFFAC[0, 0] * (3.0 * BLADT**0.75 + _ZFFAC[0, 0])

print("=== COST FORMULA ANALYSIS ===\n")
print(f"Input parameters:")
print(f"  CCLF1 = {CCLF1:.4f} (cost factor 1)")
print(f"  CCLF  = {CCLF:.4f} (cost factor 2)")
print(f"  WT70  = {WT70:.2f} lb (weight)")
print(f"  CCK70 = {CCK70:.4f} (base cost constant)")
print(f"  CQUAN = {CQUAN_quantity:.0f} (quantity)")
print()

# Learning curve exponent from line 86
XLN = (np.log(CCLF) - np.log(CCLF1)) / 6.90775527
print(f"Learning curve calculation:")
print(f"  XLN = (ln({CCLF}) - ln({CCLF1})) / 6.90775527")
print(f"  XLN = ({np.log(CCLF):.4f} - {np.log(CCLF1):.4f}) / 6.90775527")
print(f"  XLN = {np.log(CCLF) - np.log(CCLF1):.4f} / 6.90775527")
print(f"  XLN = {XLN:.6f}")
print()

# Current formula from line 91
COST70_current = CCK70 * np.exp(np.log(CQUAN_quantity) * XLN + np.log(CCLF1)) * WT70 / CCLF1

# Simplified formula (likely correct)
# The exp(...) term simplifies to: CQUAN^XLN * CCLF1
# When multiplied and then divided by CCLF1, those cancel
COST70_simplified = CCK70 * np.exp(np.log(CQUAN_quantity) * XLN) * WT70 / CCLF1

# Alternative: without the CCLF1 in exp (likely correct per learning curve theory)
COST70_alt = CCK70 * (CQUAN_quantity ** XLN) * WT70 / CCLF1

print(f"Cost calculations:")
print(f"\nCURRENT (with log(CCLF1) in exp):")
print(f"  COST70 = CCK70 * exp(ln(Q)*XLN + ln(CCLF1)) * WT70 / CCLF1")
print(f"  COST70 = {CCK70:.4f} * exp({np.log(CQUAN_quantity)*XLN:.4f} + {np.log(CCLF1):.4f}) * {WT70:.2f} / {CCLF1:.4f}")
print(f"  COST70 = {CCK70:.4f} * {np.exp(np.log(CQUAN_quantity) * XLN + np.log(CCLF1)):.4f} * {WT70:.2f} / {CCLF1:.4f}")
print(f"  COST70 = ${COST70_current:.2f}")

print(f"\nSIMPLIFIED (CCLF1 terms cancel):")
print(f"  = CCK70 * (Q^XLN) * WT70 / CCLF1")
print(f"  = {CCK70:.4f} * {CQUAN_quantity**XLN:.4f} * {WT70:.2f} / {CCLF1:.4f}")
print(f"  = ${COST70_simplified:.2f}")

print(f"\n✓ Current and Simplified match: {abs(COST70_current - COST70_simplified) < 0.01}")

# Check if learning curve makes sense
print(f"\n=== LEARNING CURVE VERIFICATION ===")
print(f"If XLN = {XLN:.6f}, then cost slope is NEGATIVE (decreasing)")
print(f"This means: HIGHER quantities → LOWER costs (cost reductions from learning)")
print()

# Test with different quantities
qty_levels = [1910, 2010, 2110, 2210]
print("Cost at different quantity levels:")
for q in qty_levels:
    cost = CCK70 * (q ** XLN) * WT70 / CCLF1
    print(f"  Q={q:5.0f} → Cost=${cost:7.2f}")

print(f"\n✓ Costs decrease as quantity increases (learning curve effect): ", end="")
costs = [CCK70 * (q ** XLN) * WT70 / CCLF1 for q in qty_levels]
print(costs[0] > costs[-1])
