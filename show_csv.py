#!/usr/bin/env python
"""Show sample CSV output with new columns"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from MAIN import call_input, main_loop, _collector
from output import ResultsCollector, ReportWriter
from operating_condition import OperatingCondition, PropellerGeometry
import MAIN as main_module

# Setup test data
geometry = PropellerGeometry(
    D=6.00, DD=0.0, ND=1,
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

if collector.summary.rows:
    writer = ReportWriter(collector.summary)
    csv_data = writer.as_csv()
    print("CSV Header:")
    print(csv_data.split('\n')[0])
    print("\nFirst row (sample):")
    print(csv_data.split('\n')[1])
else:
    print("No results!")
