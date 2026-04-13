#!/usr/bin/env python
"""Verify M and FT columns are present in output"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from MAIN import call_input, main_loop, _collector
from output import ResultsCollector, ReportWriter
from operating_condition import OperatingCondition, PropellerGeometry
import MAIN as main_module

# Setup test data
geometry = PropellerGeometry(
    D=6.00, DD=2.00, ND=2,
    AF=100.0, DAF=0.0, NAF=1,
    BLADN=2.0, DBLAD=0.0, NBL=1,
    CLII=0.50, DCLI=0.0, ZNCLI=1,
    ZMWT=0.187
)

conditions = [
    OperatingCondition(IW=1, BHP=150.0, ALT=0.0, VKTAS=52.5, TS=950.0, DTS=-100.0, NDTS=1)
]

# Attach collector and run
collector = ResultsCollector()
main_module._collector = collector
call_input(conditions, geometry)
with collector.capture_stdout():
    main_loop()

# Verify results contain the new fields
if collector.summary.rows:
    row = collector.summary.rows[0]
    print(f"\n✓ mach_fs = {row.mach_fs:.4f}")
    print(f"✓ mach_tip = {row.mach_tip:.4f}")
    print(f"✓ ft = {row.ft:.4f}")

    # Check text output
    writer = ReportWriter(collector.summary)
    text = writer.as_text()
    if 'M' in text and 'Mt' in text and 'FT' in text:
        print("✓ Text report has M, Mt, FT columns")

    # Check CSV
    csv = writer.as_csv()
    if 'mach_fs' in csv and 'ft' in csv:
        print("✓ CSV has mach_fs and ft columns")
else:
    print("No results!")
