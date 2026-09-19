"""Oqim D (orkestr/nazorat) qabul mezonlari — §5 X2/X1/W1:
  - X0 yiqilsa -> X2 insident yozadi + qayta yoqadi (sog'ayadi).
  - Namuna buzilgan uzatish/KPI/kod -> X1 aniq kodlarni topadi
    (UZ_KUTILDI, UZ_HASH, UZ_SONI, UZ_YETIM, KPI_XATO, KPI_NISBAT, HB_YOQ,
    SHLYUZ_CHETLAB) va toza kunda hech narsa topmaydi.
  - W1 ishga tushsa wiki/_html/index.html + reestr + kunlik jurnal yaratadi,
    arxivlash + arxivdan o'qish ishlaydi.

Real demo repo (`INPLUS_ILDIZ`, conftest.py) ustida ishlaydi — boshqa
testlar (kontrakt_test, adapter_mock_test) bilan bir xil uslubda. O'zaro
ta'sirni oldini olish uchun sintetik `sana` (masalan "2020-01-01") va
sintetik agent ID lar ("T-...") ishlatiladi; faqat X0<->X2 integratsiya
testi haqiqiy X0 agentini (bugungi sana bilan) ishlatadi, chunki u aynan
shu maqsad uchun mo'ljallangan kanareyka agenti.
"""
import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

from inplus import konfig, kontrakt, jurnal, fayl, heartbeat, kpi as kpi_mod, uzatish

ILDIZ = konfig.ILDIZ
SINTETIK_SANA = "2020-01-01"


def _modul_yukla(nom, yol):
    spec = importlib.util.spec_from_file_location(nom, yol)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def x2_mod():
    return _modul_yukla("x2_doktor_main", ILDIZ / "agents" / "x2_doktor" / "main.py")


@pytest.fixture(scope="module")
def x1_mod():
    return _modul_yukla("x1_auditor_main", ILDIZ / "agents" / "x1_auditor" / "main.py")


@pytest.fixture(scope="module")
def w1_mod():
    return _modul_yukla("w1_xotira_main", ILDIZ / "agents" / "w1_xotira" / "main.py")


def _uzatish_satr_yoz(sana, **kw):
    satr = {
        "uzatish_id": kw["uzatish_id"], "vaqt": kw.get("vaqt", konfig.iso()),
        "yonalish": kw["yonalish"], "kimdan": kw["kimdan"], "kimga": kw["kimga"],
        "tur": kw.get("tur", "fayl"), "obyekt": kw["obyekt"], "hash": kw["hash"],
        "soni": kw.get("soni", {}), "kutish_daq": kw.get("kutish_daq"),
    }
    kontrakt.tekshir("uzatish", satr)
    jurnal.append(uzatish.yol(sana), satr)


def _kpi_yoz(agent, sana, ishlar):
    obj = {"versiya": "1.0", "agent": agent, "sana": sana, "ishlar": ishlar, "kun": {}}
    kun = {
        "ishlar_soni": len(ishlar),
        "ok": sum(1 for i in ishlar if i["holat"] == "ok"),
        "xato": sum(1 for i in ishlar if i["holat"] == "xato"),
        "davomiylik_s_jami": round(sum(i["davomiylik_s"] for i in ishlar), 3),
        "kpi": {},
    }
    obj["kun"] = kun
    kontrakt.tekshir("kpi", obj)
    fayl.json_yoz(kpi_mod.yol(agent, sana), obj)
    return obj


def _ish(holat="ok", kirdi=None, chiqdi=None, xato_soni=0):
    return {
        "boshlandi": konfig.iso(), "tugadi": konfig.iso(), "davomiylik_s": 1.0,
        "holat": holat, "xato_soni": xato_soni, "xato_oxirgi": None,
        "kirdi": kirdi or {}, "chiqdi": chiqdi or {}, "kpi": {},
    }


# ==========================================================================
# X2 — X0 yiqilsa insident + qayta yoqish (sog'ayadi)
# ==========================================================================
def test_x2_x0_ni_davolaydi(x2_mod, monkeypatch):
    sana = konfig.bugun()

    # 1) X0 "yiqilgan" holatda deb simulyatsiya qilamiz (heartbeat=xato)
    heartbeat.yoz("X0", "xato", boshlandi=konfig.iso(), xabar="RuntimeError: sinov uchun majburiy xato")

    # 2) qayta yoqilganda X0 ANIQ tirilishi uchun majburlaymiz
    monkeypatch.setenv("INPLUS_X0_YIQIL", "0")
    monkeypatch.setenv("INPLUS_X2_SIMULYATSIYA", "1")  # Mac'da systemctl yo'q

    ilgarigi_insident_soni = len(jurnal.oqi(konfig.data("insident", f"{sana}.jsonl")))

    natijalar = x2_mod.sikl_bajar()

    x0_natija = next((n for n in natijalar if n.get("agent") == "X0"), None)
    assert x0_natija is not None, f"X0 uchun natija topilmadi: {natijalar}"
    assert x0_natija.get("kod") == "HB_XATO"
    assert x0_natija.get("natija") == "ok", "restart(simulyatsiya) dan keyin X0 sog'ayishi kerak edi"

    # heartbeat haqiqatan ham tuzalgan
    hb = heartbeat.oqi("X0")
    assert hb["holat"] != "xato"

    # insident yozilgan
    insidentlar = jurnal.oqi(konfig.data("insident", f"{sana}.jsonl"))
    assert len(insidentlar) > ilgarigi_insident_soni
    x0_insidentlar = [i for i in insidentlar if i["agent"] == "X0" and i["kod"] == "HB_XATO"]
    assert x0_insidentlar, "X0 uchun HB_XATO insidenti yozilishi kerak edi"
    assert x0_insidentlar[-1]["yopildi"] is not None, "sog'aygan insident darhol yopilishi kerak"

    # restart hisobi
    restart_holat = fayl.json_oqi(konfig.data("x2", "restart.json"))
    assert restart_holat["X0"]["soni"] == 0  # sog'aygach nolga tushadi

    # dashboard yozilgan va X0 yashil
    dash = fayl.json_oqi(konfig.data("dashboard.json"))
    x0_qator = next(a for a in dash["agentlar"] if a["agent"] == "X0")
    assert x0_qator["rang"] == "yashil"


def test_x2_restart_max_toxtaydi(x2_mod, monkeypatch):
    """3 martadan ortiq qayta yoqishga urinilsa RESTART_MAX kritik, endi urinmaydi."""
    sana = konfig.bugun()
    agentlar = konfig.konfig_json("agentlar.json")
    meta = agentlar.get("D1", {"sla_daq": 30, "qayta_yoqish": {"max": 3, "oraliq_daq": 0}})

    # D1 heartbeat'ini "xato" qilib qo'yamiz, lekin qayta yoqish har doim MUVAFFAQIYATSIZ
    # bo'lsin uchun mavjud bo'lmagan agentga o'xshab ko'rsatamiz (main.py yo'q -> restart ok=False)
    heartbeat.yoz("D1", "xato", boshlandi=konfig.iso(), xabar="sinov: qattiq buzilgan")
    monkeypatch.setattr(x2_mod, "_agent_main_py", lambda aid: None)  # restart har doim muvaffaqiyatsiz
    monkeypatch.setenv("INPLUS_X2_SIMULYATSIYA", "1")

    # restart.json ni max-1 gacha oldindan to'ldiramiz (tezroq RESTART_MAXga yetish uchun)
    qy = meta.get("qayta_yoqish", {"max": 3, "oraliq_daq": 5})
    restart_holat = x2_mod._restart_holat_oqi()
    restart_holat["D1"] = {"soni": qy.get("max", 3), "oxirgi": None}
    restart_holat.setdefault("_ochiq", {})
    x2_mod._restart_holat_yoz(restart_holat)

    x2_mod.sikl_bajar()

    insidentlar = jurnal.oqi(konfig.data("insident", f"{sana}.jsonl"))
    max_insidentlar = [i for i in insidentlar if i["agent"] == "D1" and i["kod"] == "RESTART_MAX"]
    assert max_insidentlar, "RESTART_MAX insidenti yozilishi kerak edi"
    assert max_insidentlar[-1]["daraja"] == "kritik"

    # tozalash: keyingi testlarga ta'sir qilmasin
    restart_holat = x2_mod._restart_holat_oqi()
    restart_holat.pop("D1", None)
    restart_holat.get("_ochiq", {}).pop("D1", None)
    x2_mod._restart_holat_yoz(restart_holat)
    heartbeat.yoz("D1", "tugadi", boshlandi=konfig.iso())


# ==========================================================================
# X1 — namuna buzilgan uzatish/KPI -> aniq kodlar
# ==========================================================================
def _agentlar_ornat(monkeypatch, sintetik):
    """agentlar.json ni berilgan sintetik dict bilan almashtiradi (faqat shu test uchun)."""
    asl = konfig.konfig_json
    monkeypatch.setattr(konfig, "konfig_json", lambda nom: sintetik if nom == "agentlar.json" else asl(nom))


@pytest.fixture
def sof_test_agentlari(monkeypatch):
    """Uzatish-zanjiri testlari uchun: faqat ikkita agent (yozuvchi/o'quvchi)."""
    # jadval "*:0/5" (kunlik HH:MM:SS emas) -> _bugun_kutilgan_allaqachon_otdimi
    # buni "noma'lum format" deb o'tkazib yuboradi, shuning uchun bu test faqat
    # uzatish zanjiri kodlarini tekshiradi, KPI_YOQ bilan aralashmaydi.
    sintetik = {
        "T-YOZ": {"nom": "Sintetik yozuvchi", "tur": "timer", "jadval": "*:0/5",
                  "sla_daq": 30, "yozadi": ["tsinov"], "oqiydi": []},
        "T-OQ": {"nom": "Sintetik o'quvchi", "tur": "timer", "jadval": "*:0/5",
                 "sla_daq": 30, "yozadi": [], "oqiydi": ["tsinov"]},
    }
    _agentlar_ornat(monkeypatch, sintetik)
    return sintetik


def _tur_dan_obyekt_ozgartir(monkeypatch, x1_mod):
    asl = x1_mod._tur_dan_obyekt
    monkeypatch.setattr(x1_mod, "_tur_dan_obyekt",
                         lambda obyekt: "tsinov" if obyekt.startswith("data/tsinov/") else asl(obyekt))


def _agents_papkasini_izolyatsiya_qil(monkeypatch, tmp_path):
    """`konfig.yol("agents")` ni bo'sh tmp papkaga yo'naltiradi — SHLYUZ_CHETLAB
    grep testi boshqa oqimlar (D1/D6/SHLYUZ/N3) hali yozayotgan real koddan
    mustaqil, deterministik bo'lsin uchun."""
    asl_yol = konfig.yol
    monkeypatch.setattr(konfig, "yol", lambda *q: tmp_path if q == ("agents",) else asl_yol(*q))
    return tmp_path


def test_x1_uzatish_zanjiri_buzilgan_kodlarni_topadi(x1_mod, sof_test_agentlari, monkeypatch, tmp_path):
    sana = SINTETIK_SANA
    _tur_dan_obyekt_ozgartir(monkeypatch, x1_mod)
    _agents_papkasini_izolyatsiya_qil(monkeypatch, tmp_path)

    # eski sinov fayllarini tozalab boshlaymiz (qayta ishga tushirilsa ham idempotent)
    konfig.data("uzatish", f"{sana}.jsonl").unlink(missing_ok=True)
    konfig.data("insident", f"{sana}.jsonl").unlink(missing_ok=True)

    # 1) UZ_KUTILDI: berdi bor, T-OQ hech qachon olmagan, kutish_daq allaqachon o'tgan
    _uzatish_satr_yoz(sana, uzatish_id="u-t-0001", vaqt="2020-01-01T00:00:00+05:00",
                      yonalish="berdi", kimdan="T-YOZ", kimga="*",
                      obyekt="data/tsinov/kutildi.json", hash="sha256:aaa", kutish_daq=1)

    # 2) UZ_HASH: berdi va oldi hash farq qiladi
    _uzatish_satr_yoz(sana, uzatish_id="u-t-0002", yonalish="berdi", kimdan="T-YOZ", kimga="T-OQ",
                      obyekt="data/tsinov/hash.json", hash="sha256:bbb")
    _uzatish_satr_yoz(sana, uzatish_id="u-t-0002", yonalish="oldi", kimdan="T-YOZ", kimga="T-OQ",
                      obyekt="data/tsinov/hash.json", hash="sha256:CCC-BOSHQA")

    # 3) UZ_SONI: soni mos kelmaydi
    _uzatish_satr_yoz(sana, uzatish_id="u-t-0003", yonalish="berdi", kimdan="T-YOZ", kimga="T-OQ",
                      obyekt="data/tsinov/soni.json", hash="sha256:ddd", soni={"n": 5})
    _uzatish_satr_yoz(sana, uzatish_id="u-t-0003", yonalish="oldi", kimdan="T-YOZ", kimga="T-OQ",
                      obyekt="data/tsinov/soni.json", hash="sha256:ddd", soni={"n": 2})

    # 4) UZ_YETIM: oldi bor, mos berdi yo'q
    _uzatish_satr_yoz(sana, uzatish_id="u-t-YETIM", yonalish="oldi", kimdan="T-YOZ", kimga="T-OQ",
                      obyekt="data/tsinov/yetim.json", hash="sha256:eee")

    # 5) TOZA: berdi+oldi mos, hech narsa (nazorat guruhi)
    _uzatish_satr_yoz(sana, uzatish_id="u-t-0005", yonalish="berdi", kimdan="T-YOZ", kimga="T-OQ",
                      obyekt="data/tsinov/toza.json", hash="sha256:fff", soni={"n": 1})
    _uzatish_satr_yoz(sana, uzatish_id="u-t-0005", yonalish="oldi", kimdan="T-YOZ", kimga="T-OQ",
                      obyekt="data/tsinov/toza.json", hash="sha256:fff", soni={"n": 1})

    natija = x1_mod.audit(sana=sana)
    kodlar = set(natija["jami"]["kodlar"])

    assert "UZ_KUTILDI" in kodlar
    assert "UZ_HASH" in kodlar
    assert "UZ_SONI" in kodlar
    assert "UZ_YETIM" in kodlar
    assert natija["jami"]["buzilgan"] == 4, f"aniq 4 ta buzilish kutilgan edi: {natija}"

    # toza obyekt hech qanday insidentga sabab bo'lmagan
    insidentlar = jurnal.oqi(konfig.data("insident", f"{sana}.jsonl"))
    assert not any("toza.json" in i["xabar"] for i in insidentlar)

    # wiki jadval yozilgan
    assert konfig.yol("wiki", "jurnal", f"zanjir_{sana}.md").exists()


def test_x1_kpi_va_heartbeat_kodlari(x1_mod, monkeypatch, tmp_path):
    sana = SINTETIK_SANA
    _agentlar_ornat(monkeypatch, {
        "T-K1": {"nom": "KPI xato sinovi", "tur": "timer", "jadval": "*-*-* 00:00:00", "sla_daq": 30},
        "T-K2": {"nom": "KPI nisbat sinovi", "tur": "timer", "jadval": "*-*-* 00:00:00",
                 "sla_daq": 30, "kutilgan_nisbat": ["chiqdi.a == kirdi.b"]},
        "T-HB": {"nom": "Heartbeat yo'q sinovi", "tur": "timer", "jadval": "*-*-* 00:00:00", "sla_daq": 30},
    })
    _tur_dan_obyekt_ozgartir(monkeypatch, x1_mod)
    _agents_papkasini_izolyatsiya_qil(monkeypatch, tmp_path)
    konfig.data("uzatish", f"{sana}.jsonl").unlink(missing_ok=True)

    # T-K1: bugun 1 marta xato bilan tugagan -> KPI_XATO
    _kpi_yoz("T-K1", sana, [_ish(holat="xato", xato_soni=1)])
    heartbeat.yoz("T-K1", "xato", boshlandi=konfig.iso())

    # T-K2: kutilgan_nisbat buziladi (chiqdi.a=3 != kirdi.b=5) -> KPI_NISBAT
    _kpi_yoz("T-K2", sana, [_ish(holat="ok", kirdi={"b": 5}, chiqdi={"a": 3})])
    heartbeat.yoz("T-K2", "tugadi", boshlandi=konfig.iso())

    # T-HB: KPI bor, heartbeat HECH QACHON yozilmagan -> HB_YOQ
    hb_p = konfig.run_yol("heartbeat", "T-HB.json")
    hb_p.unlink(missing_ok=True)
    _kpi_yoz("T-HB", sana, [_ish(holat="ok")])

    natija = x1_mod.audit(sana=sana)
    kodlar = set(natija["jami"]["kodlar"])

    assert "KPI_XATO" in kodlar
    assert "KPI_NISBAT" in kodlar
    assert "HB_YOQ" in kodlar


def test_x1_shlyuz_chetlab_grep(x1_mod, monkeypatch, tmp_path):
    sana = SINTETIK_SANA
    _agentlar_ornat(monkeypatch, {})
    _tur_dan_obyekt_ozgartir(monkeypatch, x1_mod)
    _agents_papkasini_izolyatsiya_qil(monkeypatch, tmp_path)
    konfig.data("uzatish", f"{sana}.jsonl").unlink(missing_ok=True)

    yomon_papka = tmp_path / "t9_sinov_chetlab"
    yomon_papka.mkdir(parents=True, exist_ok=True)
    (yomon_papka / "main.py").write_text(
        "import requests\n"
        "requests.post('https://api.telegram.org/bot123/sendMessage', json={})\n",
        encoding="utf-8",
    )
    natija = x1_mod.audit(sana=sana)
    assert "SHLYUZ_CHETLAB" in set(natija["jami"]["kodlar"])


def test_x1_toza_kunda_hech_narsa_topmaydi(x1_mod, monkeypatch, tmp_path):
    """agentlar.json bo'sh ro'yxatga almashtirilsa, uzatish bo'sh bo'lsa va kod
    daraxti (grep uchun) bo'sh papkaga yo'naltirilsa -> buzilgan == 0. `agents/`
    ni bo'sh tmp papkaga yo'naltirish natijani boshqa oqimlar (D1/D6/SHLYUZ)
    hali yozayotgan kodga bog'liq qilmaydi — determinstik bo'lsin uchun."""
    sana = "2021-06-15"
    asl_konfig_json = konfig.konfig_json
    asl_yol = konfig.yol
    monkeypatch.setattr(konfig, "konfig_json",
                         lambda nom: {} if nom == "agentlar.json" else asl_konfig_json(nom))
    monkeypatch.setattr(konfig, "yol",
                         lambda *q: tmp_path if q == ("agents",) else asl_yol(*q))
    konfig.data("uzatish", f"{sana}.jsonl").unlink(missing_ok=True)
    konfig.data("insident", f"{sana}.jsonl").unlink(missing_ok=True)
    natija = x1_mod.audit(sana=sana)
    assert natija["jami"]["buzilgan"] == 0
    assert natija["jami"]["yashil"] == 0  # agent yo'q -> hisoblanadigan narsa yo'q


# ==========================================================================
# W1 — wiki yaratadi + arxivlash
# ==========================================================================
def test_w1_wiki_yaratadi(w1_mod):
    sana = konfig.bugun()
    agent = w1_mod.W1(sana=sana)
    natija = agent.ish()

    assert natija["kpi"]["sop_yozildi"] >= 1

    indeks = konfig.yol("wiki", "_html", "index.html")
    assert indeks.exists()
    matn = indeks.read_text(encoding="utf-8")
    assert "X2" in matn or "X1" in matn  # kamida bizning agentlarimiz SOP'i bor

    assert konfig.yol("wiki", "reestr", "agentlar.md").exists()
    assert konfig.yol("wiki", "reestr", "skriptlar.md").exists()
    assert konfig.yol("wiki", "jurnal", f"{sana}.md").exists()
    assert konfig.yol("wiki", "_html", "jurnal", f"{sana}.html").exists()
    assert konfig.yol("wiki", "_html", "insident", f"{sana}.html").exists()

    for aid in ("X0", "X1", "X2", "W1"):
        assert konfig.yol("wiki", "agentlar", f"{aid}.md").exists(), f"{aid} SOP wiki'ga tushmagan"


def test_w1_arxiv_va_oqish(w1_mod):
    """31 kunlik soxta KPI -> eng eskisi tar.gz ga tushadi va arxiv_oqi() bilan o'qiladi."""
    eski_sana = "2020-02-01"
    agent = "T-ARXIV"
    p = kpi_mod.yol(agent, eski_sana)
    obj = {"versiya": "1.0", "agent": agent, "sana": eski_sana, "ishlar": [],
           "kun": {"ishlar_soni": 0, "ok": 0, "xato": 0, "davomiylik_s_jami": 0, "kpi": {}}}
    fayl.json_yoz(p, obj)
    assert p.exists()

    natija = w1_mod.arxivla(bugun=date(2026, 9, 19))
    assert natija["tar"] >= 1
    assert not p.exists(), "eski fayl data/ dan yo'qolishi kerak edi"

    nisbiy = f"kpi/{agent}/{eski_sana}.json"
    oqilgan = w1_mod.arxiv_oqi(nisbiy)
    assert oqilgan is not None
    assert json.loads(oqilgan)["agent"] == agent
