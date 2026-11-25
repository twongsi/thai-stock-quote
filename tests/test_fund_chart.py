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


def test_data_urls_use_build_version_without_changing_subpath():
    if not shutil.which('node'):
        pytest.skip('Node is required for browser URL regression')
    source = (Path(__file__).resolve().parents[1] / 'fund_dashboard/static/app.js').read_text()
    function = re.search(r'const assetUrl = \(path\) => \{.*?\n\};', source, re.S).group()
    code = "const document={baseURI:'https://example.test/project/fund/',body:{dataset:{build:'123'}}};\n"
    code += function + "\nconsole.log(assetUrl('data/meta.json').href);"
    result = subprocess.run(['node', '-e', code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == 'https://example.test/project/fund/data/meta.json?v=123'
