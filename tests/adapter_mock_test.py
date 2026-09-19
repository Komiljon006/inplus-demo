"""Mock adapterlar REAL API JAVOB FORMATIDA qaytaradi."""
import os

import pytest

from inplus import adapter, konfig
from mock import generator


@pytest.fixture(scope="module", autouse=True)
def _mock_bor():
    # mock fayllar bo'lmasa yasaymiz (deterministik)
    if not konfig.mock_yol("amocrm", "leads.json").exists():
        generator.main(["--urug", "42"])
    os.environ["INPLUS_REJIM"] = "mock"


def test_amocrm_format():
    a = adapter.ol("amocrm")
    assert type(a).__name__ == "MockAmoCRM"
    leads = a.lidlar()
    assert "_embedded" in leads and "leads" in leads["_embedded"]
    lid = leads["_embedded"]["leads"][0]
    assert "status_id" in lid and "custom_fields_values" in lid
    users = a.xodimlar()
    assert "_embedded" in users and "users" in users["_embedded"]


def test_getcourse_format():
    g = adapter.ol("getcourse")
    assert type(g).__name__ == "MockGetCourse"
    tal = g.talabalar()
    assert tal["success"] is True
    assert "fields" in tal["data"] and "rows" in tal["data"]


def test_sheets_format():
    s = adapter.ol("sheets")
    varaq = s.varaq("x", "Jadval")
    assert isinstance(varaq, list) and isinstance(varaq[0], list)
    assert len(varaq[0]) == 13   # 13 ustun
    assert len(varaq) == 15      # sarlavha + 14 qator


def test_telegram_mock():
    os.environ["TG_REAL"] = "0"
    t = adapter.ol("telegram")
    assert type(t).__name__ == "MockTelegram"
    r = t.yubor(111111111, "salom")
    assert r["holat"] == "ok" and str(r["provayder_id"]).startswith("mock-tg")


def test_sms_real_himoya():
    # real rejim + token yo'q -> RuntimeError (SMS adashib ketmasin)
    os.environ["INPLUS_REJIM"] = "real"
    os.environ.pop("ETS_TOKEN", None)
    with pytest.raises(RuntimeError):
        adapter.ol("sms")
    os.environ["INPLUS_REJIM"] = "mock"
