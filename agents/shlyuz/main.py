#!/usr/bin/env python3
"""SHLYUZ — Xabar shlyuzi (N1 SMS + N2 Telegram, bitta servis).

Ikki thread:
  - HTTP (ThreadingHTTPServer, 127.0.0.1:8471): POST /yubor, GET /holat/<id>,
    GET /statistika. Faqat INSERT (§2.8/§5, 9 qadam).
  - Navbat ishchisi: 1 s da SQLite'dan `navbatda` (keyingi_urinish <= now) ni
    oladi, N1/N2 orqali yuboradi, holatni yangilaydi (UPDATE).

SQLite `data/shlyuz.db`, jadval `xabarlar` (§2.8). Jurnal —
`data/jurnal/xabar/<sana>.jsonl` (har holat o'zgarishi bitta satr).

Ishga tushirish:
  python3 agents/shlyuz/main.py [--port 8471]
  bin/inplus ishga SHLYUZ   (yoki servis sifatida systemd)

Test uchun `Shlyuz` klassi to'g'ridan-to'g'ri import qilinadi — `qayta_ishla_sorov`
va `navbatni_ishla` ixtiyoriy `hozir` parametrini qabul qiladi (real vaqtni
kutmasdan sinash uchun).
"""
import argparse
import json
import re
import sqlite3
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import konfig, kontrakt, jurnal, heartbeat, uzatish, fayl, adapter  # noqa: E402

AGENT_ID = "SHLYUZ"
MAX_URINISH = 5  # N1/N2 tarmoq xatosida shuncha urinishdan keyin "xato"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS xabarlar (
    xabar_id TEXT PRIMARY KEY,
    idempotent_kalit TEXT UNIQUE,
    kimdan_agent TEXT,
    kanal TEXT,
    kimga_tur TEXT,
    kimga_id TEXT,
    manzil TEXT,
    skript_id TEXT,
    til TEXT,
    ozgaruvchilar TEXT,
    matn_tayyor TEXT,
    holat TEXT,
    rad_sabab TEXT,
    yaratildi TEXT,
    yuborildi TEXT,
    provayder_id TEXT,
    urinish INTEGER DEFAULT 0,
    keyingi_urinish TEXT,
    narx_som INTEGER,
    rejim TEXT
);
CREATE INDEX IF NOT EXISTS idx_manzil_skript_yaratildi
    ON xabarlar(manzil, skript_id, yaratildi);
CREATE INDEX IF NOT EXISTS idx_holat_keyingi
    ON xabarlar(holat, keyingi_urinish);
"""


def _sana(hozir: datetime) -> str:
    return hozir.strftime("%Y-%m-%d")


class Shlyuz:
    """Shlyuz mantig'i: SQLite + qayta ishlash qadamlari. HTTP'dan mustaqil —
    testlar to'g'ridan-to'g'ri chaqiradi."""

    def __init__(self, db_yol=None):
        self.db_yol = Path(db_yol) if db_yol else konfig.data("shlyuz.db")
        self.db_yol.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_yol), check_same_thread=False,
                                    isolation_level=None)  # autocommit, biz commit qilamiz
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA_SQL)

    def yop(self):
        with self.lock:
            self.conn.close()

    # ------------------------------------------------------------------
    # yordamchilar
    # ------------------------------------------------------------------
    def _jurnal_yoz(self, obj: dict, hozir: datetime):
        obj = dict(obj)
        obj.setdefault("vaqt", konfig.iso(hozir))
        jurnal.append(konfig.data("jurnal", "xabar", f"{_sana(hozir)}.jsonl"), obj)

    def _xabar_id(self, hozir: datetime) -> str:
        sana = _sana(hozir)
        n = self.conn.execute(
            "SELECT COUNT(*) FROM xabarlar WHERE yaratildi LIKE ?", (f"{sana}%",)
        ).fetchone()[0]
        return f"x-{sana}-{n + 1:06d}"

    def _manzil(self, kanal: str, kimga: dict):
        if kanal == "tg":
            v = kimga.get("telegram_id")
            if v is not None:
                return str(v)
            v = self._paketdan_kontakt(kimga.get("id"), "telegram_id")
            return str(v) if v is not None else None
        v = kimga.get("telefon")
        if v is not None:
            return v
        return self._paketdan_kontakt(kimga.get("id"), "telefon")

    def _paketdan_kontakt(self, kimga_id, kalit):
        """Agent faqat ID beradi — kontaktni (telefon/telegram_id) paketdan topamiz."""
        if not kimga_id:
            return None
        try:
            obj = fayl.json_oqi(konfig.data("paket", "joriy.json"))
        except Exception:
            return None
        for royxat_nomi, id_kaliti in (
            ("xodimlar", "xodim_id"), ("talabalar", "talaba_id"), ("lidlar", "lid_id")
        ):
            for satr in obj.get(royxat_nomi, []):
                if satr.get(id_kaliti) == kimga_id:
                    return satr.get(kalit)
        return None

    def _skript_top(self, skript_id: str):
        reestr = konfig.konfig_json("skriptlar.json")
        for s in reestr.get("skriptlar", []):
            if s.get("skript_id") == skript_id:
                return s
        return None

    def _matn_render(self, skript: dict, til: str, ozgaruvchilar: dict) -> str:
        matnlar = skript.get("matn", {})
        shablon = matnlar.get(til)
        if shablon is None and matnlar:
            shablon = next(iter(matnlar.values()))
        if shablon is None:
            shablon = ""
        return shablon.format(**ozgaruvchilar)

    def _manzil_ruxsat(self, kanal: str, manzil: str):
        """(ruxsat: bool, sabab: str|None). Qora ro'yxat oq ro'yxatdan ustun."""
        qora = konfig.konfig_json("qora_royxat.json")
        if kanal == "tg" and manzil in [str(x) for x in qora.get("telegram_id", [])]:
            return False, "QORA_ROYXAT"
        if kanal == "sms" and manzil in qora.get("telefon", []):
            return False, "QORA_ROYXAT"

        oq = konfig.konfig_json("oq_royxat.json")
        if kanal == "tg":
            ruxsat = manzil in [str(x) for x in oq.get("telegram_id", [])]
        else:
            ruxsat = manzil in oq.get("telefon", [])

        if not ruxsat:
            ruxsat = self._paket_manzilida(kanal, manzil)

        if not ruxsat:
            return False, "OQ_ROYXAT"
        return True, None

    def _paket_manzilida(self, kanal: str, manzil: str) -> bool:
        try:
            obj = fayl.json_oqi(konfig.data("paket", "joriy.json"))
        except Exception:
            return False
        kalit = "telegram_id" if kanal == "tg" else "telefon"
        for royxat_nomi in ("lidlar", "talabalar", "xodimlar"):
            for satr in obj.get(royxat_nomi, []):
                v = satr.get(kalit)
                if v is None:
                    continue
                if kanal == "tg" and str(v) == manzil:
                    return True
                if kanal == "sms" and v == manzil:
                    return True
        return False

    def _vaqt_oynasi_hisobla(self, oyna: str, hozir: datetime) -> datetime:
        """Oyna ichida bo'lsa hozir, aks holda keyingi ochilish vaqti."""
        boshlanish_s, tugash_s = oyna.split("-")
        b_h, b_m = (int(x) for x in boshlanish_s.split(":"))
        t_h, t_m = (int(x) for x in tugash_s.split(":"))
        boshlanish = hozir.replace(hour=b_h, minute=b_m, second=0, microsecond=0)
        if t_h >= 24:
            tugash = hozir.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            tugash = hozir.replace(hour=t_h, minute=t_m, second=0, microsecond=0)
        if boshlanish <= hozir < tugash:
            return hozir
        if hozir < boshlanish:
            return boshlanish
        return boshlanish + timedelta(days=1)

    def _yetkazish_tekshir_vaqti(self, hozir: datetime) -> datetime:
        s = int(konfig.env("INPLUS_SHLYUZ_YETKAZISH_S", "600"))
        return hozir + timedelta(seconds=s)

    def _rad(self, xom: dict, sabab: str, hozir: datetime,
              skript_id: str = None, kanal: str = None, manzil: str = None,
              kimga: dict = None, xabar_id: str = None):
        kimga = kimga or xom.get("kimga") or {}
        kanal = kanal or xom.get("kanal")
        skript_id = skript_id or xom.get("skript_id")
        manzil = manzil if manzil is not None else self._manzil(kanal, kimga)
        with self.lock:
            xid = xabar_id or self._xabar_id(hozir)
            self.conn.execute(
                "INSERT OR IGNORE INTO xabarlar (xabar_id, idempotent_kalit, kimdan_agent, "
                "kanal, kimga_tur, kimga_id, manzil, skript_id, til, ozgaruvchilar, "
                "matn_tayyor, holat, rad_sabab, yaratildi, rejim) VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (xid, xom.get("idempotent_kalit"), xom.get("kimdan_agent"), kanal,
                 kimga.get("tur"), kimga.get("id"), manzil, skript_id, xom.get("til"),
                 json.dumps(xom.get("ozgaruvchilar", {}), ensure_ascii=False),
                 None, "rad", sabab, konfig.iso(hozir), konfig.rejim()),
            )
        self._jurnal_yoz({"xabar_id": xid, "holat": "rad", "rad_sabab": sabab,
                          "skript_id": skript_id, "kanal": kanal, "manzil": manzil,
                          "kimdan_agent": xom.get("kimdan_agent")}, hozir)
        return 200, {"holat": "rad", "sabab": sabab}

    # ------------------------------------------------------------------
    # asosiy oqim: POST /yubor — 9 qadam (§2.8 / §5)
    # ------------------------------------------------------------------
    def qayta_ishla_sorov(self, xom: dict, hozir: datetime = None):
        hozir = hozir or konfig.hozir()

        # (1) JSON schema
        try:
            kontrakt.tekshir("xabar", xom)
        except kontrakt.KontraktXato as e:
            return self._rad(xom, "SXEMA_XATO", hozir)

        kimdan_agent = xom["kimdan_agent"]
        kanal = xom["kanal"]
        kimga = xom["kimga"]
        skript_id = xom["skript_id"]
        til = xom["til"]
        ozgaruvchilar = xom["ozgaruvchilar"]
        idempotent_kalit = xom["idempotent_kalit"]
        muhimlik = xom.get("muhimlik", "oddiy")

        # (2) skriptlar.json: bor, faol, kanal ruxsat, agent ruxsat
        skript = self._skript_top(skript_id)
        if skript is None:
            return self._rad(xom, "SKRIPT_YOQ", hozir)
        if skript.get("holat") != "faol":
            return self._rad(xom, "SKRIPT_ARXIV", hozir)
        if kanal not in skript.get("kanallar", []):
            return self._rad(xom, "KANAL_YOQ", hozir)
        ruxsat_agentlar = skript.get("ruxsat_agentlar", [])
        if "*" not in ruxsat_agentlar and kimdan_agent not in ruxsat_agentlar:
            return self._rad(xom, "AGENT_RUXSAT_YOQ", hozir)

        # (3) ozgaruvchilar to'liq -> matn render -> (sms) uzunlik
        kerakli = set(skript.get("ozgaruvchilar", []))
        if not kerakli.issubset(set(ozgaruvchilar.keys())):
            return self._rad(xom, "OZGARUVCHI_YETISHMAYDI", hozir)
        try:
            matn_tayyor = self._matn_render(skript, til, ozgaruvchilar)
        except (KeyError, IndexError, ValueError):
            return self._rad(xom, "OZGARUVCHI_YETISHMAYDI", hozir)
        if kanal == "sms":
            maxlen = skript.get("sms_uzunlik_max")
            if maxlen and len(matn_tayyor) > maxlen:
                return self._rad(xom, "SMS_UZUN", hozir)

        # (4) oq/qora ro'yxat
        manzil = self._manzil(kanal, kimga)
        if not manzil:
            return self._rad(xom, "MANZIL_YOQ", hozir)
        ruxsat, sabab = self._manzil_ruxsat(kanal, manzil)
        if not ruxsat:
            return self._rad(xom, sabab, hozir, manzil=manzil)

        # (5) idempotent_kalit UNIQUE -> dublikat (rad EMAS, 200)
        with self.lock:
            mavjud = self.conn.execute(
                "SELECT xabar_id FROM xabarlar WHERE idempotent_kalit=?",
                (idempotent_kalit,)).fetchone()
        if mavjud:
            self._jurnal_yoz({"voqea": "dublikat_urinish",
                              "idempotent_kalit": idempotent_kalit,
                              "xabar_id": mavjud["xabar_id"]}, hozir)
            return 200, {"holat": "dublikat", "xabar_id": mavjud["xabar_id"]}

        # (6) dublikat_soat: shu manzil+skript oxirgi N soatda yuborilgan
        limit = skript.get("limit", {}) or {}
        dub_soat = limit.get("dublikat_soat")
        if dub_soat:
            chegara = konfig.iso(hozir - timedelta(hours=dub_soat))
            with self.lock:
                bor = self.conn.execute(
                    "SELECT 1 FROM xabarlar WHERE manzil=? AND skript_id=? "
                    "AND holat != 'rad' AND yaratildi >= ? LIMIT 1",
                    (manzil, skript_id, chegara)).fetchone()
            if bor:
                return self._rad(xom, "DUBLIKAT", hozir, manzil=manzil)

        # (7) limitlar
        bugun_str = _sana(hozir)
        bir_kunlik = limit.get("bir_odamga_kunlik")
        if bir_kunlik:
            with self.lock:
                n = self.conn.execute(
                    "SELECT COUNT(*) FROM xabarlar WHERE manzil=? AND skript_id=? "
                    "AND holat != 'rad' AND substr(yaratildi,1,10)=?",
                    (manzil, skript_id, bugun_str)).fetchone()[0]
            if n >= bir_kunlik:
                return self._rad(xom, "LIMIT_KUNLIK", hozir, manzil=manzil)
        kunlik_jami = limit.get("kunlik_jami")
        if kunlik_jami:
            with self.lock:
                n = self.conn.execute(
                    "SELECT COUNT(*) FROM xabarlar WHERE skript_id=? "
                    "AND holat != 'rad' AND substr(yaratildi,1,10)=?",
                    (skript_id, bugun_str)).fetchone()[0]
            if n >= kunlik_jami:
                return self._rad(xom, "LIMIT_KUNLIK", hozir, manzil=manzil)

        # (8) vaqt_oynasi -> kechiktirish (rad EMAS), kritik -> darhol
        keyingi_urinish = hozir
        oyna = skript.get("vaqt_oynasi")
        if oyna and muhimlik != "kritik":
            keyingi_urinish = self._vaqt_oynasi_hisobla(oyna, hozir)

        # (9) INSERT + jurnal + uzatish
        # Idempotentlik poygasi (TOCTOU): (5)-tekshiruv bilan INSERT orasida
        # parallel oqim shu idempotent_kalit ni kiritib ulgurishi mumkin ->
        # UNIQUE buziladi. Uni ushlab, dublikat sifatida qaytaramiz (500 emas).
        with self.lock:
            xabar_id = self._xabar_id(hozir)
            try:
                self.conn.execute(
                    "INSERT INTO xabarlar (xabar_id, idempotent_kalit, kimdan_agent, kanal, "
                    "kimga_tur, kimga_id, manzil, skript_id, til, ozgaruvchilar, matn_tayyor, "
                    "holat, rad_sabab, yaratildi, yuborildi, provayder_id, urinish, "
                    "keyingi_urinish, narx_som, rejim) VALUES "
                    "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (xabar_id, idempotent_kalit, kimdan_agent, kanal, kimga.get("tur"),
                     kimga.get("id"), manzil, skript_id, til,
                     json.dumps(ozgaruvchilar, ensure_ascii=False), matn_tayyor,
                     "navbatda", None, konfig.iso(hozir), None, None, 0,
                     konfig.iso(keyingi_urinish), None, konfig.rejim()),
                )
            except sqlite3.IntegrityError:
                mavjud = self.conn.execute(
                    "SELECT xabar_id FROM xabarlar WHERE idempotent_kalit=?",
                    (idempotent_kalit,)).fetchone()
                eski = mavjud["xabar_id"] if mavjud else None
                return 200, {"holat": "dublikat", "xabar_id": eski}
        self._jurnal_yoz({"xabar_id": xabar_id, "holat": "navbatda",
                          "skript_id": skript_id, "kanal": kanal, "manzil": manzil,
                          "kimdan_agent": kimdan_agent,
                          "keyingi_urinish": konfig.iso(keyingi_urinish)}, hozir)
        kimga_n = "N1" if kanal == "sms" else "N2"
        uzatish.berdi(kimdan_agent, xabar_id, fayl.hash_matn(matn_tayyor),
                      tur="xabar", kimga=kimga_n, soni={"xabar": 1}, sana=bugun_str)

        return 200, {"xabar_id": xabar_id, "holat": "navbatda"}

    # ------------------------------------------------------------------
    # navbat ishchisi
    # ------------------------------------------------------------------
    def _yangila(self, xabar_id: str, **maydonlar):
        agar_ustun = {"holat", "rad_sabab", "yuborildi", "provayder_id", "urinish",
                      "keyingi_urinish", "narx_som"}
        maydonlar = {k: v for k, v in maydonlar.items() if k in agar_ustun}
        if not maydonlar:
            return
        ustunlar = ", ".join(f"{k}=?" for k in maydonlar)
        qiymatlar = list(maydonlar.values()) + [xabar_id]
        with self.lock:
            self.conn.execute(f"UPDATE xabarlar SET {ustunlar} WHERE xabar_id=?", qiymatlar)

    def _jurnal_holat(self, xabar_id: str, holat: str, hozir: datetime, **qoshimcha):
        obj = {"xabar_id": xabar_id, "holat": holat}
        obj.update(qoshimcha)
        self._jurnal_yoz(obj, hozir)

    def _birlik_s(self) -> int:
        return 1 if konfig.env("INPLUS_SHLYUZ_TEZ", "0") == "1" else 60

    def _shlyuz_ichki_ogohlantirish(self, xabar_matni: str, hozir: datetime):
        """Shlyuzning o'z ichki, tuzatib bo'lmas xatolarini S-900 orqali
        direktor/xodimga yetkazadi. `SHLYUZ` konfig/skriptlar.json S-900
        ruxsat_agentlar ro'yxatida (minimal, hujjatlashtirilgan qo'shimcha)."""
        try:
            tg_admin = konfig.env("TG_ADMIN_ID", "")
            kimga = {"tur": "xodim", "id": "X-001",
                     "telegram_id": int(tg_admin) if tg_admin else None,
                     "telefon": None}
            xom = {
                "kimdan_agent": "SHLYUZ", "kanal": "tg", "kimga": kimga,
                "skript_id": "S-900", "til": "uz",
                "ozgaruvchilar": {"agent": "SHLYUZ", "xabar": xabar_matni,
                                  "vaqt": konfig.iso(hozir)},
                "idempotent_kalit": f"SHLYUZ:S-900:{hash(xabar_matni) & 0xffffffff}:{_sana(hozir)}",
                "muhimlik": "kritik",
            }
            self.qayta_ishla_sorov(xom, hozir=hozir)
        except Exception:
            traceback.print_exc()

    def navbatni_ishla(self, hozir: datetime = None, limit: int = 20):
        hozir = hozir or konfig.hozir()
        hozir_str = konfig.iso(hozir)
        with self.lock:
            qatorlar = self.conn.execute(
                "SELECT * FROM xabarlar WHERE holat='navbatda' AND "
                "(keyingi_urinish IS NULL OR keyingi_urinish <= ?) "
                "ORDER BY yaratildi LIMIT ?", (hozir_str, limit)).fetchall()
        for row in qatorlar:
            self._yubor_va_yangila(dict(row), hozir)

        with self.lock:
            kutilayotgan = self.conn.execute(
                "SELECT * FROM xabarlar WHERE holat='yuborildi' AND kanal='sms' "
                "AND keyingi_urinish IS NOT NULL AND keyingi_urinish <= ?",
                (hozir_str,)).fetchall()
        for row in kutilayotgan:
            self._sms_holat_tekshir(dict(row), hozir)

    def _yubor_va_yangila(self, row: dict, hozir: datetime):
        xabar_id = row["xabar_id"]
        with self.lock:
            self.conn.execute("UPDATE xabarlar SET holat='yuborilmoqda' WHERE xabar_id=?",
                              (xabar_id,))
        if row["kanal"] == "tg":
            self._tg_yubor(row, hozir)
        else:
            self._sms_yubor(row, hozir)

    def _tg_yubor(self, row: dict, hozir: datetime):
        xabar_id = row["xabar_id"]
        manzil = row["manzil"]
        urinish = (row["urinish"] or 0) + 1
        tarmoq_xato = None
        javob = {}
        try:
            t = adapter.ol("telegram")
            chat_id = int(manzil) if str(manzil).lstrip("-").isdigit() else manzil
            javob = t.yubor(chat_id, row["matn_tayyor"])
        except Exception as e:
            tarmoq_xato = e

        if tarmoq_xato is not None:
            if urinish < MAX_URINISH:
                kutish = (2 ** urinish) * self._birlik_s()
                keyingi = hozir + timedelta(seconds=kutish)
                self._yangila(xabar_id, holat="navbatda", urinish=urinish,
                              keyingi_urinish=konfig.iso(keyingi))
                self._jurnal_holat(xabar_id, "urinish_xato", hozir, sabab=str(tarmoq_xato))
            else:
                self._yangila(xabar_id, holat="xato", urinish=urinish,
                              rad_sabab=str(tarmoq_xato))
                self._jurnal_holat(xabar_id, "xato", hozir, sabab=str(tarmoq_xato))
            return

        holat = javob.get("holat")
        if holat == "ok":
            self._yangila(xabar_id, holat="yuborildi",
                          provayder_id=str(javob.get("provayder_id")),
                          yuborildi=konfig.iso(hozir), urinish=urinish,
                          keyingi_urinish=None)
            self._jurnal_holat(xabar_id, "yuborildi", hozir,
                               provayder_id=javob.get("provayder_id"))
            return
        if holat == "kechiktir":
            kutish = javob.get("retry_after", 1)
            keyingi = hozir + timedelta(seconds=kutish)
            self._yangila(xabar_id, holat="navbatda", urinish=urinish,
                          keyingi_urinish=konfig.iso(keyingi))
            self._jurnal_holat(xabar_id, "kechiktirildi", hozir,
                               sabab=f"429 retry_after={kutish}")
            return
        # xato — bot bloklangan / chat topilmadi: urinish YO'Q, darhol xato
        self._yangila(xabar_id, holat="xato", urinish=urinish,
                      rad_sabab=javob.get("sabab", "TG_XATO"))
        self._jurnal_holat(xabar_id, "xato", hozir, sabab=javob.get("sabab"))

    def _sms_yubor(self, row: dict, hozir: datetime):
        xabar_id = row["xabar_id"]
        manzil = row["manzil"]
        urinish = (row["urinish"] or 0) + 1
        tarmoq_xato = None
        javob = {}
        try:
            s = adapter.ol("sms")
            javob = s.yubor(manzil, row["matn_tayyor"])
        except Exception as e:
            tarmoq_xato = e

        if tarmoq_xato is None and javob.get("holat") == "ok":
            keyingi = self._yetkazish_tekshir_vaqti(hozir)
            self._yangila(xabar_id, holat="yuborildi",
                          provayder_id=str(javob.get("provayder_id")),
                          yuborildi=konfig.iso(hozir), urinish=urinish,
                          narx_som=javob.get("narx_som"),
                          keyingi_urinish=konfig.iso(keyingi))
            self._jurnal_holat(xabar_id, "yuborildi", hozir,
                               provayder_id=javob.get("provayder_id"),
                               narx_som=javob.get("narx_som"))
            return

        http_kod = None if tarmoq_xato is not None else javob.get("http")
        sabab = str(tarmoq_xato) if tarmoq_xato is not None else str(javob.get("sabab") or http_kod)

        if http_kod == 429:
            kutish = (2 ** min(urinish, MAX_URINISH)) * self._birlik_s()
            keyingi = hozir + timedelta(seconds=kutish)
            self._yangila(xabar_id, holat="navbatda", urinish=urinish,
                          keyingi_urinish=konfig.iso(keyingi))
            self._jurnal_holat(xabar_id, "kechiktirildi", hozir, sabab="ETS 429")
            return

        if urinish < MAX_URINISH:
            kutish = (2 ** urinish) * self._birlik_s()
            keyingi = hozir + timedelta(seconds=kutish)
            self._yangila(xabar_id, holat="navbatda", urinish=urinish,
                          keyingi_urinish=konfig.iso(keyingi))
            self._jurnal_holat(xabar_id, "urinish_xato", hozir, sabab=sabab)
            return

        self._yangila(xabar_id, holat="xato", urinish=urinish, rad_sabab=sabab)
        self._jurnal_holat(xabar_id, "xato", hozir, sabab=sabab)
        self._shlyuz_ichki_ogohlantirish(
            f"SMS {xabar_id} {MAX_URINISH} urinishdan keyin xato ({sabab})", hozir)

    def _sms_holat_tekshir(self, row: dict, hozir: datetime):
        xabar_id = row["xabar_id"]
        try:
            s = adapter.ol("sms")
            javob = s.holat(row["provayder_id"])
        except Exception:
            # provayder javob bermasa — 'yuborildi' da qoladi, keyinroq qayta urinamiz
            self._yangila(xabar_id, keyingi_urinish=konfig.iso(hozir + timedelta(minutes=10)))
            return
        hol = javob.get("holat")
        if hol == "yetkazildi":
            self._yangila(xabar_id, holat="yetkazildi", keyingi_urinish=None)
            self._jurnal_holat(xabar_id, "yetkazildi", hozir)
        elif hol == "xato":
            self._yangila(xabar_id, holat="xato", rad_sabab="ETS_HOLAT_XATO",
                          keyingi_urinish=None)
            self._jurnal_holat(xabar_id, "xato", hozir, sabab="ETS holat: xato")
        else:
            # provayderda status yo'q — 'yuborildi' da qoladi (N3 alohida ustunda ko'radi)
            self._yangila(xabar_id, keyingi_urinish=None)

    # ------------------------------------------------------------------
    # o'qish (HTTP GET)
    # ------------------------------------------------------------------
    def holat(self, xabar_id: str):
        with self.lock:
            row = self.conn.execute("SELECT * FROM xabarlar WHERE xabar_id=?",
                                    (xabar_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        try:
            d["ozgaruvchilar"] = json.loads(d.get("ozgaruvchilar") or "{}")
        except Exception:
            pass
        return d

    def statistika(self):
        with self.lock:
            kesim = [dict(r) for r in self.conn.execute(
                "SELECT kanal, skript_id, holat, COUNT(*) AS n, "
                "COALESCE(SUM(narx_som), 0) AS narx_som FROM xabarlar "
                "GROUP BY kanal, skript_id, holat ORDER BY kanal, skript_id, holat")]
            jami = self.conn.execute("SELECT COUNT(*) FROM xabarlar").fetchone()[0]
        return {"jami": jami, "kesim": kesim}


# ----------------------------------------------------------------------
# HTTP qatlami
# ----------------------------------------------------------------------
def _handler_klass(shlyuz: Shlyuz):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _javob(self, kod, obj):
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(kod)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != "/yubor":
                return self._javob(404, {"xato": "noma'lum yo'l"})
            uz = int(self.headers.get("Content-Length", 0))
            gavda = self.rfile.read(uz) if uz else b"{}"
            try:
                xom = json.loads(gavda.decode("utf-8"))
            except Exception:
                return self._javob(400, {"holat": "rad", "sabab": "JSON_XATO"})
            try:
                kod, javob = shlyuz.qayta_ishla_sorov(xom)
            except Exception as e:
                traceback.print_exc()
                return self._javob(500, {"holat": "xato", "sabab": str(e)})
            self._javob(kod, javob)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/statistika":
                return self._javob(200, shlyuz.statistika())
            if parsed.path.startswith("/holat/"):
                xabar_id = parsed.path[len("/holat/"):]
                row = shlyuz.holat(xabar_id)
                if row is None:
                    return self._javob(404, {"xato": "topilmadi"})
                return self._javob(200, row)
            return self._javob(404, {"xato": "noma'lum yo'l"})

    return Handler


class _NavbatIshchisi(threading.Thread):
    def __init__(self, shlyuz: Shlyuz, oraliq_s: float = 1.0):
        super().__init__(daemon=True, name="shlyuz-navbat")
        self.shlyuz = shlyuz
        self.oraliq_s = oraliq_s
        self._toxta = threading.Event()

    def toxtat(self):
        self._toxta.set()

    def run(self):
        while not self._toxta.is_set():
            try:
                self.shlyuz.navbatni_ishla()
            except Exception:
                traceback.print_exc()
            self._toxta.wait(self.oraliq_s)


class _HeartbeatIshchisi(threading.Thread):
    def __init__(self, oraliq_s: float = 30.0):
        super().__init__(daemon=True, name="shlyuz-heartbeat")
        self.oraliq_s = oraliq_s
        self._toxta = threading.Event()
        self._boshlandi = konfig.iso()

    def toxtat(self):
        self._toxta.set()

    def run(self):
        while not self._toxta.is_set():
            try:
                heartbeat.yoz(AGENT_ID, "ishlayapti", boshlandi=self._boshlandi)
            except Exception:
                traceback.print_exc()
            self._toxta.wait(self.oraliq_s)


def serverni_yasa(port: int = None, db_yol=None):
    port = port or int(konfig.env("INPLUS_SHLYUZ_PORT", "8471"))
    shlyuz = Shlyuz(db_yol=db_yol)
    Handler = _handler_klass(shlyuz)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server, shlyuz


def main(argv=None):
    ap = argparse.ArgumentParser(description="IN PLUS shlyuz (N1 SMS + N2 Telegram)")
    ap.add_argument("--port", type=int, default=None)
    args = ap.parse_args(argv)

    server, shlyuz = serverni_yasa(port=args.port)
    heartbeat.yoz(AGENT_ID, "boshladi", boshlandi=konfig.iso())
    hb = _HeartbeatIshchisi()
    navbat = _NavbatIshchisi(shlyuz)
    hb.start()
    navbat.start()
    print(f"shlyuz: http://127.0.0.1:{server.server_address[1]} "
          f"(db={shlyuz.db_yol})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        heartbeat.yoz(AGENT_ID, "tugadi", boshlandi=konfig.iso())
        navbat.toxtat()
        hb.toxtat()
        server.shutdown()
        shlyuz.yop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
