#!/usr/bin/env python
"""Analyze cost formula variations"""

import numpy as np

# Standard test case values
WTCON = 1.0
BLADT = 2.0
CCLF1 = 3.2178
CCLF  = 1.02
WT70  = 35.71
CQUAN_quantity = 1910.0

# From COST.py line 67 (for ICON=1)
_ZFFAC = np.array([3.5, 3.5, 3.7, 3.7, 3.2, 3.2, 2.6, 3.5, 2.0, 3.4],
                  dtype=float).reshape(5, 2).T
CCK70 = _ZFFAC[0, 0] * (3.0 * BLADT**0.75 + _ZFFAC[0, 0])

XLN = (np.log(CCLF) - np.log(CCLF1)) / 6.90775527

print("=== COST FORMULA VARIATIONS ===\n")
print(f"Input: CCK70={CCK70:.2f}, Q={CQUAN_quantity:.0f}, WT70={WT70:.2f}, CCLF1={CCLF1:.2f}")
print(f"Learning exponent XLN = {XLN:.6f}\n")

# Variation 1: Current formula (my fix)
formula1 = CCK70 * np.exp(np.log(CQUAN_quantity) * XLN) * WT70 / CCLF1
print(f"1. Current (removed log(CCLF1)):")
print(f"   CCK70 * exp(ln(Q)*XLN) * WT70 / CCLF1")
print(f"   = ${formula1:.2f}\n")

# Variation 2: Original formula
formula2 = CCK70 * np.exp(np.log(CQUAN_quantity) * XLN + np.log(CCLF1)) * WT70 / CCLF1
print(f"2. Original (with log(CCLF1) in exp):")
print(f"   CCK70 * exp(ln(Q)*XLN + ln(CCLF1)) * WT70 / CCLF1")
print(f"   = ${formula2:.2f}\n")

# Variation 3: Without CCLF1 division
formula3 = CCK70 * np.exp(np.log(CQUAN_quantity) * XLN) * WT70
print(f"3. Without CCLF1 division:")
print(f"   CCK70 * exp(ln(Q)*XLN) * WT70")
print(f"   = ${formula3:.2f}\n")

# Variation 4: With log(CCLF1) but no division
formula4 = CCK70 * np.exp(np.log(CQUAN_quantity) * XLN + np.log(CCLF1)) * WT70
print(f"4. With log(CCLF1) but no division:")
print(f"   CCK70 * exp(ln(Q)*XLN + ln(CCLF1)) * WT70")
print(f"   = ${formula4:.2f}\n")

# Variation 5: CCLF1 factor (not in exp)
formula5 = CCLF1 * CCK70 * np.exp(np.log(CQUAN_quantity) * XLN) * WT70 / CCLF1
print(f"5. CCLF1 multiplied instead (cancels out):")
print(f"   CCLF1 * CCK70 * exp(ln(Q)*XLN) * WT70 / CCLF1")
print(f"   = ${formula5:.2f}\n")

print("Which formula value seems correct for cost70?")
