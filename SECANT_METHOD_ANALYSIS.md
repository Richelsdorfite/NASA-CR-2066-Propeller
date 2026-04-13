# Secant Method Analysis for IW=2 (Thrust Path)

## Current Implementation (PERFM.py lines 354-398)

### Initial Guesses (lines 359-360)
```python
CTA[0] = CT           # First guess
CTA[1] = 1.5 * CT     # Second guess
```

### Iteration Loop (lines 362-393)
```python
for KJ in range(5):
    NFTX = KJ
    CTE1 = CTA[KJ] * AFCT[K]
    # ... table lookups and calculations ...
    CTA1[KJ] = CT - CTA[KJ] * XFFT[KL]  # Residual (line 385)
    
    if KJ >= 1:
        # Convergence check
        if abs(CTA1[KJ-1] - CTA1[KJ]) / CT <= 0.001:
            break
        
        # Secant method update (lines 392-393)
        CTA[KJ+1] = (-CTA1[KJ-1] * (CTA[KJ] - CTA[KJ-1])
                     / (CTA[KJ] - CTA1[KJ-1]) + CTA[KJ-1])
```

## Problem Analysis

### 1. **INCORRECT SECANT FORMULA** (Line 392-393)

**Standard Secant Method:**
```
x_{n+1} = x_n - f(x_n) * (x_n - x_{n-1}) / (f(x_n) - f(x_{n-1}))
```

**Current Code (Wrong):**
```python
CTA[KJ+1] = (-CTA1[KJ-1] * (CTA[KJ] - CTA[KJ-1]) 
             / (CTA[KJ] - CTA1[KJ-1]) + CTA[KJ-1])
```

**Issue:** The denominator is `(CTA[KJ] - CTA1[KJ-1])` 
- This mixes a GUESS (CTA[KJ]) with a RESIDUAL (CTA1[KJ-1])
- Should be: `(CTA1[KJ] - CTA1[KJ-1])` (difference in residuals)

**Correct Formula Should Be:**
```python
CTA[KJ+1] = CTA[KJ] - CTA1[KJ] * (CTA[KJ] - CTA[KJ-1]) / (CTA1[KJ] - CTA1[KJ-1])
```

### 2. **INCOMPLETE CONVERGENCE CHECK** (Line 390)

Current check only uses CTA1[KJ-1] and CTA1[KJ], but:
- At KJ=1: Uses CTA1[0] and CTA1[1] ✓
- But CTA1[KJ] hasn't been computed yet when checking convergence for KJ ✓

However, the residual difference check doesn't account for whether CTA1[KJ] is close to zero.

### 3. **INITIAL GUESS BOUNDS** (Lines 359-360)

```python
CTA[0] = CT
CTA[1] = 1.5 * CT
```

**Issues:**
- When CT is very small (e.g., 0.02), CTA[1] = 0.03 might not bracket the root
- XFFT[KL] is typically 0.9-1.0, so we're looking for CTA where:
  - CT - CTA * XFFT ≈ 0
  - CTA ≈ CT / XFFT ≈ CT to 1.11*CT
  
- Initial guess CTA[1] = 1.5*CT is too high! It's OUTSIDE the expected range.

**Better Initial Guesses:**
```python
CTA[0] = CT / 1.05      # Slightly lower
CTA[1] = CT / 0.95      # Slightly higher
```

Or:
```python
CTA[0] = CT * 0.95
CTA[1] = CT * 1.05
```

### 4. **ZERO DENOMINATOR RISK** (Line 392-393)

If `CTA[KJ] ≈ CTA1[KJ-1]`, the denominator approaches zero → division error

## Summary of Issues

| Issue | Severity | Impact on IW=2 |
|-------|----------|----------------|
| Wrong secant formula | **HIGH** | Iteration direction may be wrong; slow/no convergence |
| Initial guesses out of range | **MEDIUM** | Requires more iterations; may diverge for some cases |
| Missing zero-denominator guard | **MEDIUM** | Could crash on certain data |
| Incomplete residual check | **LOW** | May not detect true convergence |

## Likely Cause of 1.76% IW=2 Error

The incorrect secant formula causes the iterator to follow a suboptimal path, never reaching true convergence. The algorithm uses the best value from 5 iterations (even if far from actual solution), resulting in systematic bias.
