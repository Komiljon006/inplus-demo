#!/usr/bin/env python3
"""S2 — Sotuv voronkasi hisoboti (2-blok, «Sotuv va CRM», analitik, И0).

Kirish : paket.oqi() — joriy paket (D1 chiqishi), faqat `lidlar` bo'limi.
Ish    : `lidlar` ni `bosqich` bo'yicha sanaydi (voronka taqsimoti), har
         bosqich uchun summa yig'indisi, umumiy summa/o'rtacha chek va
         `manba_kanal` kesimi hisoblanadi.
Chiqish: data/voronka/<sana>.json (tarix) + data/voronka.json (joriy, D1
         courses.py naqshiga o'xshab ikkalasiga ham to'liq obyekt yoziladi),
         KPI. Ixtiyoriy: wiki/voronka_<sana>.md (W1 index'ga olishi mumkin).

Bu agent HECH NARSA YOZMAYDI/yubormaydi tashqariga — faqat paketni o'qiydi
va hisobot chiqaradi (И0 = faqat kuzatish/hisobot, xabar yubormaydi).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import konfig, paket, fayl  # noqa: E402
from inplus.agent import Agent, ishga_tushir  # noqa: E402

# Voronka tartibi: chapdan o'ngga sotuv bosqichi, so'ng yon-natijalar
# (qayta faollashtirish, yo'qotildi). paket.schema.json `lid.bosqich` enum'i
# bilan AYNAN mos (kontrakt MUZLATILGAN, shu yerda faqat o'qiladi).
BOSQICH_TARTIB = [
    ("yangi", "Yangi"),
    ("aloqa", "Aloqa"),
    ("konsultatsiya", "Konsultatsiya"),
    ("sinov_dars", "Sinov dars"),
    ("tolov_kutish", "To'lov kutilmoqda"),
    ("sotildi", "Sotildi"),
    ("qayta", "Qayta faollashtirish"),
    ("yoqotildi", "Yo'qotildi"),
]


def _bosqichlar_hisobla(lidlar):
    soni = {kod: 0 for kod, _ in BOSQICH_TARTIB}
    summa = {kod: 0 for kod, _ in BOSQICH_TARTIB}
    for lid in lidlar:
        kod = lid.get("bosqich") or "noma'lum"
        if kod not in soni:
            soni[kod] = 0
            summa[kod] = 0
        soni[kod] += 1
        summa[kod] += lid.get("summa") or 0

    nomlar = dict(BOSQICH_TARTIB)
    bosqichlar = [
        {"kod": kod, "nom": nomlar.get(kod, kod), "soni": soni[kod], "summa": summa[kod]}
        for kod, _ in BOSQICH_TARTIB
    ]
    # kontraktda yo'q, lekin ma'lumotda uchragan bosqich kodlari bo'lsa oxiriga qo'shamiz
    for kod in soni:
        if kod not in nomlar:
            bosqichlar.append({"kod": kod, "nom": kod, "soni": soni[kod], "summa": summa[kod]})
    return bosqichlar


def _kanallar_hisobla(lidlar):
    hisob = {}
    for lid in lidlar:
        nom = lid.get("manba_kanal") or "noma'lum"
        hisob[nom] = hisob.get(nom, 0) + 1
    kanallar = [{"nom": nom, "soni": soni} for nom, soni in hisob.items()]
    kanallar.sort(key=lambda k: k["soni"], reverse=True)
    return kanallar


def _wiki_yoz(sana, obj):
    """Ixtiyoriy: wiki/voronka_<sana>.md. Xato bo'lsa agent yiqilmaydi."""
    try:
        satrlar = [f"# Sotuv voronkasi — {sana}", "",
                   f"Jami lid: **{obj['jami_lid']}** · Jami summa: **{obj['jami_summa']:,}"
                   .replace(",", " ") + " so'm** · O'rtacha chek: "
                   f"**{obj['ortacha_chek']:,}".replace(",", " ") + " so'm**", "",
                   "| Bosqich | Soni | Summa |", "|---|---:|---:|"]
        for b in obj["bosqichlar"]:
            summa_str = f"{b['summa']:,}".replace(",", " ")
            satrlar.append(f"| {b['nom']} | {b['soni']} | {summa_str} |")
        satrlar += ["", "| Kanal | Soni |", "|---|---:|"]
        for k in obj["kanallar"]:
            satrlar.append(f"| {k['nom']} | {k['soni']} |")
        p = konfig.yol("wiki", f"voronka_{sana}.md")
        fayl.yoz(p, "\n".join(satrlar) + "\n")
    except Exception:
        pass


class S2(Agent):
    agent_id = "S2"
    nom = "Sotuv voronkasi hisoboti"

    def ish(self) -> dict:
        p = paket.oqi(self.agent_id)
        lidlar = p.get("lidlar", [])

        bosqichlar = _bosqichlar_hisobla(lidlar)
        kanallar = _kanallar_hisobla(lidlar)
        jami_lid = len(lidlar)
        jami_summa = sum(l.get("summa") or 0 for l in lidlar)
        ortacha_chek = round(jami_summa / jami_lid) if jami_lid else 0

        obj = {
            "versiya": "1.0",
            "sana": self.sana,
            "jami_lid": jami_lid,
            "bosqichlar": bosqichlar,
            "kanallar": kanallar,
            "jami_summa": jami_summa,
            "ortacha_chek": ortacha_chek,
            "paket_id": p.get("paket_id"),
            "paket_hash": p.get("hash"),
        }

        fayl.json_yoz(konfig.data("voronka", f"{self.sana}.json"), obj)
        fayl.json_yoz(konfig.data("voronka.json"), obj)
        _wiki_yoz(self.sana, obj)

        bosqich_faol = sum(1 for b in bosqichlar if b["soni"] > 0)
        return {
            "kirdi": {"lidlar": jami_lid},
            "chiqdi": {"voronka": 1, "bosqich_faol": bosqich_faol, "kanal": len(kanallar)},
            "kpi": {"jami_lid": jami_lid, "jami_summa": jami_summa,
                    "ortacha_chek": ortacha_chek, "sotildi": next(
                        (b["soni"] for b in bosqichlar if b["kod"] == "sotildi"), 0)},
        }


if __name__ == "__main__":
    sys.exit(ishga_tushir(S2))
