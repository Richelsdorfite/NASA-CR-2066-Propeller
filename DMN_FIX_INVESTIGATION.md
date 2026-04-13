# IW=2 Investigation Summary

## Findings

### 1. DMN Condition Fix Applied
Changed line 383 from:
```python
if DMN > 0.0:
```
to:
```python
if abs(DMN) > 0.0:
```

**Result:** biquad() is now called with negative DMN values, but returns **XFFT = 1.0** (unchanged).

### 2. Why XFFT = 1.0 is Correct
- biquad() is a table interpolation function
- It looks up XFFT value in the ZMMMC table based on DMN and CTE2
- For all test operating points, the table returns XFFT = 1.0
- This means **no compressibility loss** (factor of 1.0 = 100% efficiency)
- This is likely correct for the test conditions

### 3. Secant Iteration Early Exit is Correct
Since XFFT = 1.0:
```python
CTA1[0] = CT - CTA[0] * XFFT = CT - CT * 1.0 = 0.0
```
The condition `if CTA1[0] == 0.0: break` correctly identifies that the **initial guess CTA[0] = CT is already the solution** and further iteration is unnecessary.

### 4. Algorithm Architecture is Correct
The secant iteration flow is:
1. Initial guess: CTA[0] = CT, CTA[1] = 1.5 × CT
2. Compute XFFT via table lookup (biquad)
3. Compute residuals: CTA1[KJ] = CT - CTA[KJ] × XFFT
4. If residual = 0, solution found; otherwise iterate

For XFFT = 1.0, the first residual is zero, so iteration stops immediately. This is **correct behavior**, not a bug.

### 5. Remaining IW=2 Error Not Explained by Algorithm
Current accuracy:
- IW=1: ±0.1% error (accurate)
- IW=2: 1-3% error (systematic)

The ~2% error cannot be explained by:
- ✓ Secant iteration logic (algorithm works correctly)
- ✓ XFFT computation (table lookup works correctly)  
- ✓ Double division bug (user's theory was correct in principle but XFFT=1.0 makes it irrelevant here)

### Next Steps to Investigate

1. **Check IW=2 input/output variables:** Are TS (thrust specification), ALT, VKTAS being used correctly?
2. **Compare detailed intermediate values** with Fortran to find where divergence occurs
3. **Review the CTA initialization**: Is CTA[0] = CT the right initial guess for thrust mode?
4. **Check reference data:** Are the 2% errors within acceptable tolerance or genuine mismatches?

## Conclusion

The DMN fix allows XFFT to be properly computed from the table, but since the table returns 1.0 for these test points, there's no functional change. The secant iteration algorithm is working as designed.

The 1-3% IW=2 error appears to be fundamental to either:
- The algorithm's inherent accuracy for thrust-specified mode
- A correctness issue in another part of the calculation (not the secant method)
- A difference between Fortran and Python implementations in other routines
