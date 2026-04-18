# H432 — NASA CR-2066  Optimisation TODO

Priority order: highest impact first.

---

## 0. New Features (ranked by impact)

### High impact

- [x] **Torque column in results**
  Torque is directly derivable from quantities already computed:
  `Q (ft·lbf) = SHP × 5252.11 / RPM` (US) or `Q (N·m) = kW × 9549.3 / RPM` (SI),
  where `RPM = Vt × 60 / (π × D)`.
  Added `torque` field to `ResultRow` and `RevThrustRow`; computed in `MAIN.py` and
  `REVTHT.py`; shown in Log window with unit label; displayed as "Torque(ft·lbf)" /
  "Torque(N·m)" column in both Results and Rev-Thrust treeviews; included in all
  saved formats (txt, csv, json) with full unit-system conversion.

- [ ] **Engine characteristics database**
  Store engine "decks" in a JSON file (`engines.json`):
  name, type (reciprocating / turbine / electric), rated SHP, rated RPM, gear reduction
  ratio, altitude power-lapse model, and an optional RPM→SHP table.
  - **Engine selection dropdown** in the Conditions tab (or a dedicated Engine tab):
    auto-fill BHP, RPM, gear ratio for the selected engine.
  - **Auto-compute propeller RPM** from engine RPM and gear ratio, removing the need
    to guess tip speed manually.
  - **Altitude derating**: automatically reduce BHP with altitude using the engine's
    lapse model (`P ≈ P_SL × ρ/ρ₀` for reciprocating; turbine model TBD).
  - Effort: **medium** (~200–300 lines for a minimal useful version).

- [ ] **Engine operating-point matching**
  At each (diameter, RPM) the propeller requires `P_req = CP × ρ × n³ × D⁵`.
  The engine delivers `P_avail(RPM, ALT, T)`. Iterate RPM until
  `P_req == P_avail` to find the true equilibrium operating point — currently H432
  assumes BHP is fixed input.  Requires the engine deck above.
  Torque matching (`Q_prop == Q_engine`) gives an independent check.
  Effort: **medium** (~150–200 additional lines).

- [x] **Propeller characteristic map (CP–CT–J)**
  `run_map()` added to `MAIN.py`: sweeps J from `j_start` to `j_end` in `nj`
  steps for every (AF, CLi, blades, D, Vt) geometry combination.  At each J,
  `V_ktas = J × Vt / J_CONV`; CP is held fixed (derived from BHP, Vt, D, RORO)
  so the returned CT(J) and η(J) = J·CT/CP trace the propeller's operating line
  at fixed power and RPM — the standard certification deliverable.
  Added `MapPoint`, `MapCurve`, `MapResult` dataclasses to `output.py`;
  `MapResult.as_csv()` exports all points as a flat CSV.
  New **🗺 Map** notebook tab (`MapFrame` in `HMI.py`): J sweep parameters
  (start/end/steps), condition selector, plot-type radio (η / CT / CP / All),
  group-by radio (Blades / BAF / CLi / Dia / Vt), embedded dark-theme
  matplotlib figure (1 or 3 stacked subplots), ▶ Run Map, ✕ Clear, 📤 Export CSV.
  Run executes in a background thread; off-chart PERFM points are silently
  excluded from the plot.  IW=3 conditions are rejected with a clear message.

- [x] **Plot tab (matplotlib embedded in the notebook)** *(see section 3)*
  `PlotFrame` class added; nine selectable curve types (η/CT/CP vs J, Thrust/SHP/Weight vs
  Diameter, SHP vs Tip Speed, Rev Thrust vs Airspeed); group-by radio buttons (Condition,
  Blades, AF, CLi); dark-theme matplotlib figure; SI unit conversion; auto-refreshes after
  each run; responds to unit-system toggle; cleared by ✕ Clear.

### Medium impact

- [ ] **Altitude and temperature sweep**
  Add per-condition sweep parameters `DALT` / `NALT` (1–10) and `DT` / `NT` (1–10)
  mirroring the existing tip-speed sweep pattern.  RORO is a function of ALT and T
  only, so the sweep introduces a new ALT × T loop wrapping the AF loop in `MAIN.py`;
  this also resolves the "compute RORO once" performance item as a natural side-effect.
  Files to touch: `operating_condition.py` (4 new fields), `MAIN.py` (loop
  restructure + RORO placement), `output.py` / `ResultRow` / `RevThrustRow`
  (add `alt_ft`, `temp_r`), `HMI.py` (ConditionDialog: 4 new entries; Results and
  Rev-Thrust treeviews: new "Atmosphere" column group; all export formats).
  Add a total-points warning in the HMI before running to guard against combinatorial
  explosion (NAF × ZNCLI × NBL × ND × NALT × NT × NDTS can reach 10⁷ at max steps).
  Effort: **medium**.

- [ ] **Multi-condition mission summary**
  Define a mission as a sequence of named phases (takeoff, climb, cruise, loiter,
  descent) with weights (fuel fraction, time fraction). Compute weighted efficiency,
  weighted noise exposure, and total propeller weight impact on payload.
  Useful for optimising across the full flight rather than at a single design point.
  Effort: **medium**.

- [ ] **Blade stress (first-order estimate)**
  Centrifugal stress at the blade root:
  `σ_c = ρ_blade × (2πn)² × ∫r·A(r)dr`.
  Add bending moment from the thrust distribution.  Flag (diameter × RPM) combinations
  that exceed a material limit (parameterised by AF and blade material choice).
  Useful for certification screening. Effort: **medium**.

- [ ] **Electric motor matching**
  Same structure as the engine deck but simpler: flat torque up to base RPM,
  then constant power above. Motor deck = 3-column table (RPM, torque, efficiency).
  Matching logic is identical to the piston engine case. Increasingly relevant for
  eVTOL and hybrid aircraft. Effort: **medium**.

- [x] **Atmospheric model improvement (ISA+ΔT)**
  Added `DT_ISA` (ISA temperature deviation, °F) per operating condition.
  Applied in `MAIN.py` RORO block when `T ≤ 0` (ISA day):
  `T_RANKINE = T0_ISA - LAPSE_RATE × alt + DT_ISA` (troposphere) or
  `T_RANKINE = T_TROPO + DT_ISA` (stratosphere).
  Also fixed the T mutation bug: `com_zinput.T[IC]` is no longer overwritten with
  the Rankine value, so repeated Run clicks produce correct temperatures.
  `DT_ISA` field added to `OperatingCondition`, wired in `load_conditions()`,
  and exposed in `ConditionDialog` with tooltip (ignored when T > 0).
  Custom atmosphere tables and MIL-STD-210 profiles remain future work.

### Low impact / easy to add

- [ ] **Noise certification margin**
  Overlay FAA Part 36 / ICAO Annex 16 limits on the PNL results for the selected
  aircraft category. Flag configurations that exceed the limit.
  Effort: **trivial** (lookup table).

- [ ] **Comparative run (delta table)**
  Run two configurations back-to-back (e.g. 3-blade vs 4-blade) and display a
  ΔThrust / ΔSHP / ΔWeight / ΔCost / ΔNoise table.  Currently the user must compare
  two separate result files manually. Effort: **low**.

- [ ] **Session history**
  Keep the last N runs in memory (or a `.h432history` file) so the user can compare
  current results with a previous run without re-running. Effort: **low**.

---

## 1. Architecture

- [x] **Replace `print()` → collector in `PERFM.py`**
  Removed the `sys.stdout` redirect hack (`capture_stdout()` / `_StdoutCapture`).
  Added `_emit()` helper in `MAIN.py` and `_emit_fn = print` in `PERFM.py` and
  `REVTHT.py`; wired together by `set_collector()` which HMI calls instead of
  directly setting `_collector`. All 17 `print()` calls in `MAIN.py`, 3 in
  `PERFM.py`, and 4 in `REVTHT.py` now route through `_emit` / `_emit_fn`.
  In CLI mode they fall back to `print()`; in HMI mode they go directly to
  `collector.add_message()`. `output.py` cleaned up (removed `_StdoutCapture`,
  `capture_stdout()`, unused `sys` / `TextIO` imports).

- [x] **Eliminate global mutable state in `MAIN.py`**
  Removed module-level `state`, `_collector`, `_unit_system`, `com_zinput`,
  `com_afcor`, `com_cpecte`, `com_astrk`, `FC`, `RORO`, `ZMS` and all other
  aliases.  `call_input()` now creates a fresh `PropellerState` and returns it;
  `main_loop(state, collector=None, unit_system="US")` receives everything as
  explicit arguments.  `run_map()` creates its own local state internally.
  PERFM / REVTHT emitters wired per-call at the top of `main_loop()`.
  `set_collector()` and `main_module._unit_system` removed from `HMI.py`.
  Tests updated: `_run()` helpers use the returned state; T-mutation test
  reads state from `call_input()` return value.  74 tests pass.

- [ ] **Split `HMI.py` (1 664 lines) into focused modules**
  Suggested split:
  - `hmi_geometry.py`   — `GeometryFrame`
  - `hmi_conditions.py` — `ConditionsFrame`, `ConditionDialog`
  - `hmi_results.py`    — `ResultsFrame`, `RevThrustFrame`, `LogFrame`
  - `hmi_runner.py`     — `AppWindow` (toolbar, notebook, run/save/load logic)

---

## 2. Performance

- [x] **Compute atmosphere (`RORO`) once per condition, not inside the sweep loop**
  `RORO[IC]`, `FC[IC]`, `TOT`, and `T_RANKINE` are computed in the IC loop
  before the AF / CLi / blade / diameter / tip-speed sweep begins.
  They depend only on `ALT[IC]` and `T[IC]`, both fixed per condition, so they
  are never recalculated inside the geometry loops.  (The "move it above the
  diameter loop" note already reflects the existing code structure; this item
  tracks the T mutation bug fix and DT_ISA addition that complete the work.)

- [ ] **Replace `BIQUAD.py` / `UNINT.py` with `scipy.interpolate`**
  The two Fortran-translated interpolation routines are correct but slow Python
  loops. `scipy.interpolate.RegularGridInterpolator` (already available in
  `.venv`) would be faster and better tested.

- [ ] **Vectorise or parallelise the geometry sweep**
  The five nested loops in `MAIN.py` (AF × CLi × blades × diameter × tip speed)
  run sequentially in Python. For large sweeps, use
  `concurrent.futures.ProcessPoolExecutor` — one worker per
  (diameter × tip-speed) point.  The global-state prerequisite is now met.

---

## 3. HMI / User Experience

- [x] **Real-time input validation in the Condition dialog and Geometry tab**
  `_attach_validator(entry, ok_fn)` helper binds `<KeyRelease>` and `<FocusOut>`;
  invalid entries turn dark red (`Error.TEntry` style). Geometry tab: 26 fields
  with physics-meaningful ranges (AF 80–200, BLADN 2–8, CLi 0.3–0.8, Mach 0–1 …).
  Condition dialog: 17 fields incl. ALT range adjusted for SI/US. Non-blocking
  (never prevents typing); existing OK-button validation unchanged.

- [x] **Progress bar for long sweeps**
  `ResultsCollector` gains `_tick_fn` called by `add_row()` / `add_rev_row()` after
  every result point. Toolbar right side replaced with a `grid` container: progress
  bar (200 px, determinate) + `"N / total"` counter label, hidden until a run starts.
  `_compute_total_points()` estimates the total (NAF × ZNCLI × NBL × ND × NDTS for
  IW=1/2; NAF × NBL × ND × NPCPW × NOUNT for IW=3). `_poll_progress()` runs every
  120 ms in the GUI thread; `_progress_tick()` increments an int from the background
  thread (GIL-safe). Bar is hidden 2 s after completion, or immediately on error.

- [x] **Column visibility toggles in the Results treeview**
  Checkbox strip above the treeview controls five groups: Aero coeff (J/M/Mt/BldAng/CP/CT/FT/Eff%),
  Performance (Thrust/SHP/Torque), Noise (PNL), Cost 70, Cost 80.
  Core columns (IC, Blades, AF, CLi, Dia, Vt, Status) are always visible.
  Uses `displaycolumns` so `populate()` is unchanged.

- [x] **Propeller efficiency η = J·CT/CP** — computed in `MAIN.py`, stored in
  `ResultRow.eta`, displayed as "Eff%" in the Results treeview, and included in
  all saved formats (txt, csv, json). Displays "—" when J=0 (static condition).

- [x] **Log window single-line format** — weight/cost data appended inline on the
  same line as the performance data; single `_emit()` per iteration, no second line.
  Format: `Qty70= XXXX  Wt70= XXX.Xlb  Cost70= $XXXX.XX  Qty80= …`

- [x] **US / SI unit system toggle** — `units.py` module with `UnitSystem` enum and
  conversion helpers; toolbar `[US]`/`[SI]` button propagates to all tabs;
  `ConditionDialog` and `GeometryFrame` accept and convert values; Results and
  Rev-Thrust treeviews display in selected units; all saved formats (txt, csv, json)
  record and apply the active unit system.  Internal computation always runs in
  US customary; conversion is at the HMI and file-output boundary only.

- [x] **Plot tab (matplotlib embedded in the notebook)** *(see section 0)*

---

## 4. Testing & Reliability

- [x] **`pytest` unit test suite for individual subroutines**
  74 tests across 4 files in `tests/`:
  - `test_interpolation.py` — 9 UNINT tests + 5 BIQUAD tests (boundary behaviour,
    exact knot recovery, regression values: 5000 ft→0.833338, 36000 ft→0.224458,
    ZMMMC table at DMN=0.04→0.984).
  - `test_subroutines.py` — 5 WAIT tests, 3 COST tests, 6 PERFM tests (IW=1 and
    IW=2 modes; off-chart sentinel; CP/CT regression values; η and CT monotonicity).
  - `test_atmosphere.py` — 7 ISA atmosphere tests + 2 T-mutation regression tests
    (state.T[IC] must stay in °F; repeated runs produce bit-identical CP/CT).
  - `test_integration.py` — 17 IW=2 two-condition tests, 3 IW=3 reverse-thrust
    tests, 16 IW=1 stall+cost tests; physical consistency checks for all three.
  Requires `pytest` installed in the project venv (`python -m ensurepip` then
  `python -m pip install pytest`).

- [x] **Automated CI check (pre-commit hook)**
  `.git/hooks/pre-commit` locates the project venv (`venv/Scripts/python.exe`)
  or falls back to PATH Python, then runs `python -m pytest --tb=short -q`.
  Aborts the commit with a clear message if any test fails; warns and skips
  (non-blocking) if pytest is not installed.  `pyproject.toml` updated with
  `[tool.pytest.ini_options]` setting `testpaths = ["tests"]` and
  `addopts = "-q --tb=short"` so plain `python -m pytest` also works.
