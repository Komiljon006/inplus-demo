"""S4 (Menejer nazorati) — 2-blok «Sotuv va CRM» qabul mezonlari.

Poydevorga (kontrakt/, lib/) tegilmagan — S4 faqat `paket.oqi()` orqali
o'qiydi, xuddi S2/S6/X3 kabi (tests/blok2_test.py va tests/tahlil_test.py
bilan bir xil naqsh: mock generator + haqiqiy D6->D1 quvuri bilan
`data/paket/joriy.json` tayyorlanadi, so'ng S4.ish() to'g'ridan-to'g'ri
chaqiriladi va natija PAKETNING O'ZIDAN mustaqil ravishda qayta
hisoblangan qiymatlar bilan solishtiriladi — hech qanday raqam bu faylda
ham hardcode qilinmagan)."""
import importlib.util
import os
import shutil
import subprocess
import sys
from datetime import date, datetime

import pytest

from inplus import konfig, fayl, paket

ILDIZ = konfig.ILDIZ
SANA = konfig.bugun()  # S4 doim joriy.json'ni o'qiydi — sana shu bilan mos


def _modul_yukla(nom, yol):
    spec = importlib.util.spec_from_file_location(nom, yol)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _toza_paket_tayyorla():
    """data/ va run/heartbeat/ ni tozalab, mock+D6+D1 bilan haqiqiy joriy
    paket yaratadi (deterministik: urug=42, kun=0 — tests/blok2_test.py va
    tests/tahlil_test.py bilan bir xil urug)."""
    shutil.rmtree(ILDIZ / "data", ignore_errors=True)
    shutil.rmtree(ILDIZ / "run" / "heartbeat", ignore_errors=True)
    (ILDIZ / "data").mkdir(parents=True, exist_ok=True)
    (ILDIZ / "run" / "heartbeat").mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(ILDIZ))
    from mock import generator
    generator.main(["--lid", "400", "--talaba", "260", "--urug", "42", "--kun", "0"])

    csv = ILDIZ / "mock" / "sheets" / "jadval.csv"
    matn = csv.read_text(encoding="utf-8").replace("31.09.2026", "30.09.2026")
    csv.write_text(matn, encoding="utf-8")

    env = dict(os.environ)
    env["INPLUS_ILDIZ"] = str(ILDIZ)
    env["INPLUS_SHLYUZ_PORT"] = "18471"
    env.pop("INPLUS_MOCK_YIQIL", None)

    d6 = subprocess.run([sys.executable, str(ILDIZ / "agents" / "d6_jadval" / "main.py"),
                        "--bir-marta", "--sana", SANA],
                        cwd=str(ILDIZ), env=env, capture_output=True, text=True)
    assert d6.returncode == 0, f"D6 yiqildi: {d6.stdout}\n{d6.stderr}"

    d1 = subprocess.run([sys.executable, str(ILDIZ / "agents" / "d1_sborshik" / "main.py"),
                        "--bir-marta", "--sana", SANA],
                        cwd=str(ILDIZ), env=env, capture_output=True, text=True)
    assert d1.returncode == 0, f"D1 yiqildi: {d1.stdout}\n{d1.stderr}"

    assert paket.joriy_yol().exists()


@pytest.fixture(scope="module")
def s4_mod():
    return _modul_yukla("s4_nazorat_main", ILDIZ / "agents" / "s4_nazorat" / "main.py")


@pytest.fixture(scope="module", autouse=True)
def _paket_tayyor():
    _toza_paket_tayyorla()
    yield


@pytest.fixture(scope="module")
def joriy_paket():
    return paket.oqi("TEST")


@pytest.fixture(scope="module")
def nazorat(s4_mod):
    agent = s4_mod.S4(sana=SANA)
    natija = agent.ish()
    obj = fayl.json_oqi(konfig.data("nazorat.json"))
    return obj, natija


def _tegilmagan_mustaqil(lid):
    """javobsiz mezonini paket ma'lumotidan MUSTAQIL qayta hisoblaydi
    (agent kodidan chaqirmasdan) — testning o'zi mustaqil bo'lishi uchun."""
    if lid.get("bosqich") != "yangi":
        return False
    oxirgi = lid.get("oxirgi_aloqa")
    yaratildi = lid.get("yaratildi")
    return oxirgi is None or oxirgi == yaratildi


def _ishlangan_mustaqil(lid):
    yaratildi = lid.get("yaratildi")
    oxirgi = lid.get("oxirgi_aloqa")
    if not yaratildi or not oxirgi:
        return False
    return datetime.fromisoformat(oxirgi) > datetime.fromisoformat(yaratildi)


# ==========================================================================
# menejerlar — lid yig'indisi
# ==========================================================================

def test_menejer_lid_yigindisi_paket_lidlar_soniga_teng(nazorat, joriy_paket):
    obj, _ = nazorat
    lidlar = joriy_paket["lidlar"]
    kutilgan_jami = sum(1 for l in lidlar if l.get("menejer_id"))
    haqiqiy_jami = sum(m["lid"] for m in obj["menejerlar"])
    assert haqiqiy_jami == kutilgan_jami
    assert haqiqiy_jami == len(lidlar), "mock'da har lid uchun menejer_id bor bo'lishi kerak"

    for m in obj["menejerlar"]:
        assert m["ism"], "ism xodimlar ro'yxatidan to'ldirilishi kerak"
        assert m["ishlangan"] <= m["lid"]
        assert m["javobsiz"] <= m["lid"]


# ==========================================================================
# javobsiz — faqat tegmagan "yangi" lidlar
# ==========================================================================

def test_javobsiz_faqat_tegmagan_yangi_lidlarga_teng(nazorat, joriy_paket):
    """Har menejerning `javobsiz` soni, o'sha menejerga biriktirilgan
    lidlar orasida `bosqich=="yangi"` va tegilmaganlar soniga aynan teng."""
    obj, _ = nazorat
    kutilgan = {}
    for l in joriy_paket["lidlar"]:
        mid = l.get("menejer_id")
        if not mid:
            continue
        kutilgan.setdefault(mid, 0)
        if _tegilmagan_mustaqil(l):
            kutilgan[mid] += 1
    haqiqiy = {m["id"]: m["javobsiz"] for m in obj["menejerlar"]}
    assert haqiqiy == kutilgan

    # javobsiz_lidlar ro'yxatidagi HAR bir yozuv haqiqatan ham
    # bosqich="yangi" va tegilmagan lidga mos kelishi kerak
    lid_xarita = {l["lid_id"]: l for l in joriy_paket["lidlar"]}
    assert obj["javobsiz_lidlar"], "mock'da javobsiz lid bo'lishi kerak"
    for r in obj["javobsiz_lidlar"]:
        lid = lid_xarita[r["lid_id"]]
        assert lid["bosqich"] == "yangi"
        assert _tegilmagan_mustaqil(lid)


def test_javobsiz_jami_togri_hisoblanadi(nazorat, joriy_paket):
    obj, natija = nazorat
    kutilgan_jami = sum(1 for l in joriy_paket["lidlar"] if _tegilmagan_mustaqil(l))
    assert obj["jami"]["javobsiz_jami"] == kutilgan_jami
    assert obj["jami"]["javobsiz_jami"] == sum(m["javobsiz"] for m in obj["menejerlar"])
    assert natija["kpi"]["javobsiz_jami"] == kutilgan_jami
    assert kutilgan_jami > 0, "mock'da javobsiz lid bo'lishi kerak (aks holda test hech nima sinamaydi)"


# ==========================================================================
# reaksiya_soat — mantiqan to'g'ri
# ==========================================================================

def test_reaksiya_soat_mantiqan_togri(nazorat, joriy_paket):
    """`reaksiya_soat` musbat, va mock generatordagi profilga mos: X-301
    tez, X-302 o'rta, X-303 sekin (agar barcha uchtasi ham lid olsa)."""
    obj, _ = nazorat
    xarita = {m["id"]: m["reaksiya_soat"] for m in obj["menejerlar"]}
    for m in obj["menejerlar"]:
        if m["ishlangan"] > 0:
            assert m["reaksiya_soat"] is not None
            assert m["reaksiya_soat"] > 0
        else:
            assert m["reaksiya_soat"] is None

    if {"X-301", "X-302", "X-303"} <= xarita.keys():
        assert xarita["X-301"] < xarita["X-302"] < xarita["X-303"], (
            "mock generator: X-301 tez, X-302 o'rta, X-303 sekin bo'lishi kerak "
            f"(haqiqiy: {xarita})")

    # o'rtacha reaksiya paketdan mustaqil qayta hisoblab tekshiriladi
    diffs = []
    for l in joriy_paket["lidlar"]:
        if _ishlangan_mustaqil(l):
            yar = datetime.fromisoformat(l["yaratildi"])
            oxr = datetime.fromisoformat(l["oxirgi_aloqa"])
            diffs.append((oxr - yar).total_seconds() / 3600)
    assert diffs, "mock'da ishlangan (aloqa qilingan) lid bo'lishi kerak"


# ==========================================================================
# javobsiz_lidlar — tartib
# ==========================================================================

def test_javobsiz_lidlar_kamayish_tartibida_va_top_15(nazorat):
    obj, _ = nazorat
    royxat = obj["javobsiz_lidlar"]
    assert len(royxat) <= 15
    kunlar = [r["kun_javobsiz"] for r in royxat]
    assert kunlar == sorted(kunlar, reverse=True), \
        "eng ko'p kun javobsiz turgan lid birinchi bo'lishi kerak"
    for r in royxat:
        assert r["kun_javobsiz"] is not None and r["kun_javobsiz"] >= 0


# ==========================================================================
# Fayl / KPI / reestr
# ==========================================================================

def test_nazorat_json_fayli_va_kpi_yoziladi(nazorat):
    obj, natija = nazorat
    assert obj["versiya"] == "1.0"
    assert obj["sana"] == SANA
    assert konfig.data("nazorat.json").exists()
    assert natija["kpi"]["menejerlar"] == len(obj["menejerlar"])
    assert natija["kpi"]["javobsiz_lidlar_royxatda"] == len(obj["javobsiz_lidlar"])
    assert natija["kpi"]["ortacha_reaksiya_soat"] == obj["jami"]["ortacha_reaksiya_soat"]


def test_agentlar_json_s4_royxatda():
    reestr = konfig.konfig_json("agentlar.json")
    assert "S4" in reestr, "S4 konfig/agentlar.json ga qo'shilmagan"
    meta = reestr["S4"]
    assert meta["tur"] == "timer"
    assert "paket" in meta.get("oqiydi", [])
    assert meta.get("egasi")
    assert meta.get("ijro") == "И0"
    assert meta.get("rol") == "kontrolyor"
    # poydevor + boshqa 2-blok yozuvlariga tegilmaganini tekshiramiz
    for aid in ("D1", "D6", "SHLYUZ", "N3", "X2", "X1", "W1", "X0", "S2", "S6", "X3"):
        assert aid in reestr
