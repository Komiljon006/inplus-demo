"""X3 (Analitika hisoboti) — 2-blok «Sotuv va CRM» qabul mezonlari.

Poydevorga (kontrakt/, lib/) tegilmagan — X3 faqat `paket.oqi()` orqali
o'qiydi, xuddi S2/S6 kabi (tests/blok2_test.py bilan bir xil naqsh: mock
generator + haqiqiy D6->D1 quvuri bilan `data/paket/joriy.json` tayyorlanadi,
so'ng X3.ish() to'g'ridan-to'g'ri chaqiriladi va natija PAKETNING O'ZIDAN
mustaqil ravishda qayta hisoblangan qiymatlar bilan solishtiriladi — hech
qanday raqam bu faylda ham hardcode qilinmagan)."""
import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

from inplus import konfig, fayl, paket

ILDIZ = konfig.ILDIZ
SANA = konfig.bugun()  # X3 doim joriy.json'ni o'qiydi — sana shu bilan mos


def _modul_yukla(nom, yol):
    spec = importlib.util.spec_from_file_location(nom, yol)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _toza_paket_tayyorla():
    """data/ va run/heartbeat/ ni tozalab, mock+D6+D1 bilan haqiqiy joriy
    paket yaratadi (deterministik: urug=42, kun=0 — tests/blok2_test.py
    bilan bir xil urug)."""
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
def x3_mod():
    return _modul_yukla("x3_tahlil_main", ILDIZ / "agents" / "x3_tahlil" / "main.py")


@pytest.fixture(scope="module", autouse=True)
def _paket_tayyor():
    _toza_paket_tayyorla()
    yield


@pytest.fixture(scope="module")
def joriy_paket():
    return paket.oqi("TEST")


@pytest.fixture(scope="module")
def tahlil(x3_mod):
    agent = x3_mod.X3(sana=SANA)
    natija = agent.ish()
    obj = fayl.json_oqi(konfig.data("tahlil.json"))
    return obj, natija


# ==========================================================================
# kunlik_tushum
# ==========================================================================

def test_kunlik_tushum_yigindisi_paketdagi_umumiy_tolangan_summaga_teng(tahlil, joriy_paket):
    obj, _ = tahlil
    kutilgan = sum(t.get("summa") or 0 for t in joriy_paket["tolovlar"])
    haqiqiy = sum(r["summa"] for r in obj["kunlik_tushum"])
    assert haqiqiy == kutilgan
    assert haqiqiy > 0, "mock to'lovlar bo'lishi shart (aks holda test hech narsani sinamaydi)"
    # tartiblangan (o'sish tartibida) bo'lishi shart
    sanalar = [r["sana"] for r in obj["kunlik_tushum"]]
    assert sanalar == sorted(sanalar)
    # ~30-45 kunga tarqalgan (bitta kunda emas)
    assert len(obj["kunlik_tushum"]) >= 20, "sanalar bitta kunga to'planib qolmasligi kerak"


# ==========================================================================
# kurs_daromadi
# ==========================================================================

def test_kurs_daromadi_talabalar_tolov_jami_bilan_mos_va_kamayish_tartibida(tahlil, joriy_paket):
    obj, _ = tahlil
    hisob = {}
    for t in joriy_paket["talabalar"]:
        kurs_id = t.get("kurs_id")
        if not kurs_id:
            continue
        hisob[kurs_id] = hisob.get(kurs_id, 0) + (t.get("tolov") or {}).get("jami", 0)

    haqiqiy = {r["kurs_id"]: r["summa"] for r in obj["kurs_daromadi"]}
    assert haqiqiy == hisob
    summalar = [r["summa"] for r in obj["kurs_daromadi"]]
    assert summalar == sorted(summalar, reverse=True), "kamayish tartibida bo'lishi kerak"
    for r in obj["kurs_daromadi"]:
        assert r["nom"], "kurs nomi bo'sh bo'lmasligi kerak"


# ==========================================================================
# menejerlar
# ==========================================================================

def test_menejerlar_lid_yigindisi_paket_lidlar_soniga_teng(tahlil, joriy_paket):
    obj, _ = tahlil
    lidlar = joriy_paket["lidlar"]
    kutilgan_jami = sum(1 for l in lidlar if l.get("menejer_id"))
    haqiqiy_jami = sum(m["lid"] for m in obj["menejerlar"])
    assert haqiqiy_jami == kutilgan_jami
    assert haqiqiy_jami == len(lidlar), "mock'da har lid uchun menejer_id bor bo'lishi kerak"

    for m in obj["menejerlar"]:
        assert m["ism"], "ism xodimlar ro'yxatidan to'ldirilishi kerak"
        assert 0.0 <= m["konv"] <= 1.0
        assert m["sotildi"] <= m["lid"]


def test_menejerlar_sotildi_togri_sanaladi(tahlil, joriy_paket):
    obj, _ = tahlil
    kutilgan = {}
    for l in joriy_paket["lidlar"]:
        mid = l.get("menejer_id")
        if not mid:
            continue
        kutilgan[mid] = kutilgan.get(mid, 0) + (1 if l.get("bosqich") == "sotildi" else 0)
    haqiqiy = {m["id"]: m["sotildi"] for m in obj["menejerlar"]}
    assert haqiqiy == kutilgan


# ==========================================================================
# orqada
# ==========================================================================

def test_orqada_faqat_past_korsatkichli_faol_talabalar(tahlil, joriy_paket):
    obj, _ = tahlil
    talaba_xarita = {t["talaba_id"]: t for t in joriy_paket["talabalar"]}

    assert len(obj["orqada"]) > 0, "mock'da orqada qolgan talaba bo'lishi kerak"
    for r in obj["orqada"]:
        t = talaba_xarita[r["talaba_id"]]
        assert t["holat"] == "faol"
        davomat = t.get("davomat_foiz")
        progress = t.get("progress_foiz")
        past_davomat = davomat is not None and davomat < 60
        past_progress = progress is not None and progress < 25
        assert past_davomat or past_progress
        if past_davomat:
            assert "davomat" in r["sabab"]
        if past_progress:
            assert "progress" in r["sabab"]

    # hech bir "yaxshi" faol talaba (past ko'rsatkichsiz) ro'yxatga tushmagan
    orqada_idlar = {r["talaba_id"] for r in obj["orqada"]}
    for t in joriy_paket["talabalar"]:
        if t["holat"] != "faol":
            continue
        davomat = t.get("davomat_foiz")
        progress = t.get("progress_foiz")
        yaxshi = (davomat is None or davomat >= 60) and (progress is None or progress >= 25)
        if yaxshi:
            assert t["talaba_id"] not in orqada_idlar


# ==========================================================================
# nps
# ==========================================================================

def test_nps_ball_formulasi(tahlil, joriy_paket):
    obj, _ = tahlil
    promoter = passiv = kritik = 0
    for t in joriy_paket["talabalar"]:
        xom = t.get("xom") or {}
        raw = xom.get("nps")
        if raw is None or str(raw).strip() == "":
            continue
        ball = int(raw)
        if ball >= 9:
            promoter += 1
        elif ball >= 7:
            passiv += 1
        else:
            kritik += 1
    javob = promoter + passiv + kritik
    kutilgan_ball = round((promoter - kritik) / javob * 100) if javob else 0

    assert obj["nps"]["promoter"] == promoter
    assert obj["nps"]["passiv"] == passiv
    assert obj["nps"]["kritik"] == kritik
    assert obj["nps"]["javob"] == javob
    assert obj["nps"]["ball"] == kutilgan_ball
    assert javob > 0, "mock'da NPS javob berganlar bo'lishi kerak"
    # ba'zi talaba javob bermagan bo'lishi kerak (mock generator shart bilgan)
    assert javob < len(joriy_paket["talabalar"])


# ==========================================================================
# prognoz
# ==========================================================================

def test_prognoz_4_element_va_haftalar_togri(tahlil):
    obj, _ = tahlil
    prognoz = obj["prognoz"]
    assert len(prognoz) == 4
    assert [p["hafta"] for p in prognoz] == ["1-hafta", "2-hafta", "3-hafta", "4-hafta"]
    for p in prognoz:
        assert isinstance(p["summa"], int)
        assert p["summa"] >= 0


# ==========================================================================
# vozvrat
# ==========================================================================

def test_vozvrat_tashladi_va_tolandi_musbat_bolganlar(tahlil, joriy_paket):
    obj, _ = tahlil
    kutilgan = [t for t in joriy_paket["talabalar"]
                if t.get("holat") == "tashladi" and (t.get("tolov") or {}).get("tolandi", 0) > 0]
    kutilgan_summa = sum(t["tolov"]["tolandi"] for t in kutilgan)

    assert obj["vozvrat"]["soni"] == len(kutilgan)
    assert obj["vozvrat"]["summa"] == kutilgan_summa
    assert obj["vozvrat"]["soni"] > 0, "mock'da vozvrat manbai bo'lishi kerak (~5-8%)"


# ==========================================================================
# Fayl / KPI / reestr
# ==========================================================================

def test_tahlil_json_fayli_va_kpi_yoziladi(tahlil):
    obj, natija = tahlil
    assert obj["versiya"] == "1.0"
    assert obj["paket_id"] == SANA
    assert konfig.data("tahlil.json").exists()
    assert natija["kpi"]["kunlar"] == len(obj["kunlik_tushum"])
    assert natija["kpi"]["menejerlar"] == len(obj["menejerlar"])
    assert natija["kpi"]["orqada_soni"] == len(obj["orqada"])
    assert natija["kpi"]["vozvrat_soni"] == obj["vozvrat"]["soni"]


def test_agentlar_json_x3_royxatda():
    reestr = konfig.konfig_json("agentlar.json")
    assert "X3" in reestr, "X3 konfig/agentlar.json ga qo'shilmagan"
    meta = reestr["X3"]
    assert meta["tur"] == "timer"
    assert "paket" in meta.get("oqiydi", [])
    assert meta.get("egasi")
    # poydevor + 2-blok yozuvlariga tegilmaganini tekshiramiz
    for aid in ("D1", "D6", "SHLYUZ", "N3", "X2", "X1", "W1", "X0", "S2", "S6"):
        assert aid in reestr
