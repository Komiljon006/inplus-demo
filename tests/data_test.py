"""D6 (Kurslar jadvali) va D1 (Sborshik dannyx) — PLAN_BLOK1.md §5 dagi
QABUL MEZONLARI aynan shu holatlarda tekshiriladi.

Har test o'z ichida mock/generator.py bilan toza, deterministik holatni
tiklaydi (boshqa testga ta'sir qilmasin uchun) va `data/`, `run/heartbeat/`
ni ishlatadi (tests/conftest.py INPLUS_ILDIZ ni repo ildiziga o'rnatadi).
"""
import importlib
import os
import shutil
import subprocess
import sys
import time

import pytest

from inplus import konfig, kontrakt, fayl, heartbeat, kpi as kpi_mod, uzatish

ILDIZ = konfig.ILDIZ
SANA = "2026-09-19"
CSV_ASL = ILDIZ / "mock" / "sheets" / "jadval.csv"


def _toza_holat():
    """data/ va run/heartbeat/ ni tozalab, mock ni qayta yasaydi (deterministik)."""
    for env in ("INPLUS_MOCK_YIQIL",):
        os.environ.pop(env, None)
    shutil.rmtree(ILDIZ / "data", ignore_errors=True)
    shutil.rmtree(ILDIZ / "run" / "heartbeat", ignore_errors=True)
    (ILDIZ / "data").mkdir(parents=True, exist_ok=True)
    (ILDIZ / "run" / "heartbeat").mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ILDIZ))
    from mock import generator
    generator.main(["--lid", "400", "--talaba", "260", "--urug", "42", "--kun", "0"])


def _agent_modul(nom):
    """agents/<papka>/main.py ni modul sifatida yuklaydi (bin/inplus kabi)."""
    papka = {"D6": "d6_jadval", "D1": "d1_sborshik"}[nom]
    yol = ILDIZ / "agents" / papka / "main.py"
    spec = importlib.util.spec_from_file_location(f"agent_{papka}", yol)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _ishga_tushir(nom, sana=SANA, env_qoshimcha=None):
    """CLI orqali subprocess (bin/inplus kabi) — real ishga tushirish yo'lini sinaydi."""
    papka = {"D6": "d6_jadval", "D1": "d1_sborshik"}[nom]
    main_py = ILDIZ / "agents" / papka / "main.py"
    env = dict(os.environ)
    env["INPLUS_ILDIZ"] = str(ILDIZ)
    # Shlyuz (boshqa oqim) shu mashinada tasodifan ishlab turgan bo'lsa ham,
    # bu testlar undan mustaqil va deterministik bo'lishi kerak: standart
    # bo'lmagan portga yuboramiz -> "ConnectionRefused" -> shlyuz_yoq (kutilgan
    # yiqilmaydigan yo'l). Real shlyuzni sinash bu fayl vazifasi emas.
    # (setdefault emas — `inplus.konfig` import paytida .env dan
    # INPLUS_SHLYUZ_PORT=8471 ni allaqachon os.environ ga yozgan bo'ladi.)
    env["INPLUS_SHLYUZ_PORT"] = "18471"
    if env_qoshimcha:
        env.update(env_qoshimcha)
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, str(main_py), "--bir-marta", "--sana", sana],
                       cwd=str(ILDIZ), env=env, capture_output=True, text=True)
    dt = time.monotonic() - t0
    return r.returncode, r.stdout, r.stderr, dt


@pytest.fixture(autouse=True)
def _har_test_toza():
    # _toza_holat() generator.main() ni qayta chaqiradi -> jadval.csv ham
    # deterministik qayta yasaladi, shuning uchun oldingi testning CSV
    # o'zgarishi keyingi testga o'tmaydi.
    _toza_holat()
    yield


# --------------------------------------------------------------------------- #
# D6 — Kurslar jadvali
# --------------------------------------------------------------------------- #

def test_d6_xato_bosqichida_courses_yangilanmaydi():
    """(1) mock csv 14 qatordan N kurs/guruh + 1 xato + 1 ogohlantirish chiqadi,
    courses.json YANGILANMAYDI (xato bor)."""
    kod, out, err, _ = _ishga_tushir("D6")
    assert kod == 0, err

    assert not (ILDIZ / "data" / "courses.json").exists()
    xato_fayl = ILDIZ / "data" / "courses" / f"{SANA}.xato.json"
    assert xato_fayl.exists()

    obj = fayl.json_oqi(xato_fayl)
    assert obj["validatsiya"]["holat"] == "xato"
    xatolar = [x for x in obj["validatsiya"]["xatolar"] if x["daraja"] == "xato"]
    ogohlar = [x for x in obj["validatsiya"]["xatolar"] if x["daraja"] == "ogohlantirish"]
    assert len(xatolar) == 1
    assert len(ogohlar) == 1
    assert "31.09.2026" in str(xatolar[0]["qiymat"]) or "sana" in xatolar[0]["maydon"]


def test_d6_tuzatilgach_ogohlantirish_holatida_yangilanadi():
    """(2) csv'da xatoli qator tuzatilsa -> holat: ogohlantirish, fayl yangilanadi."""
    matn = CSV_ASL.read_text(encoding="utf-8").replace("31.09.2026", "30.09.2026")
    CSV_ASL.write_text(matn, encoding="utf-8")

    kod, out, err, _ = _ishga_tushir("D6")
    assert kod == 0, err

    courses_fayl = ILDIZ / "data" / "courses.json"
    assert courses_fayl.exists()
    obj = fayl.json_oqi(courses_fayl)
    assert obj["validatsiya"]["holat"] == "ogohlantirish"
    assert len(obj["validatsiya"]["xatolar"]) == 1
    assert obj["validatsiya"]["xatolar"][0]["daraja"] == "ogohlantirish"


def test_d6_kontrakt_tekshir_otadi():
    """(3) kontrakt.tekshir("courses", ...) o'tadi."""
    matn = CSV_ASL.read_text(encoding="utf-8").replace("31.09.2026", "30.09.2026")
    CSV_ASL.write_text(matn, encoding="utf-8")
    kod, out, err, _ = _ishga_tushir("D6")
    assert kod == 0, err
    obj = fayl.json_oqi(ILDIZ / "data" / "courses.json")
    assert kontrakt.tekshir("courses", obj) is True


def test_d6_uzatish_kpi_heartbeat_yozilgan():
    """(4) uzatish+KPI+heartbeat yozilgan."""
    matn = CSV_ASL.read_text(encoding="utf-8").replace("31.09.2026", "30.09.2026")
    CSV_ASL.write_text(matn, encoding="utf-8")
    kod, out, err, _ = _ishga_tushir("D6")
    assert kod == 0, err

    hb = heartbeat.oqi("D6")
    assert hb is not None and hb["holat"] == "tugadi"

    kpi = kpi_mod.oqi("D6", SANA)
    assert kpi is not None and kpi["kun"]["ok"] == 1

    satrlar = uzatish.oqi(SANA)
    berdi = [s for s in satrlar if s["kimdan"] == "D6" and s["yonalish"] == "berdi"]
    assert len(berdi) == 1
    assert berdi[0]["obyekt"] == "data/courses.json"


def test_d6_xato_bosqichida_s902_yuboriladi_yoki_shlyuz_yoq_kpida():
    """(5) S-902 xabar shlyuz jurnalida ko'rinadi (yoki shlyuz_yoq KPI/logda)."""
    kod, out, err, _ = _ishga_tushir("D6")
    assert kod == 0, err
    log_fayl = ILDIZ / "data" / "jurnal" / "agent" / "D6" / f"{SANA}.log"
    satrlar = log_fayl.read_text(encoding="utf-8").splitlines()
    voqealar = [s for s in satrlar if '"skript_id":"S-902"' in s or '"voqea":"shlyuz_yoq"' in s]
    assert voqealar, "S-902 urinishi (yoki shlyuz_yoq) logda topilmadi"


# --------------------------------------------------------------------------- #
# D1 — Sborshik dannyx
# --------------------------------------------------------------------------- #

def _d6_muvaffaqiyatli_ishga_tushir():
    matn = CSV_ASL.read_text(encoding="utf-8").replace("31.09.2026", "30.09.2026")
    CSV_ASL.write_text(matn, encoding="utf-8")
    kod, out, err, _ = _ishga_tushir("D6")
    assert kod == 0, err


def test_d1_mock_uch_manbadan_paket_schema_va_vaqt():
    """(1) mock 3 manbadan paket 400+ lid/260+ talaba, schema o'tadi, <= 15 s."""
    _d6_muvaffaqiyatli_ishga_tushir()
    kod, out, err, dt = _ishga_tushir("D1")
    assert kod == 0, err
    assert dt <= 15, f"D1 {dt:.1f}s da tugadi (SLA 15s)"

    obj = fayl.json_oqi(ILDIZ / "data" / "paket" / f"{SANA}.json")
    assert kontrakt.tekshir("paket", obj) is True
    assert len(obj["lidlar"]) >= 400
    assert len(obj["talabalar"]) >= 260
    assert (ILDIZ / "data" / "paket" / "joriy.json").is_symlink()


def test_d1_getcourse_yiqilsa_eski_bolim_va_s900():
    """(2) INPLUS_MOCK_YIQIL=getcourse -> manbalar.getcourse.holat=eski,
    paket baribir yoziladi, S-900 ketadi, exit 0."""
    _d6_muvaffaqiyatli_ishga_tushir()
    kod, out, err, _ = _ishga_tushir("D1")  # avval sog'lom paket (fallback manbasi)
    assert kod == 0, err

    kod, out, err, _ = _ishga_tushir("D1", env_qoshimcha={"INPLUS_MOCK_YIQIL": "getcourse"})
    assert kod == 0, err

    obj = fayl.json_oqi(ILDIZ / "data" / "paket" / f"{SANA}.json")
    assert obj["manbalar"]["getcourse"]["holat"] == "eski"
    assert obj["holat_umumiy"] == "qisman"
    assert len(obj["talabalar"]) >= 260  # baribir yozilgan (fallback)

    log_fayl = ILDIZ / "data" / "jurnal" / "agent" / "D1" / f"{SANA}.log"
    satrlar = log_fayl.read_text(encoding="utf-8").splitlines()
    voqealar = [s for s in satrlar if '"skript_id":"S-900"' in s or '"voqea":"shlyuz_yoq"' in s]
    assert voqealar, "S-900 urinishi (yoki shlyuz_yoq) logda topilmadi"


def test_d1_uchala_manba_yiqilsa_paket_yozilmaydi():
    """(3) 3 manba ham yiqilsa -> exit 1, joriy.json o'zgarmaydi, heartbeat xato."""
    amocrm_bak = ILDIZ / "mock" / "amocrm"
    getcourse_bak = ILDIZ / "mock" / "getcourse"
    tmp1 = ILDIZ / "mock" / "_amocrm_bak"
    tmp2 = ILDIZ / "mock" / "_getcourse_bak"
    shutil.move(str(amocrm_bak), str(tmp1))
    shutil.move(str(getcourse_bak), str(tmp2))
    try:
        kod, out, err, _ = _ishga_tushir("D1")  # courses.json ham yo'q (D6 hali ishlamagan)
        assert kod != 0
        assert not (ILDIZ / "data" / "paket" / f"{SANA}.json").exists()
        assert not (ILDIZ / "data" / "paket" / "joriy.json").exists()
        hb = heartbeat.oqi("D1")
        assert hb is not None and hb["holat"] == "xato"
    finally:
        shutil.move(str(tmp1), str(amocrm_bak))
        shutil.move(str(tmp2), str(getcourse_bak))


def test_d1_telefon_normalizatsiya():
    """(4) telefon '90 123 45 67' -> '+998901234567', 'abc' -> null + KPI telefon_xato."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "d1main", ILDIZ / "agents" / "d1_sborshik" / "main.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.normalize_telefon("90 123 45 67") == "+998901234567"
    assert m.normalize_telefon("abc") is None
    assert m.normalize_telefon("") is None
    assert m.normalize_telefon("+7 916 000 00 00") is None
    assert m.normalize_telefon("+998901234567") == "+998901234567"

    _d6_muvaffaqiyatli_ishga_tushir()
    kod, out, err, _ = _ishga_tushir("D1")
    assert kod == 0, err
    kpi = kpi_mod.oqi("D1", SANA)
    assert kpi["ishlar"][-1]["kpi"]["telefon_normalizatsiya_xato"] > 0


def test_d1_guruh_id_courses_da_yoq_bolsa_null():
    """(5) talabalar[].guruh_id courses'da yo'q -> null + KPI."""
    _d6_muvaffaqiyatli_ishga_tushir()
    kod, out, err, _ = _ishga_tushir("D1")
    assert kod == 0, err
    obj = fayl.json_oqi(ILDIZ / "data" / "paket" / f"{SANA}.json")
    nomalum = [t for t in obj["talabalar"] if t["xom"].get("kurs_id") == "K-XXX-99"]
    assert nomalum, "K-XXX-99 (courses'da yo'q kurs) testi uchun namuna talaba topilmadi"
    for t in nomalum:
        assert t["guruh_id"] is None
        assert t["kurs_id"] is None
    kpi = kpi_mod.oqi("D1", SANA)
    assert kpi["ishlar"][-1]["kpi"]["guruh_id_topilmadi"] > 0


def test_d1_ikki_marta_ishga_tushirilsa_idempotent():
    """(6) ikki marta ishga tushirilsa fayl idempotent (hash bir xil,
    uzatish 2 marta emas)."""
    _d6_muvaffaqiyatli_ishga_tushir()
    kod, _, err, _ = _ishga_tushir("D1")
    assert kod == 0, err
    obj1 = fayl.json_oqi(ILDIZ / "data" / "paket" / f"{SANA}.json")

    kod, _, err, _ = _ishga_tushir("D1")
    assert kod == 0, err
    obj2 = fayl.json_oqi(ILDIZ / "data" / "paket" / f"{SANA}.json")

    assert obj1["hash"] == obj2["hash"]

    satrlar = uzatish.oqi(SANA)
    berdi = [s for s in satrlar if s["kimdan"] == "D1" and s["yonalish"] == "berdi"]
    assert len(berdi) == 1, f"idempotent bo'lishi kerak, lekin {len(berdi)} ta uzatish(berdi) bor"
