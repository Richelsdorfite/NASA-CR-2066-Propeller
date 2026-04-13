#!/usr/bin/env python
"""Test reorganized output format"""

import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from MAIN import call_input, main_loop, _collector
from output import ResultsCollector, ReportWriter
from operating_condition import OperatingCondition, PropellerGeometry
import MAIN as main_module

geometry = PropellerGeometry(
    D=6.00, DD=0.0, ND=1,
    AF=100.0, DAF=0.0, NAF=1,
    BLADN=2.0, DBLAD=0.0, NBL=1,
    CLII=0.50, DCLI=0.0, ZNCLI=1,
    ZMWT=0.187,
    WTCON=1.0,
    CAMT=0.0,
    DAMT=100.0,
    NAMT=3
)

conditions = [
    OperatingCondition(IW=1, BHP=150.0, ALT=0.0, VKTAS=52.5, TS=950.0, DTS=-100.0, NDTS=1,
                      DCOST=1.0)
]

collector = ResultsCollector()
main_module._collector = collector
call_input(conditions, geometry)
with collector.capture_stdout():
    main_loop()

print("=== LOG OUTPUT (one line per computation) ===\n")
# Get last few messages (the computation output)
for msg in collector.summary.messages[-30:]:
    # Only show the relevant lines (the performance line and weight/cost line)
    if "Diameter=" in msg or "Wt70=" in msg:
        print(msg)

print("\n\n=== CSV FORMAT (grouped by technology) ===\n")
writer = ReportWriter(collector.summary)
csv_lines = writer.as_csv().split('\n')
print(csv_lines[0])
if csv_lines[1]:
    print(csv_lines[1][:100] + "...")

print("\n\n=== EXPORT FILES TEST ===")
with tempfile.TemporaryDirectory() as tmpdir:
    paths = writer.save_all(Path(tmpdir) / "test")
    print(f"✓ Text file saved")
    print(f"✓ CSV file saved")
    print(f"✓ JSON file saved")
