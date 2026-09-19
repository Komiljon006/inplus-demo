"""2-blok «Sotuv va CRM» (oson qism) — S2 (voronka hisoboti) va S6
(qarzdorlar eslatmasi) qabul mezonlari.

Poydevorga (kontrakt/, lib/) tegilmagan — bu ikkala agent faqat
`paket.oqi()` orqali o'qiydi, xuddi boshqa 2-N blok agentlari kabi.

Har test o'z sikli boshida mock ma'lumotni deterministik qayta yasaydi
(`--urug 42 --kun 0`, `tests/data_test.py` bilan bir xil naqsh) va real D6+D1
ni ishga tushiradi -> `data/paket/joriy.json` haqiqiy quvur bilan tayyorlanadi.
Shundan keyin S2/S6 `ish()` metodi to'g'ridan-to'g'ri chaqiriladi
(`tests/orkestr_test.py` dagi kabi) — natija dict + yozilgan fayllar tekshiriladi.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
from collections import Counter

import pytest

from inplus import konfig, fayl, paket

ILDIZ = konfig.ILDIZ
SANA = konfig.bugun()  # S2/S6 doim joriy.json'ni o'qiydi — sana shu bilan mos


def _modul_yukla(nom, yol):
    spec = importlib.util.spec_from_file_location(nom, yol)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _toza_paket_tayyorla():
    """data/ va run/heartbeat/ ni tozalab, mock+D6+D1 bilan haqiqiy joriy
    paket yaratadi (deterministik: urug=42, kun=0 -> 400 lid/260 talaba,
    8 bosqichda aynan 50 tadan, tests/data_test.py bilan bir xil urug)."""
    shutil.rmtree(ILDIZ / "data", ignore_errors=True)
    shutil.rmtree(ILDIZ / "run" / "heartbeat", ignore_errors=True)
    (ILDIZ / "data").mkdir(parents=True, exist_ok=True)
    (ILDIZ / "run" / "heartbeat").mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(ILDIZ))
    from mock import generator
    generator.main(["--lid", "400", "--talaba", "260", "--urug", "42", "--kun", "0"])

    # generator har doim 31.09.2026 (mavjud bo'lmagan sana) qo'yadi -> D6 uni
    # "xato" deb belgilaydi va courses.json YANGILANMAYDI. Testda D1 ga
    # to'liq kurslar ro'yxati kerak bo'lgani uchun 30.09.2026 ga tuzatamiz
    # (bin/demo.sh / vazifa ta'rifidagi sed bilan bir xil qadam).
    csv = ILDIZ / "mock" / "sheets" / "jadval.csv"
    matn = csv.read_text(encoding="utf-8").replace("31.09.2026", "30.09.2026")
    csv.write_text(matn, encoding="utf-8")

    env = dict(os.environ)
    env["INPLUS_ILDIZ"] = str(ILDIZ)
    env["INPLUS_SHLYUZ_PORT"] = "18471"  # bu testlar shlyuzdan mustaqil
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
def s2_mod():
    return _modul_yukla("s2_voronka_main", ILDIZ / "agents" / "s2_voronka" / "main.py")


@pytest.fixture(scope="module")
def s6_mod():
    return _modul_yukla("s6_qarz_main", ILDIZ / "agents" / "s6_qarz" / "main.py")


@pytest.fixture(scope="module", autouse=True)
def _paket_tayyor():
    _toza_paket_tayyorla()
    yield


# ==========================================================================
# S2 — Sotuv voronkasi hisoboti
# ==========================================================================

def test_s2_bosqich_taqsimoti_togri_sanaladi(s2_mod):
    """Voronka bosqichlari yig'indisi = paketdagi umumiy lidlar soni, va
    ma'lum urug (42) bilan generator har 8 bosqichga aynan 50 tadan taqsimlaydi."""
    joriy = paket.oqi("TEST")
    jami_lid = len(joriy["lidlar"])
    assert jami_lid == 400

    agent = s2_mod.S2(sana=SANA)
    natija = agent.ish()

    obj = fayl.json_oqi(konfig.data("voronka.json"))
    assert obj["jami_lid"] == jami_lid
    soni_yigindi = sum(b["soni"] for b in obj["bosqichlar"])
    assert soni_yigindi == jami_lid

    # generator: realistik voronka (funnel) — deterministik ulushlar (urug=42, 400 lid)
    kodlar = {b["kod"] for b in obj["bosqichlar"]}
    assert kodlar == {"yangi", "aloqa", "konsultatsiya", "sinov_dars",
                       "tolov_kutish", "sotildi", "qayta", "yoqotildi"}
    kutilgan = {"yangi": 88, "aloqa": 72, "konsultatsiya": 60, "sinov_dars": 48,
                "tolov_kutish": 40, "sotildi": 48, "qayta": 24, "yoqotildi": 20}
    haqiqiy = {b["kod"]: b["soni"] for b in obj["bosqichlar"]}
    assert haqiqiy == kutilgan, f"voronka taqsimoti: {haqiqiy}"

    assert natija["kpi"]["jami_lid"] == jami_lid
    assert natija["kpi"]["sotildi"] == 48


def test_s2_summa_va_kanal_hisobi_togri(s2_mod):
    joriy = paket.oqi("TEST")
    lidlar = joriy["lidlar"]
    kutilgan_jami_summa = sum(l.get("summa") or 0 for l in lidlar)
    kutilgan_kanal = Counter(l.get("manba_kanal") or "noma'lum" for l in lidlar)

    agent = s2_mod.S2(sana=SANA)
    agent.ish()
    obj = fayl.json_oqi(konfig.data("voronka.json"))

    assert obj["jami_summa"] == kutilgan_jami_summa
    kanal_soni = sum(k["soni"] for k in obj["kanallar"])
    assert kanal_soni == len(lidlar)
    for k in obj["kanallar"]:
        assert kutilgan_kanal[k["nom"]] == k["soni"]


def test_s2_fayllar_yoziladi_va_ikki_marta_barqaror(s2_mod):
    """data/voronka/<sana>.json + data/voronka.json ikkalasi ham yoziladi va
    ikki marta ishga tushirilsa bir xil natija chiqadi (idempotent hisob)."""
    agent = s2_mod.S2(sana=SANA)
    n1 = agent.ish()
    obj1 = fayl.json_oqi(konfig.data("voronka", f"{SANA}.json"))
    n2 = agent.ish()
    obj2 = fayl.json_oqi(konfig.data("voronka.json"))

    assert konfig.data("voronka", f"{SANA}.json").exists()
    assert konfig.data("voronka.json").exists()
    assert obj1["bosqichlar"] == obj2["bosqichlar"]
    assert n1["kpi"] == n2["kpi"]


# ==========================================================================
# S6 — Qarzdorlar eslatmasi
# ==========================================================================

def test_s6_qarzdorlarni_togri_topadi(s6_mod):
    joriy = paket.oqi("TEST")
    kutilgan_qarzdorlar = [t for t in joriy["talabalar"]
                           if (t.get("tolov") or {}).get("qarz", 0) > 0]

    agent = s6_mod.S6(sana=SANA)
    natija = agent.ish()
    obj = fayl.json_oqi(konfig.data("qarz.json"))

    assert obj["qarzdorlar_soni"] == len(kutilgan_qarzdorlar)
    assert natija["kpi"]["qarzdorlar_soni"] == len(kutilgan_qarzdorlar)
    assert len(obj["royxat"]) == len(kutilgan_qarzdorlar)
    # hech bir "qarzsiz" talaba ro'yxatga tushmagan
    assert all(r["qarz"] > 0 for r in obj["royxat"])
    assert obj["qarz_jami"] == sum(r["qarz"] for r in obj["royxat"])


def test_s6_royxat_keyingi_sana_boyicha_tartiblangan(s6_mod):
    agent = s6_mod.S6(sana=SANA)
    agent.ish()
    obj = fayl.json_oqi(konfig.data("qarz.json"))

    sanalar = [r["keyingi_sana"] for r in obj["royxat"] if r["keyingi_sana"] is not None]
    assert sanalar == sorted(sanalar), "keyingi_sana bo'yicha o'sish tartibida bo'lishi kerak"
    # sana yo'qlar (agar bo'lsa) ro'yxat oxirida
    nonelar_indeks = [i for i, r in enumerate(obj["royxat"]) if r["keyingi_sana"] is None]
    borlar_indeks = [i for i, r in enumerate(obj["royxat"]) if r["keyingi_sana"] is not None]
    if nonelar_indeks and borlar_indeks:
        assert min(nonelar_indeks) > max(borlar_indeks)


def test_s6_shlyuz_yoq_bolsa_yiqilmaydi(s6_mod, monkeypatch):
    """Shlyuz ishlamayotgan portga yo'naltirilsa (real shlyuz servis
    ishlamagan holat) — agent xato bermaydi, har eslatma
    xabar_holati='shlyuz_yoq' bilan yoziladi (shlyuz_client.py qoidasi)."""
    monkeypatch.setenv("INPLUS_SHLYUZ_PORT", "18999")  # hech kim tinglamaydi
    agent = s6_mod.S6(sana=SANA)
    natija = agent.ish()
    obj = fayl.json_oqi(konfig.data("qarz.json"))

    assert obj["qarzdorlar_soni"] > 0
    assert all(r["xabar_holati"] == "shlyuz_yoq" for r in obj["royxat"])
    assert natija["kpi"].get("xabar_shlyuz_yoq") == obj["qarzdorlar_soni"]


# ==========================================================================
# Reestr — konfig/agentlar.json ga to'g'ri qo'shilgan
# ==========================================================================

def test_agentlar_json_s2_s6_royxatda():
    reestr = konfig.konfig_json("agentlar.json")
    for aid in ("S2", "S6"):
        assert aid in reestr, f"{aid} konfig/agentlar.json ga qo'shilmagan"
        meta = reestr[aid]
        assert meta["tur"] == "timer"
        assert "paket" in meta.get("oqiydi", [])
        assert meta.get("egasi")
    # poydevor yozuvlariga tegilmaganini tekshiramiz (mavjud kalitlar saqlangan)
    for aid in ("D1", "D6", "SHLYUZ", "N3", "X2", "X1", "W1", "X0"):
        assert aid in reestr
