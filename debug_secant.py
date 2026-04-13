#!/usr/bin/env python
"""Debug the secant method convergence in PERFM.py IW=2"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np

# Instrument PERFM to capture debug info
debug_iterations = []

def capture_secant_debug(CTA, CTA1, NFTX, CT):
    """Store convergence data for analysis"""
    debug_iterations.append({
        'NFTX': NFTX,
        'CTA': CTA[NFTX],
        'CTA1_final': CTA1[NFTX],
        'CTA1_array': CTA1.copy(),
        'CT': CT
    })

# Monkey-patch PERFM to capture debug info
import PERFM
original_perfm_func = PERFM.perfm

def perfm_with_debug(*args, **kwargs):
    # This is complex to hook at the right point, so we'll do it differently
    return original_perfm_func(*args, **kwargs)

PERFM.perfm = perfm_with_debug

# Instead, let's directly test the convergence criterion logic
print("="*80)
print("SECANT METHOD CONVERGENCE CRITERION ANALYSIS")
print("="*80)

# Simulate some convergence scenarios
scenarios = [
    {
        'name': 'Good convergence (residuals -> 0)',
        'residuals': [-0.10, -0.02, 0.001, 0.0001],
        'description': 'Residual approaching zero (correct behavior)'
    },
    {
        'name': 'BAD convergence (residuals oscillate around non-zero)',
        'residuals': [0.05, 0.04, 0.045, 0.041],
        'description': 'Residuals converging to ~0.04, NOT to zero'
    },
    {
        'name': 'Premature convergence (small change, large residual)',
        'residuals': [0.08, 0.075, 0.078, 0.076],
        'description': 'Residuals vary by only ~0.003, but never approach zero'
    }
]

CT_example = 0.5  # Example CT value

for scenario in scenarios:
    print(f"\n{scenario['name']}")
    print(f"Description: {scenario['description']}")
    print(f"Residuals: {scenario['residuals']}")
    print("-" * 80)

    residuals = scenario['residuals']

    # Current WRONG criterion from PERFM.py line 390
    print(f"{'Iter':>4} {'CTA1[KJ]':>12} {'|diff|':>12} {'Converge?':>12} {'|CTA1|/CT':>12}")
    print("-" * 80)

    for kj in range(1, len(residuals)):
        diff = abs(residuals[kj-1] - residuals[kj])
        wrong_criterion = (diff / CT_example <= 0.001)
        residual_ratio = abs(residuals[kj]) / CT_example

        print(f"{kj:4d} {residuals[kj]:12.6f} {diff:12.6f} "
              f"{'YES' if wrong_criterion else 'NO':>12} {residual_ratio:12.4f}")

    # Find where wrong criterion would converge
    for kj in range(1, len(residuals)):
        diff = abs(residuals[kj-1] - residuals[kj])
        if diff / CT_example <= 0.001:
            residual_at_convergence = abs(residuals[kj]) / CT_example
            print(f"\n*** CONVERGENCE at iteration {kj}")
            print(f"    Residual at convergence: {residual_at_convergence:.4f} ({residual_at_convergence*100:.2f}% of CT)")
            break
    else:
        print(f"\nOK: No premature convergence with this tolerance")

print("\n" + "="*80)
print("CORRECT CONVERGENCE CRITERION")
print("="*80)
print("""
The convergence check should be:
    if abs(CTA1[KJ]) / CT <= 0.001:
        break

This checks if the RESIDUAL ITSELF is small (±0.1% of CT), not if the change in
residuals is small. The current criterion checks the wrong thing!
""")
