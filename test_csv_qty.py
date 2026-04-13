#!/usr/bin/env python
"""Check CSV output"""

import sys
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
    NAMT=2
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

if collector.summary.rows:
    writer = ReportWriter(collector.summary)
    csv = writer.as_csv()
    lines = csv.split('\n')
    print("CSV Header:")
    print(lines[0])
    print("\nFirst data row (qty/cost fields shown):")
    if len(lines) > 1:
        parts = lines[1].split(',')
        # Find and print qty/cost fields
        header = lines[0].split(',')
        for i, h in enumerate(header):
            if 'qty' in h or 'cost' in h.lower():
                print(f"  {h}: {parts[i] if i < len(parts) else 'N/A'}")
