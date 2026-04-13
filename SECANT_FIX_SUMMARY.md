# IW=2 Secant Method Bug Fix - Summary

## Problem Identified

The secant method iteration for IW=2 (thrust-specified) contained an **incorrect formula** that was faithfully translated from the Fortran code. The formula had a dimensionally inconsistent denominator that mixed a **guess value** with a **residual value**.

### Original (INCORRECT) Formula (PERFM.py line 392-393)
```python
CTA[KJ+1] = (-CTA1[KJ-1] * (CTA[KJ] - CTA[KJ-1])) / (CTA[KJ] - CTA1[KJ-1]) + CTA[KJ-1]
            └─────────────────────────────────────────┬──────────────────────────────────┘
                                                Denominator mixes guess (CTA) with residual (CTA1)
```

### Standard Secant Method (CORRECT)
```
x_{n+1} = x_n - f(x_n) * (x_n - x_{n-1}) / (f(x_n) - f(x_{n-1}))
           └──┬──┘  └──────────────────┬──────────────────────┘
               │                       └─ Both are residuals!
          Current x         Both differences are between x values AND residuals
```

The denominator should compare **residuals to residuals**, not **guess to residual**.

## Fix Applied

Replaced line 392-393 with the mathematically correct secant formula:

```python
denom = CTA1[KJ] - CTA1[KJ-1]
if abs(denom) > 1e-14:  # Avoid division by zero
    CTA[KJ+1] = CTA[KJ] - CTA1[KJ] * (CTA[KJ] - CTA[KJ-1]) / denom
else:
    CTA[KJ+1] = (CTA[KJ] + CTA[KJ-1]) / 2.0  # Fallback for equal residuals
```

## Results

### Before Fix (Worst cases)
| Case | SHP Error | CP Error |
|------|-----------|----------|
| IC 2 | 2.17% | 2.25% |
| IC 3 | 3.09% | 3.04% |
| IC 7 | 2.45% | 2.53% |
| IC 8 | 2.72% | 2.69% |

### After Fix (Same cases)
| Case | SHP Error | CP Error | Improvement |
|------|-----------|----------|-------------|
| IC 2 | 1.05% | 1.13% | ↓ 1.1% |
| IC 3 | 2.62% | 2.57% | ↓ 0.5% |
| IC 7 | 1.97% | 2.05% | ↓ 0.5% |
| IC 8 | 2.72% | 2.69% | (no change) |

### Best Cases After Fix
| Case | SHP Error | CP Error |
|------|-----------|----------|
| IC 1 | 0.20% | 0.13% |
| IC 5 | -0.14% | 0.01% |
| IC 6 | 0.78% | 0.64% |

## Remaining Accuracy Gap

After the fix, most IW=2 cases are within 1-2% (vs original 2-3%), but we have not yet achieved IW=1's ±0.1% accuracy on all operating points. This suggests:

1. **Hypothesis 1:** The Fortran code has the same bug and similar remaining errors
2. **Hypothesis 2:** There may be additional subtle issues in either code
3. **Hypothesis 3:** The algorithm has inherent limitations for certain operating points

### Recommended Next Step

Compare results with original Fortran PERFM to determine if:
- Fortran produces similar 2-3% errors (algorithm limitation)
- Fortran produces better accuracy (additional Python bug exists)
- The 2.6% remaining error on IC 3 & 8 is expected behavior

## Code Location

- **File:** PERFM.py
- **Lines:** 392-398 (secant iteration)
- **Function:** perfm() - IW==2 branch
