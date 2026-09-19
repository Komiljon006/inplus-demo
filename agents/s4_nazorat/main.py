#!/usr/bin/env python3
"""S4 — Menejer nazorati (2-blok, «Sotuv va CRM», kontrolyor, И0).

Mijozning ASOSIY dardi: «lid keladi-yu menejer ishlamaydi / javobsiz
qoladi» — buni ko'rish uchun oldin CRM'ga qo'lda kirish, filtr qo'yish,
sanash kerak edi. S4 buni har kuni avtomat qiladi.

Kirish : paket.oqi() — joriy paket (D1 chiqishi): `lidlar` (bosqich,
         yaratildi, oxirgi_aloqa, menejer_id, manba_kanal) va `xodimlar`
         (ism, rol) bo'limlari. BOSHQA HECH NARSA o'qilmaydi.
Ish    : har menejer (`lidlar[].menejer_id`) bo'yicha HAQIQIY hisoblaydi:
  - lid       : shu menejerga biriktirilgan lidlar soni.
  - ishlangan : `oxirgi_aloqa > yaratildi` — kamida bitta aloqa bo'lgan.
  - javobsiz  : `bosqich == "yangi"` VA (`oxirgi_aloqa` yo'q YOKI
                `oxirgi_aloqa == yaratildi`) — «hech kim tegmagan».
  - reaksiya_soat : `ishlangan` lidlar bo'yicha o'rtacha (yaratildi ->
                     oxirgi_aloqa) soat — menejer qanchalik tez ishlashini
                     ko'rsatadi.
  `javobsiz_lidlar` — barcha javobsiz lidlar (menejeridan qat'iy nazar),
  eng ko'p kun tegmagandan boshlab (top 15) — direktor birinchi navbatda
  KIMGA qarashini ko'radi.
Chiqish: data/nazorat.json, KPI.

Bu agent HECH NARSA YOZMAYDI/yubormaydi tashqariga — faqat paketni o'qiydi
va hisobot chiqaradi (И0 = faqat kuzatish/hisobot, xabar yubormaydi).
"""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import konfig, paket, fayl  # noqa: E402
from inplus.agent import Agent, ishga_tushir  # noqa: E402

TOP_JAVOBSIZ = 15


# --------------------------------------------------------------------- #
# Hisoblovchi yordamchilar (sof funksiya — paketdan kelgan ro'yxatlarni
# oladi, hech qanday tashqi/hardcode qiymat ishlatmaydi).
# --------------------------------------------------------------------- #

def _dt(iso_matn):
    """ISO vaqt matnini datetime'ga o'giradi. Bo'lmasa/xato bo'lsa None."""
    if not iso_matn:
        return None
    try:
        return datetime.fromisoformat(iso_matn)
    except (TypeError, ValueError):
        return None


def _kun_sana(iso_yoki_sana):
    """ISO vaqt matnidan (yoki "YYYY-MM-DD" dan) faqat sanani oladi."""
    if not iso_yoki_sana:
        return None
    try:
        return date.fromisoformat(str(iso_yoki_sana)[:10])
    except ValueError:
        return None


def _tegilmagan(lid: dict) -> bool:
    """bosqich=yangi VA hech qanday aloqa bo'lmagan (oxirgi_aloqa yo'q
    YOKI yaratilgan payt bilan bir xil — hech kim tegmagan)."""
    if lid.get("bosqich") != "yangi":
        return False
    oxirgi = lid.get("oxirgi_aloqa")
    yaratildi = lid.get("yaratildi")
    return oxirgi is None or oxirgi == yaratildi


def _ishlangan(lid: dict) -> bool:
    """oxirgi_aloqa > yaratildi — kamida bitta aloqa (real reaksiya) bo'lgan."""
    yaratildi_dt = _dt(lid.get("yaratildi"))
    oxirgi_dt = _dt(lid.get("oxirgi_aloqa"))
    if yaratildi_dt is None or oxirgi_dt is None:
        return False
    return oxirgi_dt > yaratildi_dt


def _reaksiya_soat(lid: dict):
    """(oxirgi_aloqa - yaratildi) soatda. Faqat _ishlangan() uchun chaqiring."""
    yaratildi_dt = _dt(lid.get("yaratildi"))
    oxirgi_dt = _dt(lid.get("oxirgi_aloqa"))
    if yaratildi_dt is None or oxirgi_dt is None:
        return None
    return (oxirgi_dt - yaratildi_dt).total_seconds() / 3600


def _menejerlar_nazorat(lidlar, xodimlar):
    """lidlar[] menejer_id bo'yicha: lid/ishlangan/javobsiz/reaksiya_soat,
    ism+rol xodimlar[] dan (xodim_id == menejer_id, D1 formati `X-<uid>`)."""
    xodim_xarita = {x.get("xodim_id"): x for x in xodimlar}
    hisob = {}
    for l in lidlar:
        mid = l.get("menejer_id")
        if not mid:
            continue
        if mid not in hisob:
            xodim = xodim_xarita.get(mid)
            hisob[mid] = {
                "id": mid,
                "ism": xodim.get("ism") if xodim else mid,
                "rol": xodim.get("rol") if xodim else "noma'lum",
                "lid": 0, "ishlangan": 0, "javobsiz": 0,
                "_reaksiya_yigindi": 0.0, "_reaksiya_soni": 0,
            }
        row = hisob[mid]
        row["lid"] += 1
        if _tegilmagan(l):
            row["javobsiz"] += 1
        if _ishlangan(l):
            row["ishlangan"] += 1
            soat = _reaksiya_soat(l)
            if soat is not None:
                row["_reaksiya_yigindi"] += soat
                row["_reaksiya_soni"] += 1

    natija = []
    for row in hisob.values():
        soni = row.pop("_reaksiya_soni")
        yigindi = row.pop("_reaksiya_yigindi")
        row["reaksiya_soat"] = round(yigindi / soni, 1) if soni else None
        natija.append(row)
    natija.sort(key=lambda r: (r["javobsiz"], r["lid"]), reverse=True)
    return natija


def _javobsiz_royxat(lidlar, xodimlar, paket_sana):
    """Barcha javobsiz (bosqich=yangi, tegilmagan) lidlar — eng ko'p kun
    tegmagandan boshlab (kamayish tartibida), top TOP_JAVOBSIZ."""
    xodim_xarita = {x.get("xodim_id"): x for x in xodimlar}
    bugun = _kun_sana(paket_sana)
    royxat = []
    for l in lidlar:
        if not _tegilmagan(l):
            continue
        yaratildi_kun = _kun_sana(l.get("yaratildi"))
        kun_javobsiz = (bugun - yaratildi_kun).days if (bugun and yaratildi_kun) else None
        mid = l.get("menejer_id")
        xodim = xodim_xarita.get(mid)
        royxat.append({
            "lid_id": l.get("lid_id"),
            "ism": l.get("ism"),
            "menejer_id": mid,
            "menejer_ism": xodim.get("ism") if xodim else mid,
            "kanal": l.get("manba_kanal"),
            "kun_javobsiz": kun_javobsiz,
        })
    royxat.sort(key=lambda r: (r["kun_javobsiz"] is None, r["kun_javobsiz"] or 0), reverse=True)
    return royxat[:TOP_JAVOBSIZ]


class S4(Agent):
    agent_id = "S4"
    nom = "Menejer nazorati"

    def ish(self) -> dict:
        p = paket.oqi(self.agent_id)
        lidlar = p.get("lidlar", [])
        xodimlar = p.get("xodimlar", [])
        paket_sana = p.get("paket_id") or self.sana

        menejerlar = _menejerlar_nazorat(lidlar, xodimlar)
        javobsiz_lidlar = _javobsiz_royxat(lidlar, xodimlar, paket_sana)

        javobsiz_jami = sum(m["javobsiz"] for m in menejerlar)
        reaksiya_soatlar = [m["reaksiya_soat"] for m in menejerlar if m["reaksiya_soat"] is not None]
        ortacha_reaksiya_soat = round(sum(reaksiya_soatlar) / len(reaksiya_soatlar), 1) \
            if reaksiya_soatlar else 0

        obj = {
            "versiya": "1.0",
            "sana": paket_sana,
            "menejerlar": menejerlar,
            "javobsiz_lidlar": javobsiz_lidlar,
            "jami": {"javobsiz_jami": javobsiz_jami,
                     "ortacha_reaksiya_soat": ortacha_reaksiya_soat},
            "paket_id": p.get("paket_id"),
            "paket_hash": p.get("hash"),
        }

        fayl.json_yoz(konfig.data("nazorat.json"), obj)

        return {
            "kirdi": {"lidlar": len(lidlar), "xodimlar": len(xodimlar)},
            "chiqdi": {"menejerlar": len(menejerlar), "javobsiz_lidlar": len(javobsiz_lidlar)},
            "kpi": {"menejerlar": len(menejerlar), "javobsiz_jami": javobsiz_jami,
                    "ortacha_reaksiya_soat": ortacha_reaksiya_soat,
                    "javobsiz_lidlar_royxatda": len(javobsiz_lidlar)},
        }


if __name__ == "__main__":
    sys.exit(ishga_tushir(S4))
