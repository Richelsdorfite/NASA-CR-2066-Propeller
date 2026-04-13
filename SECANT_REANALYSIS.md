# Re-Analysis of Secant Method for IW=2

## The Fortran/Python Formula IS Correct
```fortran
CTA(KJ+1) = -CTA1(KJ-1)*(CTA(KJ)-CTA(KJ-1))/(CTA(KJ)-CTA1(KJ-1))+CTA(KJ-1)
```

This is the actual implementation in both Fortran and Python - NOT an error.

## Re-examining the Algorithm

### Iteration Sequence:

**KJ=0:**
- CTA[0] = CT (initial guess)
- CTA1[0] = CT - CTA[0] * XFFT = residual at CTA[0]
- Convergence check? NO (KJ < 1)
- Continue to next iteration

**KJ=1:**
- CTA[1] = 1.5 * CT (second initial guess)
- CTA1[1] = CT - CTA[1] * XFFT = residual at CTA[1]
- Convergence check? YES: if |CTA1[0] - CTA1[1]| / CT <= 0.001 → break?
- If not converged: CTA[2] = formula using CTA1[0], CTA[1], CTA[0]

**KJ=2:**
- CTA[2] = result from formula
- CTA1[2] = CT - CTA[2] * XFFT = residual at CTA[2]
- Convergence check? YES: if |CTA1[1] - CTA1[2]| / CT <= 0.001 → break?
- If not converged: CTA[3] = formula using CTA1[1], CTA[2], CTA[1]

...and so on

## Potential Issues Identified:

### 1. **CONVERGENCE USES WRONG RESIDUAL INDEX**

Line 390:
```python
if abs(CTA1[KJ-1] - CTA1[KJ]) / CT <= 0.001:
```

BUT the secant formula uses:
```python
CTA[KJ+1] = ... / (CTA[KJ] - CTA1[KJ-1]) + CTA[KJ-1]
```

**Issue:** At iteration KJ, we're comparing residuals at KJ-1 and KJ, but the formula uses residual from KJ-1 (not current residual CTA1[KJ])!

The convergence check doesn't directly tell us if CTA1[KJ] ≈ 0 (the goal).

### 2. **INITIAL GUESSES MAY NOT BRACKET THE ROOT**

```python
CTA[0] = CT
CTA[1] = 1.5 * CT
```

For convergence, ideal is when:
- CTA1[0] and CTA1[1] have **opposite signs** (bracket the root)

But we're calculating:
- CTA1[0] = CT - CTA[0] * XFFT[KL] = CT - CT * XFFT = CT * (1 - XFFT)
- CTA1[1] = CT - CTA[1] * XFFT[KL] = CT - 1.5*CT * XFFT = CT * (1 - 1.5*XFFT)

Since XFFT is typically 0.9-1.0 and CT > 0:
- CTA1[0] = CT * (1 - 0.9 to 1.0) = CT * (0 to 0.1) → slightly positive
- CTA1[1] = CT * (1 - 1.5*0.9 to 1.5*1.0) = CT * (-0.35 to -0.5) → NEGATIVE!

✓ They DO have opposite signs (good for bracketing)

### 3. **MISSING: USE OF CURRENT RESIDUAL IN ITERATION**

Standard secant method uses both current AND previous residuals. This formula ONLY uses previous residual (CTA1[KJ-1]).

For iteration KJ, we should use:
- CTA1[KJ-1] and CTA1[KJ] to form the secant through previous two points

But we only use CTA1[KJ-1]. This might be intentional (simpler), but it means convergence is slower.

## Critical Question:

**Does the original Fortran code produce ±0.1% accuracy (like IW=1) or does it also produce 1.76% error for IW=2?**

If Fortran is accurate → Python translation has a subtle bug
If Fortran also has 1.76% error → The algorithm itself is the limitation
