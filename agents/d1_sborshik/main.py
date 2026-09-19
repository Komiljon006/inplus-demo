#!/usr/bin/env python3
"""D1 — Sborshik dannyx (И0, timer 06:00; D6 dan keyin ishlaydi).

Kirish : amocrm.lidlar(kundan=-90), amocrm.xodimlar(), getcourse.talabalar(),
         getcourse.tolovlar(kundan=-30), courses.oqi().
Ish    : har manbani ALOHIDA try ichida oladi — biri yiqilsa
         manbalar.<x>.holat=eski va OLDINGI (joriy.json) paketdan shu bo'lim
         qayta ishlatiladi -> normalizatsiya (telefon E.164, ID prefiks,
         bosqich xaritasi, kurs_id/guruh_id courses'da borligini tekshirish)
         -> statistika -> kontrakt.tekshir("paket") -> paket.yoz().
Chiqish: data/paket/<sana>.json (+ joriy.json symlink), uzatish(berdi, *),
         KPI, biror manba muammoli bo'lsa shlyuz.yubor(S-900, direktor).

INPLUS_MOCK_YIQIL=amocrm|getcourse|sheets — shu manbani sun'iy yiqitadi (demo/test).
"""
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import konfig, adapter, paket, courses, fayl, shlyuz_client  # noqa: E402
from inplus.agent import Agent, ishga_tushir  # noqa: E402

GURUH_ID_RE = re.compile(r"^G-[A-Z]{2,5}-\d{2}-[A-Z]{3}$")
UZ_TELEFON_RE = re.compile(r"^\+998\d{9}$")


def _yiqiladigan(nomi: str) -> bool:
    majbur = konfig.env("INPLUS_MOCK_YIQIL", "").strip().lower()
    return majbur == nomi


def normalize_telefon(xom):
    """Har xil formatdagi telefonni +998XXXXXXXXX ga keltiradi. Bo'lmasa None."""
    if xom is None:
        return None
    matn = str(xom).strip()
    if not matn:
        return None
    raqamlar = re.sub(r"[^\d]", "", matn)
    agar_xorij = matn.startswith("+") and not matn.startswith("+998")
    if agar_xorij:
        return None
    if raqamlar.startswith("998") and len(raqamlar) == 12:
        kand = "+" + raqamlar
    elif len(raqamlar) == 9:
        kand = "+998" + raqamlar
    else:
        return None
    return kand if UZ_TELEFON_RE.match(kand) else None


def _int(v, standart=0):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return standart


def _int_yoki_none(v):
    try:
        s = str(v).strip()
        return int(s) if s != "" else None
    except (TypeError, ValueError):
        return None


def _epoch_iso(ts):
    if ts is None:
        return None
    try:
        dt = datetime.fromtimestamp(int(ts), tz=konfig.TASHKENT)
        return konfig.iso(dt)
    except (TypeError, ValueError, OSError):
        return None


class D1(Agent):
    agent_id = "D1"
    nom = "Sborshik dannyx"

    def ish(self) -> dict:
        oldingi = self._oldingi_paket()
        kpi = {"manba_ok": 0, "manba_eski": 0, "manba_xato": 0,
               "telefon_normalizatsiya_xato": 0, "kurs_id_topilmadi": 0,
               "guruh_id_topilmadi": 0}

        courses_obj, manba_sheets = self._olish_sheets(oldingi)
        kurs_idlar = courses.kurs_idlar(courses_obj) if courses_obj else set()
        guruh_idlar = courses.guruh_idlar(courses_obj) if courses_obj else set()

        lidlar, xodimlar, manba_amocrm = self._olish_amocrm(oldingi, kurs_idlar, kpi)
        talabalar, tolovlar, manba_getcourse = self._olish_getcourse(
            oldingi, kurs_idlar, guruh_idlar, kpi)

        manbalar = {"amocrm": manba_amocrm, "getcourse": manba_getcourse, "sheets": manba_sheets}
        for m in manbalar.values():
            if m["holat"] == "ok":
                kpi["manba_ok"] += 1
            elif m["holat"] == "eski":
                kpi["manba_eski"] += 1
            else:
                kpi["manba_xato"] += 1

        if kpi["manba_ok"] == 0 and kpi["manba_eski"] == 0:
            raise RuntimeError("D1: barcha manbalar yiqildi (amocrm+getcourse+sheets); "
                               "paket yozilmaydi, joriy.json o'zgarmaydi")

        statistika = self._statistika(lidlar, talabalar, tolovlar)

        if courses_obj is not None:
            kurslar_ref = {"fayl": "data/courses.json", "hash": fayl.hash_obj(courses_obj),
                           "versiya": courses_obj.get("versiya", "1.0")}
        elif oldingi:
            kurslar_ref = oldingi.get("kurslar_ref", {"fayl": "data/courses.json",
                                                       "hash": "sha256:000000", "versiya": "1.0"})
        else:
            kurslar_ref = {"fayl": "data/courses.json", "hash": "sha256:000000", "versiya": "1.0"}

        obj = {
            "versiya": "1.0",
            "paket_id": self.sana,
            "yaratildi": konfig.iso(),
            "rejim": konfig.rejim(),
            "hash": "sha256:000000",  # pastda qayta hisoblanadi
            "holat_umumiy": "toliq" if all(m["holat"] == "ok" for m in manbalar.values()) else "qisman",
            "manbalar": manbalar,
            "kurslar_ref": kurslar_ref,
            "lidlar": lidlar,
            "talabalar": talabalar,
            "tolovlar": tolovlar,
            "xodimlar": xodimlar,
            "statistika": statistika,
        }
        # Hash faqat MAZMUNDAN (lidlar/talabalar/...) hisoblanadi — "yaratildi",
        # "olindi", "davomiylik_s" kabi har ishga tushishda o'zgaradigan
        # maydonlar KIRMAYDI. Aks holda ikki marta ishga tushirish idempotent
        # bo'lmay qoladi (har safar yangi hash -> ortiqcha uzatish yozuvi).
        obj["hash"] = fayl.hash_obj({
            "lidlar": lidlar, "talabalar": talabalar, "tolovlar": tolovlar,
            "xodimlar": xodimlar, "statistika": statistika,
            "kurslar_ref": kurslar_ref,
            "manbalar_holat": {nom: m["holat"] for nom, m in manbalar.items()},
        })

        paket.yoz(obj, kim=self.agent_id, kutish_daq=180)

        muammoli = [nom for nom, m in manbalar.items() if m["holat"] != "ok"]
        if muammoli:
            self._s900_yubor(muammoli, manbalar, xodimlar)

        return {
            "kirdi": {"amocrm": manbalar["amocrm"]["qator"],
                      "getcourse": manbalar["getcourse"]["qator"],
                      "sheets": manbalar["sheets"]["qator"]},
            "chiqdi": {"lidlar": len(lidlar), "talabalar": len(talabalar), "paket": 1},
            "kpi": kpi,
        }

    # ------------------------------------------------------------------ #
    # Manba olish (har biri mustaqil try, yiqilsa oldingi paketdan olinadi) #
    # ------------------------------------------------------------------ #

    def _oldingi_paket(self):
        try:
            p = paket.joriy_yol()
            if p.exists():
                return fayl.json_oqi(p)
        except Exception:
            pass
        return None

    def _olish_sheets(self, oldingi):
        t0 = time.monotonic()
        try:
            if _yiqiladigan("sheets"):
                raise RuntimeError("simulyatsiya: sheets/courses yiqildi (INPLUS_MOCK_YIQIL)")
            obj = courses.oqi(self.agent_id)
            qator = obj.get("manba", {}).get("qator", len(obj.get("kurslar", [])))
            manba = {"holat": "ok", "olindi": konfig.iso(), "qator": qator,
                     "davomiylik_s": round(time.monotonic() - t0, 3), "xato": None}
            return obj, manba
        except Exception as e:
            xabar = f"{type(e).__name__}: {e}"
            obj = None
            try:
                obj = fayl.json_oqi(courses.yol())
            except Exception:
                obj = None
            if obj is not None:
                manba = {"holat": "eski", "olindi": obj.get("yaratildi"),
                         "qator": obj.get("manba", {}).get("qator", len(obj.get("kurslar", []))),
                         "davomiylik_s": round(time.monotonic() - t0, 3),
                         "xato": f"{xabar}; eski courses.json ishlatildi",
                         "ogohlantirish": ["kontrakt.tekshir dan o'tmadi"]}
                return obj, manba
            if oldingi and "sheets" in oldingi.get("manbalar", {}):
                manba = dict(oldingi["manbalar"]["sheets"])
                manba["holat"] = "eski"
                manba["xato"] = f"{xabar}; kechagi nusxa ishlatildi"
                return None, manba
            return None, {"holat": "xato", "olindi": None, "qator": 0,
                          "davomiylik_s": round(time.monotonic() - t0, 3), "xato": xabar}

    def _olish_amocrm(self, oldingi, kurs_idlar, kpi):
        t0 = time.monotonic()
        try:
            if _yiqiladigan("amocrm"):
                raise RuntimeError("simulyatsiya: amocrm yiqildi (INPLUS_MOCK_YIQIL)")
            am = adapter.ol("amocrm")
            leads_raw = am.lidlar(kundan=-90)["_embedded"]["leads"]
            xodimlar_raw = am.xodimlar()["_embedded"]["users"]
            bosqich_xarita = konfig.konfig_json("amocrm_bosqich.json").get("status", {})
            lidlar = [self._lid_normalize(l, bosqich_xarita, kurs_idlar, kpi) for l in leads_raw]
            xodimlar = [self._xodim_normalize(u) for u in xodimlar_raw]
            manba = {"holat": "ok", "olindi": konfig.iso(), "qator": len(lidlar),
                     "davomiylik_s": round(time.monotonic() - t0, 3), "xato": None}
            return lidlar, xodimlar, manba
        except Exception as e:
            xabar = f"{type(e).__name__}: {e}"
            if oldingi and oldingi.get("lidlar") is not None:
                lidlar = oldingi.get("lidlar", [])
                xodimlar = oldingi.get("xodimlar", [])
                manba = dict(oldingi["manbalar"]["amocrm"])
                manba["holat"] = "eski"
                manba["qator"] = len(lidlar)
                manba["xato"] = f"{xabar}; kechagi nusxa ishlatildi"
                return lidlar, xodimlar, manba
            return [], [], {"holat": "xato", "olindi": None, "qator": 0,
                            "davomiylik_s": round(time.monotonic() - t0, 3), "xato": xabar}

    def _olish_getcourse(self, oldingi, kurs_idlar, guruh_idlar, kpi):
        t0 = time.monotonic()
        try:
            if _yiqiladigan("getcourse"):
                raise RuntimeError("simulyatsiya: getcourse yiqildi (INPLUS_MOCK_YIQIL)")
            gc = adapter.ol("getcourse")
            tal_raw = gc.talabalar()
            pay_raw = gc.tolovlar(kundan=-30)
            t_fields = tal_raw["data"]["fields"]
            talabalar = [self._talaba_normalize(dict(zip(t_fields, row)), kurs_idlar,
                                                 guruh_idlar, kpi)
                         for row in tal_raw["data"]["rows"]]
            p_fields = pay_raw["data"]["fields"]
            tolovlar = [self._tolov_normalize(dict(zip(p_fields, row)))
                        for row in pay_raw["data"]["rows"]]
            manba = {"holat": "ok", "olindi": konfig.iso(), "qator": len(talabalar),
                     "davomiylik_s": round(time.monotonic() - t0, 3), "xato": None}
            return talabalar, tolovlar, manba
        except Exception as e:
            xabar = f"{type(e).__name__}: {e}"
            if oldingi and oldingi.get("talabalar") is not None:
                talabalar = oldingi.get("talabalar", [])
                tolovlar = oldingi.get("tolovlar", [])
                manba = dict(oldingi["manbalar"]["getcourse"])
                manba["holat"] = "eski"
                manba["qator"] = len(talabalar)
                manba["xato"] = f"{xabar}; kechagi nusxa ishlatildi"
                return talabalar, tolovlar, manba
            return [], [], {"holat": "xato", "olindi": None, "qator": 0,
                            "davomiylik_s": round(time.monotonic() - t0, 3), "xato": xabar}

    # ------------------------------------------------------------------ #
    # Normalizatsiya                                                      #
    # ------------------------------------------------------------------ #

    def _lid_normalize(self, lead, bosqich_xarita, kurs_idlar, kpi):
        cf = {}
        for f in lead.get("custom_fields_values") or []:
            vals = f.get("values") or []
            if vals:
                cf[f.get("field_code")] = vals[0].get("value")

        telefon_xom = cf.get("PHONE")
        telefon = normalize_telefon(telefon_xom)
        if telefon is None and telefon_xom:
            kpi["telefon_normalizatsiya_xato"] += 1

        status_id = lead.get("status_id")
        bosqich = bosqich_xarita.get(str(status_id), "yangi")

        kurs_id = cf.get("KURS") or None
        if kurs_id and kurs_idlar and kurs_id not in kurs_idlar:
            kpi["kurs_id_topilmadi"] += 1
            kurs_id = None

        menejer_raw = lead.get("responsible_user_id")
        menejer_id = f"X-{menejer_raw}" if menejer_raw is not None else None

        teglar = [t.get("name") for t in lead.get("_embedded", {}).get("tags", []) if t.get("name")]

        return {
            "lid_id": f"amo:{lead['id']}",
            "manba": "amocrm",
            "ism": lead.get("name") or "",
            "telefon": telefon,
            "telegram_id": None,
            "bosqich": bosqich,
            "bosqich_kodi": status_id,
            "kurs_id": kurs_id,
            "menejer_id": menejer_id,
            "yaratildi": _epoch_iso(lead.get("created_at")) or konfig.iso(),
            "oxirgi_aloqa": _epoch_iso(lead.get("updated_at")),
            "manba_kanal": cf.get("KANAL"),
            "summa": lead.get("price"),
            "teglar": teglar,
            "xom": {"pipeline_id": lead.get("pipeline_id"), "status_id": status_id},
        }

    def _xodim_normalize(self, u):
        uid = u.get("id")
        ism = u.get("name") or u.get("ism") or ""
        rol = "direktor" if str(ism).strip().lower() == "direktor" else "menejer"
        telegram_id = None
        if rol == "direktor":
            tg = konfig.env("TG_ADMIN_ID", "").strip()
            telegram_id = int(tg) if tg.isdigit() else None
        return {
            "xodim_id": f"X-{uid}",
            "ism": ism,
            "rol": rol,
            "telefon": normalize_telefon(u.get("phone")),
            "telegram_id": telegram_id,
            "faol": True,
        }

    def _talaba_normalize(self, row, kurs_idlar, guruh_idlar, kpi):
        uid = row.get("user_id")
        kurs_id = row.get("kurs_id") or None
        if kurs_id and kurs_idlar and kurs_id not in kurs_idlar:
            kpi["kurs_id_topilmadi"] += 1
            kurs_id = None

        guruh_id = row.get("guruh_kod") or None
        if guruh_id and not GURUH_ID_RE.match(guruh_id):
            kpi["guruh_id_topilmadi"] += 1
            guruh_id = None
        elif guruh_id and guruh_idlar and guruh_id not in guruh_idlar:
            kpi["guruh_id_topilmadi"] += 1
            guruh_id = None

        telefon_xom = row.get("telefon")
        telefon = normalize_telefon(telefon_xom)
        if telefon is None and telefon_xom:
            kpi["telefon_normalizatsiya_xato"] += 1

        jami = _int(row.get("jami"))
        tolandi = _int(row.get("tolandi"))
        qarz = max(jami - tolandi, 0)

        tg_xom = row.get("telegram_id")
        telegram_id = _int_yoki_none(tg_xom)

        return {
            "talaba_id": f"gc:{uid}",
            "ism": row.get("ism") or "",
            "telefon": telefon,
            "telegram_id": telegram_id,
            "email": row.get("email") or None,
            "kurs_id": kurs_id,
            "guruh_id": guruh_id,
            "holat": row.get("holat") or "faol",
            "boshladi": row.get("boshladi") or None,
            "tolov": {"jami": jami, "tolandi": tolandi, "qarz": qarz,
                      "keyingi_sana": self._keyingi_tolov_sana() if qarz > 0 else None,
                      "valyuta": "UZS"},
            "davomat_foiz": _int_yoki_none(row.get("davomat_foiz")),
            "oxirgi_dars": None,
            "progress_foiz": _int_yoki_none(row.get("progress_foiz")),
            "xom": row,
        }

    def _tolov_normalize(self, row):
        return {
            "tolov_id": f"gc:{row.get('tolov_id')}",
            "talaba_id": f"gc:{row.get('user_id')}",
            "summa": _int(row.get("summa")),
            "valyuta": row.get("valyuta") or "UZS",
            "sana": row.get("sana"),
            "usul": row.get("usul") or None,
            "kurs_id": row.get("kurs_id") or None,
            "izoh": row.get("izoh") or None,
        }

    def _keyingi_tolov_sana(self):
        try:
            dt = datetime.strptime(self.sana, "%Y-%m-%d") + timedelta(days=30)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    def _statistika(self, lidlar, talabalar, tolovlar):
        kecha = None
        try:
            kecha = (datetime.strptime(self.sana, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            pass
        faol_talabalar = sum(1 for t in talabalar if t.get("holat") == "faol")
        qarzdorlar = sum(1 for t in talabalar if t.get("tolov", {}).get("qarz", 0) > 0)
        qarz_jami = sum(t.get("tolov", {}).get("qarz", 0) for t in talabalar)
        tolovlar_kecha = sum(1 for p in tolovlar if kecha and p.get("sana") == kecha)
        return {
            "lidlar": len(lidlar), "talabalar": len(talabalar),
            "faol_talabalar": faol_talabalar, "qarzdorlar": qarzdorlar,
            "qarz_jami": qarz_jami, "tolovlar_kecha": tolovlar_kecha,
        }

    # ------------------------------------------------------------------ #
    # Xabar                                                               #
    # ------------------------------------------------------------------ #

    def _s900_yubor(self, muammoli, manbalar, xodimlar):
        direktor = next((x for x in xodimlar if x.get("rol") == "direktor"), None)
        tg_admin = konfig.env("TG_ADMIN_ID", "").strip()
        telegram_id = direktor.get("telegram_id") if direktor else None
        if telegram_id is None and tg_admin.isdigit():
            telegram_id = int(tg_admin)
        xodim_id = direktor.get("xodim_id") if direktor else "direktor"
        telefon = direktor.get("telefon") if direktor else None

        tafsilot = "; ".join(f"{nom}: {manbalar[nom].get('xato')}" for nom in muammoli)
        shlyuz_client.yubor(
            kimdan_agent=self.agent_id, kanal="tg",
            kimga={"tur": "xodim", "id": xodim_id, "telegram_id": telegram_id, "telefon": telefon},
            skript_id="S-900", til="uz",
            ozgaruvchilar={"agent": self.agent_id, "xabar": f"manba muammosi: {tafsilot}",
                           "vaqt": konfig.iso()},
            idempotent_kalit=f"D1:S-900:{self.sana}:{'-'.join(muammoli)}",
        )


if __name__ == "__main__":
    sys.exit(ishga_tushir(D1))
