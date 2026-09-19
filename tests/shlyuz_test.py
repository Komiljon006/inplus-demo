"""Shlyuz (N1 SMS + N2 Telegram) — §5 qabul mezonlari.

`Shlyuz` klassi to'g'ridan-to'g'ri import qilinadi (HTTP serversiz) — har bir
vaqtga bog'liq metod ixtiyoriy `hozir` parametrini qabul qiladi, shu sababli
testlar haqiqiy vaqtni kutmaydi (dakikalar o'rniga aniq `datetime` beriladi).
"""
import importlib.util
import threading
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

from inplus import konfig

ILDIZ = Path(__file__).resolve().parents[1]


def _modul_yukla(nom, fayl):
    spec = importlib.util.spec_from_file_location(nom, fayl)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


shlyuz_main = _modul_yukla("shlyuz_main", ILDIZ / "agents" / "shlyuz" / "main.py")
Shlyuz = shlyuz_main.Shlyuz


# ----------------------------------------------------------------------
# yordamchilar
# ----------------------------------------------------------------------
def _xom(agent="TEST", kanal="tg", kimga=None, skript="S-999",
         oz=None, idem=None, muhimlik="oddiy", til="uz"):
    return {
        "kimdan_agent": agent,
        "kanal": kanal,
        "kimga": kimga or {"tur": "xodim", "id": "X-001",
                           "telegram_id": 111111111, "telefon": None},
        "skript_id": skript,
        "til": til,
        "ozgaruvchilar": oz or {"matn": "salom"},
        "idempotent_kalit": idem or f"TEST:{uuid.uuid4()}",
        "muhimlik": muhimlik,
    }


@pytest.fixture()
def shlyuz(tmp_path):
    s = Shlyuz(db_yol=tmp_path / "shlyuz_test.db")
    yield s
    s.yop()


@pytest.fixture(scope="module")
def ets_server():
    from mock import ets_server as ets_mod
    srv = ets_mod.ThreadingHTTPServer(("127.0.0.1", 8472), ets_mod.Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield srv
    srv.shutdown()
    th.join(timeout=2)


@pytest.fixture()
def ets_ok(ets_server, monkeypatch):
    monkeypatch.setenv("ETS_MOCK_REJIM", "ok")
    monkeypatch.setenv("ETS_MOCK_URL", "http://127.0.0.1:8472")
    yield


# ----------------------------------------------------------------------
# asosiy yo'l: navbatda -> yuborildi (tg, mock)
# ----------------------------------------------------------------------
def test_xabar_navbatga_qoyiladi_va_yuboriladi(shlyuz):
    hozir = konfig.hozir()
    kod, javob = shlyuz.qayta_ishla_sorov(_xom(), hozir=hozir)
    assert kod == 200
    assert javob["holat"] == "navbatda"
    xabar_id = javob["xabar_id"]

    shlyuz.navbatni_ishla(hozir=hozir)
    row = shlyuz.holat(xabar_id)
    assert row["holat"] == "yuborildi"
    assert str(row["provayder_id"]).startswith("mock-tg-")


# ----------------------------------------------------------------------
# (1) idempotent dublikat — aynan bitta so'rov qayta yuborilsa
# ----------------------------------------------------------------------
def test_idempotent_dublikat(shlyuz):
    hozir = konfig.hozir()
    idem = f"TEST:{uuid.uuid4()}"
    kod1, javob1 = shlyuz.qayta_ishla_sorov(_xom(idem=idem), hozir=hozir)
    assert javob1["holat"] == "navbatda"

    kod2, javob2 = shlyuz.qayta_ishla_sorov(_xom(idem=idem), hozir=hozir)
    assert kod2 == 200
    assert javob2["holat"] == "dublikat"
    assert javob2["xabar_id"] == javob1["xabar_id"]

    # ikkinchi so'rov yangi qator YARATMAGAN
    with shlyuz.lock:
        n = shlyuz.conn.execute(
            "SELECT COUNT(*) FROM xabarlar WHERE idempotent_kalit=?", (idem,)
        ).fetchone()[0]
    assert n == 1


def test_dublikat_soat_content_asosida(shlyuz):
    """Har xil idempotent_kalit, lekin bir xil manzil+skript — dublikat_soat ushlaydi."""
    hozir = konfig.hozir()
    kimga = {"tur": "xodim", "id": "X-002", "telegram_id": 987654321, "telefon": None}
    oz = {"ism": "Test", "kurs": "Kurs", "summa": "1", "sana": "1-oktyabr"}

    kod1, javob1 = shlyuz.qayta_ishla_sorov(
        _xom(kanal="tg", kimga=kimga, skript="S-001", oz=oz), hozir=hozir)
    assert javob1["holat"] == "navbatda"

    kod2, javob2 = shlyuz.qayta_ishla_sorov(
        _xom(kanal="tg", kimga=kimga, skript="S-001", oz=oz),
        hozir=hozir + timedelta(minutes=1))
    assert javob2 == {"holat": "rad", "sabab": "DUBLIKAT"}


# ----------------------------------------------------------------------
# (2) oq ro'yxatda yo'q manzil -> rad
# ----------------------------------------------------------------------
def test_oq_royxatda_yoq_rad(shlyuz):
    hozir = konfig.hozir()
    kimga = {"tur": "xodim", "id": "notanish", "telegram_id": 555555555, "telefon": None}
    kod, javob = shlyuz.qayta_ishla_sorov(_xom(kimga=kimga), hozir=hozir)
    assert javob == {"holat": "rad", "sabab": "OQ_ROYXAT"}


# ----------------------------------------------------------------------
# (3) ozgaruvchi yetishmasa -> rad
# ----------------------------------------------------------------------
def test_ozgaruvchi_yetishmaydi(shlyuz):
    hozir = konfig.hozir()
    kimga = {"tur": "xodim", "id": "X-003", "telegram_id": 123456789, "telefon": None}
    # S-001 uchun ism/kurs/summa/sana kerak — "sana" yo'q
    oz = {"ism": "Bekzod", "kurs": "Buxgalter", "summa": "1 200 000"}
    kod, javob = shlyuz.qayta_ishla_sorov(
        _xom(kanal="tg", kimga=kimga, skript="S-001", oz=oz), hozir=hozir)
    assert javob == {"holat": "rad", "sabab": "OZGARUVCHI_YETISHMAYDI"}


# ----------------------------------------------------------------------
# (4) SMS matni uzun -> rad SMS_UZUN
# ----------------------------------------------------------------------
def test_sms_uzun_rad(shlyuz):
    hozir = konfig.hozir()
    kimga = {"tur": "xodim", "id": "X-004", "telefon": "+998935550011",
             "telegram_id": None}
    oz = {"ism": "Bekzod", "kurs": "x" * 200, "summa": "1 200 000", "sana": "1-oktyabr"}
    kod, javob = shlyuz.qayta_ishla_sorov(
        _xom(kanal="sms", kimga=kimga, skript="S-001", oz=oz), hozir=hozir)
    assert javob == {"holat": "rad", "sabab": "SMS_UZUN"}


# ----------------------------------------------------------------------
# (5) vaqt_oynasi tashqarisida -> navbatda (rad EMAS), keyingi_urinish oyna boshi
# ----------------------------------------------------------------------
def test_vaqt_oynasi_kechiktiradi(shlyuz):
    hozir_kech = konfig.hozir().replace(hour=22, minute=30, second=0, microsecond=0)
    kimga = {"tur": "xodim", "id": "X-005", "telegram_id": 111111111, "telefon": None}
    oz = {"ism": "Bekzod", "kurs": "Kurs", "summa": "1", "sana": "1-oktyabr"}
    kod, javob = shlyuz.qayta_ishla_sorov(
        _xom(kanal="tg", kimga=kimga, skript="S-001", oz=oz), hozir=hozir_kech)
    assert javob["holat"] == "navbatda"
    xabar_id = javob["xabar_id"]

    row = shlyuz.holat(xabar_id)
    keyingi = row["keyingi_urinish"]
    assert keyingi is not None
    assert "09:00:00" in keyingi

    # oyna tashqarisida ishchi jo'natmaydi
    shlyuz.navbatni_ishla(hozir=hozir_kech)
    row = shlyuz.holat(xabar_id)
    assert row["holat"] == "navbatda"

    # ertangi 09:00 da yuboriladi
    ertaga_09 = (hozir_kech + timedelta(days=1)).replace(hour=9, minute=0, second=0)
    shlyuz.navbatni_ishla(hozir=ertaga_09)
    row = shlyuz.holat(xabar_id)
    assert row["holat"] == "yuborildi"


def test_vaqt_oynasi_kritik_darhol(shlyuz):
    hozir_kech = konfig.hozir().replace(hour=22, minute=30, second=0, microsecond=0)
    kimga = {"tur": "xodim", "id": "X-006", "telegram_id": 987654321, "telefon": None}
    oz = {"ism": "Bekzod", "kurs": "Kurs", "summa": "1", "sana": "1-oktyabr"}
    kod, javob = shlyuz.qayta_ishla_sorov(
        _xom(kanal="tg", kimga=kimga, skript="S-001", oz=oz, muhimlik="kritik"),
        hozir=hozir_kech)
    row = shlyuz.holat(javob["xabar_id"])
    assert row["keyingi_urinish"] <= konfig.iso(hozir_kech)
    shlyuz.navbatni_ishla(hozir=hozir_kech)
    row = shlyuz.holat(javob["xabar_id"])
    assert row["holat"] == "yuborildi"


# ----------------------------------------------------------------------
# (6) SMS ЕТС 429 -> eksponensial retry, keyin `ok` ga o'tkazilsa yuboriladi
# ----------------------------------------------------------------------
def test_sms_429_retry_keyin_ok(shlyuz, ets_server, monkeypatch):
    monkeypatch.setenv("ETS_MOCK_URL", "http://127.0.0.1:8472")
    monkeypatch.setenv("ETS_MOCK_REJIM", "429")

    hozir = konfig.hozir()
    kimga = {"tur": "xodim", "id": "X-007", "telefon": "+998900000001",
             "telegram_id": None}
    kod, javob = shlyuz.qayta_ishla_sorov(
        _xom(kanal="sms", kimga=kimga, skript="S-999", oz={"matn": "test"}),
        hozir=hozir)
    xabar_id = javob["xabar_id"]

    shlyuz.navbatni_ishla(hozir=hozir)
    row = shlyuz.holat(xabar_id)
    assert row["holat"] == "navbatda"
    assert row["urinish"] == 1
    assert row["keyingi_urinish"] is not None

    from datetime import datetime
    keyingi = datetime.fromisoformat(row["keyingi_urinish"])

    monkeypatch.setenv("ETS_MOCK_REJIM", "ok")
    shlyuz.navbatni_ishla(hozir=keyingi + timedelta(seconds=1))
    row = shlyuz.holat(xabar_id)
    assert row["holat"] == "yuborildi"
    assert row["narx_som"] == 95
    assert str(row["provayder_id"]).startswith("mock-ets-")


# ----------------------------------------------------------------------
# (7) SMS ЕТС 500 -> 5 urinishdan keyin xato + shlyuzning ichki S-900 ogohlantirishi
# ----------------------------------------------------------------------
def test_sms_500_besh_urinishdan_keyin_xato(shlyuz, ets_server, monkeypatch):
    monkeypatch.setenv("ETS_MOCK_URL", "http://127.0.0.1:8472")
    monkeypatch.setenv("ETS_MOCK_REJIM", "500")

    from datetime import datetime

    hozir = konfig.hozir()
    kimga = {"tur": "xodim", "id": "X-008", "telefon": "+998901112233",
             "telegram_id": None}
    kod, javob = shlyuz.qayta_ishla_sorov(
        _xom(kanal="sms", kimga=kimga, skript="S-999", oz={"matn": "test"}),
        hozir=hozir)
    xabar_id = javob["xabar_id"]

    for _ in range(5):
        row = shlyuz.holat(xabar_id)
        if row["holat"] != "navbatda":
            break
        hozir = datetime.fromisoformat(row["keyingi_urinish"]) + timedelta(seconds=1) \
            if row["keyingi_urinish"] else hozir
        shlyuz.navbatni_ishla(hozir=hozir)

    row = shlyuz.holat(xabar_id)
    assert row["holat"] == "xato"
    assert row["urinish"] == shlyuz_main.MAX_URINISH

    with shlyuz.lock:
        ichki = shlyuz.conn.execute(
            "SELECT * FROM xabarlar WHERE skript_id='S-900' AND kimdan_agent='SHLYUZ'"
        ).fetchone()
    assert ichki is not None


# ----------------------------------------------------------------------
# skript topilmadi / arxiv / kanal ruxsatsiz / agent ruxsatsiz
# ----------------------------------------------------------------------
def test_skript_yoq(shlyuz):
    kod, javob = shlyuz.qayta_ishla_sorov(_xom(skript="S-777"), hozir=konfig.hozir())
    assert javob == {"holat": "rad", "sabab": "SKRIPT_YOQ"}


def test_agent_ruxsat_yoq(shlyuz):
    # S-900 faqat X2/X1/D1/D6/N3/SHLYUZ ruxsat etilgan
    kimga = {"tur": "xodim", "id": "X-001", "telegram_id": 111111111, "telefon": None}
    oz = {"agent": "X2", "xabar": "test", "vaqt": konfig.iso()}
    kod, javob = shlyuz.qayta_ishla_sorov(
        _xom(agent="NOTANISH", kanal="tg", kimga=kimga, skript="S-900", oz=oz),
        hozir=konfig.hozir())
    assert javob == {"holat": "rad", "sabab": "AGENT_RUXSAT_YOQ"}


def test_kanal_yoq(shlyuz):
    # S-902 faqat "tg" ruxsat etilgan
    kimga = {"tur": "xodim", "id": "X-004", "telefon": "+998935550011",
             "telegram_id": None}
    oz = {"soni": "1", "royxat": "9-qator"}
    kod, javob = shlyuz.qayta_ishla_sorov(
        _xom(agent="D6", kanal="sms", kimga=kimga, skript="S-902", oz=oz),
        hozir=konfig.hozir())
    assert javob == {"holat": "rad", "sabab": "KANAL_YOQ"}


# ----------------------------------------------------------------------
# schema xato
# ----------------------------------------------------------------------
def test_sxema_xato(shlyuz):
    xom = _xom()
    xom["kanal"] = "email"  # schema enum'da yo'q
    kod, javob = shlyuz.qayta_ishla_sorov(xom, hozir=konfig.hozir())
    assert javob["holat"] == "rad"
    assert javob["sabab"] == "SXEMA_XATO"


# ----------------------------------------------------------------------
# statistika / holat
# ----------------------------------------------------------------------
def test_statistika_va_holat(shlyuz):
    hozir = konfig.hozir()
    kod, javob = shlyuz.qayta_ishla_sorov(_xom(), hozir=hozir)
    shlyuz.navbatni_ishla(hozir=hozir)
    st = shlyuz.statistika()
    assert st["jami"] >= 1
    row = shlyuz.holat(javob["xabar_id"])
    assert row["xabar_id"] == javob["xabar_id"]
    assert shlyuz.holat("x-yoq-000000") is None
