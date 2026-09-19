#!/usr/bin/env python3
"""X3 — Analitika hisoboti (2-blok, «Sotuv va CRM», analitik, И0).

Kirish : paket.oqi() — joriy paket (D1 chiqishi): `lidlar`, `talabalar`,
         `tolovlar`, `xodimlar` bo'limlari. BOSHQA HECH NARSA o'qilmaydi —
         mijozga ko'rsatiladigan hamma raqam shu bitta paketdan hisoblanadi
         (soxta/hardcode qiymat yo'q).
Ish    : quyidagilarni HAQIQIY paket ma'lumotidan hisoblaydi:
  - kunlik_tushum : `tolovlar[].summa` sana bo'yicha yig'indi.
  - kurs_daromadi : `talabalar[].tolov.jami` kurs_id bo'yicha yig'indi.
  - menejerlar    : `lidlar[]` menejer_id bo'yicha (lid/sotildi/konv),
                    ism+rol `xodimlar[]` dan.
  - orqada        : holat=faol va (davomat<60 YOKI progress<25).
  - nps           : `talabalar[].xom.nps` dan promoter/passiv/kritik+ball.
  - prognoz       : kunlik_tushum trendidan chiziqli regressiya (eng kichik
                    kvadratlar, sof Python — tashqi kutubxona yo'q) bilan
                    keyingi 4 haftaga proyeksiya.
  - vozvrat       : holat=tashladi va tolov.tolandi>0 bo'lganlar.
Chiqish: data/tahlil.json, KPI.

Bu agent HECH NARSA YOZMAYDI/yubormaydi tashqariga — faqat paketni o'qiydi
va hisobot chiqaradi (И0 = faqat kuzatish/hisobot, xabar yubormaydi).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import konfig, paket, fayl  # noqa: E402
from inplus.agent import Agent, ishga_tushir  # noqa: E402


# --------------------------------------------------------------------- #
# Hisoblovchi yordamchilar (hammasi sof funksiya — paketdan kelgan
# ro'yxatlarni oladi, hech qanday tashqi/hardcode qiymat ishlatmaydi).
# --------------------------------------------------------------------- #

def _int_yoki_none(v):
    if v is None:
        return None
    try:
        s = str(v).strip()
        return int(s) if s != "" else None
    except (TypeError, ValueError):
        return None


def _kunlik_tushum(tolovlar):
    """tolovlar[].summa ni sana bo'yicha yig'adi (tartiblangan ro'yxat)."""
    hisob = {}
    for t in tolovlar:
        sana = t.get("sana")
        if not sana:
            continue
        hisob[sana] = hisob.get(sana, 0) + (t.get("summa") or 0)
    return [{"sana": sana, "summa": hisob[sana]} for sana in sorted(hisob)]


def _kurs_daromadi(talabalar):
    """talabalar[].tolov.jami kurs_id bo'yicha yig'indi, kamayish tartibida.

    Kurs nomi paketning o'zidagi `xom.guruh_nom` dan olinadi (D1 getcourse
    xom qatorini o'zgarishsiz saqlaydi) — courses.json alohida O'QILMAYDI,
    X3 faqat `paket` ga bog'liq (konfig/agentlar.json: oqiydi=["paket"])."""
    hisob = {}
    for t in talabalar:
        kurs_id = t.get("kurs_id")
        if not kurs_id:
            continue
        jami = (t.get("tolov") or {}).get("jami") or 0
        nom = (t.get("xom") or {}).get("guruh_nom") or kurs_id
        if kurs_id not in hisob:
            hisob[kurs_id] = {"kurs_id": kurs_id, "nom": nom, "summa": 0, "talaba": 0}
        hisob[kurs_id]["summa"] += jami
        hisob[kurs_id]["talaba"] += 1
    natija = list(hisob.values())
    natija.sort(key=lambda r: r["summa"], reverse=True)
    return natija


def _menejerlar(lidlar, xodimlar):
    """lidlar[] menejer_id bo'yicha: lid/sotildi/summa/konv, ism+rol
    xodimlar[] dan (xodim_id == menejer_id, D1 formati `X-<uid>`)."""
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
                "lid": 0, "sotildi": 0, "summa": 0,
            }
        row = hisob[mid]
        row["lid"] += 1
        if l.get("bosqich") == "sotildi":
            row["sotildi"] += 1
        row["summa"] += l.get("summa") or 0
    natija = []
    for row in hisob.values():
        row["konv"] = round(row["sotildi"] / row["lid"], 3) if row["lid"] else 0.0
        natija.append(row)
    natija.sort(key=lambda r: r["lid"], reverse=True)
    return natija


def _orqada(talabalar):
    """holat=faol va (davomat<60 YOKI progress<25) — sabab qaysi biri past."""
    natija = []
    for t in talabalar:
        if t.get("holat") != "faol":
            continue
        davomat = t.get("davomat_foiz")
        progress = t.get("progress_foiz")
        past_davomat = davomat is not None and davomat < 60
        past_progress = progress is not None and progress < 25
        if not (past_davomat or past_progress):
            continue
        sabablar = []
        if past_davomat:
            sabablar.append("davomat past")
        if past_progress:
            sabablar.append("progress past")
        natija.append({
            "talaba_id": t.get("talaba_id"),
            "ism": t.get("ism"),
            "kurs_id": t.get("kurs_id"),
            "davomat": davomat,
            "progress": progress,
            "sabab": " va ".join(sabablar),
        })
    return natija


def _nps(talabalar):
    """talabalar[].xom.nps (getcourse xom qatoridagi xom string maydon) dan:
    9-10 promoter, 7-8 passiv, 0-6 kritik. Javob bermaganlar (bo'sh/yo'q)
    hisobga kirmaydi. ball = (promoter-kritik)/javob*100, yaxlitlangan."""
    promoter = passiv = kritik = 0
    for t in talabalar:
        xom = t.get("xom") or {}
        ball = _int_yoki_none(xom.get("nps"))
        if ball is None:
            continue
        if ball >= 9:
            promoter += 1
        elif ball >= 7:
            passiv += 1
        else:
            kritik += 1
    javob = promoter + passiv + kritik
    ball_umumiy = round((promoter - kritik) / javob * 100) if javob else 0
    return {"ball": ball_umumiy, "promoter": promoter, "passiv": passiv,
            "kritik": kritik, "javob": javob}


def _chiziqli_regressiya(ys):
    """Eng kichik kvadratlar usuli (sof Python, tashqi kutubxonasiz).
    x = 0..n-1. Qaytaradi: (b0, b1) -> y = b0 + b1*x."""
    n = len(ys)
    if n == 0:
        return 0.0, 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    maxray = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    maxrax = sum((x - mean_x) ** 2 for x in xs)
    b1 = maxray / maxrax if maxrax else 0.0
    b0 = mean_y - b1 * mean_x
    return b0, b1


def _prognoz(kunlik_tushum):
    """kunlik_tushum (bor kunlar bo'yicha) dan TO'LIQ kalendar qatorini
    (bo'sh kunlar = 0) tiklab, chiziqli trend bilan keyingi 4 haftaga
    (har biri 7 kun) proyeksiya qiladi. Real hisob — hardcode yo'q."""
    if not kunlik_tushum:
        return [{"hafta": f"{i}-hafta", "summa": 0} for i in range(1, 5)]

    from datetime import date as _date, timedelta as _timedelta
    sanalar = [_date.fromisoformat(r["sana"]) for r in kunlik_tushum]
    boshi, oxiri = min(sanalar), max(sanalar)
    xarita = {r["sana"]: r["summa"] for r in kunlik_tushum}
    kun_soni = (oxiri - boshi).days + 1
    ys = []
    kun = boshi
    for _ in range(kun_soni):
        ys.append(xarita.get(kun.isoformat(), 0))
        kun += _timedelta(days=1)

    b0, b1 = _chiziqli_regressiya(ys)
    n = len(ys)
    prognoz = []
    for hafta in range(4):
        boshlanish_x = n + hafta * 7
        haftalik = sum(max(0.0, b0 + b1 * (boshlanish_x + kun_ofset))
                       for kun_ofset in range(7))
        prognoz.append({"hafta": f"{hafta + 1}-hafta", "summa": round(haftalik)})
    return prognoz


def _vozvrat(talabalar):
    """holat=tashladi va tolov.tolandi>0 bo'lgan talabalar (real vozvrat manbai)."""
    royxat = [t for t in talabalar
              if t.get("holat") == "tashladi" and (t.get("tolov") or {}).get("tolandi", 0) > 0]
    summa = sum(t.get("tolov", {}).get("tolandi", 0) for t in royxat)
    return {"soni": len(royxat), "summa": summa}


class X3(Agent):
    agent_id = "X3"
    nom = "Analitika hisoboti"

    def ish(self) -> dict:
        p = paket.oqi(self.agent_id)
        lidlar = p.get("lidlar", [])
        talabalar = p.get("talabalar", [])
        tolovlar = p.get("tolovlar", [])
        xodimlar = p.get("xodimlar", [])

        kunlik_tushum = _kunlik_tushum(tolovlar)
        kurs_daromadi = _kurs_daromadi(talabalar)
        menejerlar = _menejerlar(lidlar, xodimlar)
        orqada = _orqada(talabalar)
        nps = _nps(talabalar)
        prognoz = _prognoz(kunlik_tushum)
        vozvrat = _vozvrat(talabalar)

        obj = {
            "versiya": "1.0",
            "sana": p.get("paket_id") or self.sana,
            "kunlik_tushum": kunlik_tushum,
            "kurs_daromadi": kurs_daromadi,
            "menejerlar": menejerlar,
            "orqada": orqada,
            "nps": nps,
            "prognoz": prognoz,
            "vozvrat": vozvrat,
            "paket_id": p.get("paket_id"),
            "paket_hash": p.get("hash"),
        }

        fayl.json_yoz(konfig.data("tahlil.json"), obj)

        jami_tushum = sum(r["summa"] for r in kunlik_tushum)
        return {
            "kirdi": {"lidlar": len(lidlar), "talabalar": len(talabalar),
                      "tolovlar": len(tolovlar)},
            "chiqdi": {"tahlil": 1, "kunlar": len(kunlik_tushum),
                       "kurslar": len(kurs_daromadi), "menejerlar": len(menejerlar),
                       "orqada": len(orqada)},
            "kpi": {"jami_tushum": jami_tushum, "kunlar": len(kunlik_tushum),
                    "kurslar": len(kurs_daromadi), "menejerlar": len(menejerlar),
                    "orqada_soni": len(orqada), "nps_ball": nps["ball"],
                    "vozvrat_soni": vozvrat["soni"], "vozvrat_summa": vozvrat["summa"]},
        }


if __name__ == "__main__":
    sys.exit(ishga_tushir(X3))
