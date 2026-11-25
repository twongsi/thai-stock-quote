import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fund_dashboard"))
import fund_service
import quote_service
from demo_data import DemoClient
from sec_api import ENDPOINTS, SecApiError


def test_stock_quote_does_not_need_sec_key():
    def forbidden():
        raise AssertionError("stock route must not construct SEC client")
    quote = quote_service.get_quote({"asset_type": "stock", "symbol": "PTT"}, forbidden)
    assert quote["price"] > 0
    assert quote["interval"] == "1wk"
    assert quote["date_semantics"] == "bar_start_date"
    assert not quote["is_realtime"] and not quote["is_demo"]
    assert "history" not in quote


def test_fund_quote_marks_demo_and_class():
    result = quote_service.get_quote({"asset_type": "fund", "symbol": "SCBNDQ(A)"}, DemoClient, demo=True)
    assert result["price"] > 0 and result["is_demo"]
    assert result["price_type"] == "nav" and result["class_name"] == "SCBNDQ(A)"


@pytest.mark.parametrize("params", [
    {"asset_type": "stock", "symbol": "../../README"},
    {"asset_type": "stock", "symbol": "PTT", "years": "abc"},
    {"asset_type": "stock", "symbol": "PTT", "start": "2026-01-01", "end": "2025-01-01"},
    {"asset_type": "other", "symbol": "PTT"},
])
def test_invalid_queries(params):
    with pytest.raises(SecApiError) as exc:
        quote_service.get_quote(params, DemoClient)
    assert exc.value.status == 400


def test_missing_class_does_not_substitute_another():
    with pytest.raises(SecApiError):
        quote_service.get_quote({"asset_type": "fund", "symbol": "SCBNDQ", "class": "WRONG"}, DemoClient)


def test_exact_match_required():
    with pytest.raises(SecApiError, match="ตรงกับ"):
        fund_service.resolve_fund(DemoClient(), "SCBN")


def test_class_search_falls_back_to_project_abbreviation():
    class Client:
        def fetch_all(self, path, params, **kwargs):
            assert path == ENDPOINTS["profiles"]
            if params["project_info"] == "SCBNDQ":
                return [{"proj_id": "M1", "proj_abbr_name": "SCBNDQ", "fund_class_name": "SCBNDQ(A)", "fund_status": "Registered"}]
            return []
    fund = fund_service.resolve_fund(Client(), "SCBNDQ(A)")
    assert fund["proj_id"] == "M1" and fund["matched_class"] == "SCBNDQ(A)"


def test_missing_nav_cannot_build_as_real():
    class EmptyNAV(DemoClient):
        def fetch_all(self, path, params=None, **kwargs):
            if path == ENDPOINTS["nav"]:
                return []
            return super().fetch_all(path, params, **kwargs)
    with pytest.raises(SecApiError, match="NAV|หน่วยลงทุน"):
        fund_service.build_fund_bundle(EmptyNAV(), "SCBNDQ(A)")


def test_current_renamed_fund_requires_exact_share_class():
    class Client:
        def fetch_all(self, path, params, **kwargs):
            if params["project_info"] == "KF-QUALITY":
                return [{"proj_id": "M0317_2559", "proj_abbr_name": "KF-QUALITY",
                         "fund_class_name": c, "fund_status": "Registered"}
                        for c in ("KF-QUALITY-D", "KF-QUALITY-A")]
            return []
    assert fund_service.resolve_fund(Client(), "KF-QUALITY-A")["matched_class"] == "KF-QUALITY-A"
    with pytest.raises(SecApiError):
        fund_service.resolve_fund(Client(), "KFGBRAND-A")


def test_fund_bundle_does_not_mix_class_dividends_fees_or_links():
    class MixedClient(DemoClient):
        def fetch_all(self, path, params=None, **kwargs):
            if path == ENDPOINTS['dividend_history']:
                return [{'fund_class_name': 'SCBNDQ(P)', 'dividend_value': 99},
                        {'dividend_value': 88}]
            if path == ENDPOINTS['factsheet_urls']:
                return [{'fund_class_name': 'SCBNDQ(P)', 'amc_url_factsheet': 'wrong-class'},
                        {'pdf_factsheet': 'project-pdf', 'amc_url_factsheet': 'unclassified'},
                        {'fund_class_name': 'SCBNDQ(A)', 'amc_url_factsheet': 'correct-class'}]
            if path == ENDPOINTS['mutual_fund_fees']:
                return [{'fund_class_name': 'SCBNDQ(P)', 'rate': 99},
                        {'fund_class_name': 'SCBNDQ(A)', 'rate': 1}]
            return super().fetch_all(path, params, **kwargs)
    b = fund_service.build_fund_bundle(MixedClient(), 'SCBNDQ(A)')
    assert b['dividend_history'] == []
    assert b['dividend_history_note']
    assert [r['rate'] for r in b['amc_fees']] == [1]
    assert [r['amc_url'] for r in b['factsheet_urls']] == [None, 'correct-class']


def test_class_specific_dividends_are_retained():
    rows = [{'fund_class_name': 'A', 'dividend_value': 1},
            {'fund_class_name': 'D', 'dividend_value': 2}, {'dividend_value': 3}]
    assert fund_service._class_rows(rows, 'D', False) == [rows[1]]
