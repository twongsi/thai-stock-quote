"""The chart and Python statistics must use the same holiday-boundary NAV."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


def test_chart_keeps_nav_before_weekend_boundary():
    if not shutil.which('node'):
        pytest.skip('Node is required for the browser date-window regression')
    source = (Path(__file__).resolve().parents[1] / 'fund_dashboard/static/app.js').read_text()
    function = re.search(r'function rangePoints\(history, range\) \{.*?\n\}', source, re.S).group()
    rows = [{'d': '2025-11-21', 'nav': 10}, {'d': '2025-11-24', 'nav': 11},
            {'d': '2026-11-23', 'nav': 12}]
    code = "const RANGE_DAYS={ '1Y':365 }; const toDate=x=>new Date(x+'T00:00:00Z');\n"
    code += function + '\nconsole.log(JSON.stringify(rangePoints(' + json.dumps(rows) + ", '1Y')));"
    result = subprocess.run(['node', '-e', code], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == rows
