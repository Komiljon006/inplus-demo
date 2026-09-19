#!/usr/bin/env python3
"""S6 — Qarzdorlar eslatmasi (2-blok, «Sotuv va CRM», ijrochi, И1).

Kirish : paket.oqi() — joriy paket (D1 chiqishi), `talabalar` bo'limi.
Ish    : `tolov.qarz > 0` bo'lgan talabalarni topadi, `tolov.keyingi_sana`
         bo'yicha (eng yaqini oldin) tartiblaydi, har biriga shlyuz orqali
         `S-001` (tolov_eslatma_3kun — kimga_turi=talaba, o'zgaruvchilar
         ism/kurs/summa/sana bilan aynan mos) skripti bilan eslatma yuboradi.
         Limit/dublikat/oq-qora ro'yxat/vaqt oynasi — hammasi SHLYUZDA hal
         bo'ladi, S6 faqat so'rov yuboradi va javob holatini yozadi.
Chiqish: data/qarz/<sana>.json (tarix) + data/qarz.json (joriy), KPI.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import konfig, paket, fayl, shlyuz_client  # noqa: E402
from inplus.agent import Agent, ishga_tushir  # noqa: E402

SKRIPT_ID = "S-001"
KANAL = "sms"


def _summa_matn(son: int) -> str:
    return f"{int(son):,}".replace(",", " ")


def _qarzdorlar_topish(talabalar):
    qarzdorlar = [t for t in talabalar if (t.get("tolov") or {}).get("qarz", 0) > 0]
    # keyingi_sana bo'yicha o'sish tartibida, sana yo'qlar oxirida
    qarzdorlar.sort(key=lambda t: (t.get("tolov", {}).get("keyingi_sana") is None,
                                    t.get("tolov", {}).get("keyingi_sana") or ""))
    return qarzdorlar


class S6(Agent):
    agent_id = "S6"
    nom = "Qarzdorlar eslatmasi"

    def ish(self) -> dict:
        p = paket.oqi(self.agent_id)
        talabalar = p.get("talabalar", [])
        qarzdorlar = _qarzdorlar_topish(talabalar)

        royxat = []
        holat_hisob = {}
        for t in qarzdorlar:
            xabar_holati = self._eslatma_yubor(t)
            holat_hisob[xabar_holati] = holat_hisob.get(xabar_holati, 0) + 1
            royxat.append({
                "talaba_id": t.get("talaba_id"),
                "ism": t.get("ism"),
                "qarz": t.get("tolov", {}).get("qarz", 0),
                "keyingi_sana": t.get("tolov", {}).get("keyingi_sana"),
                "xabar_holati": xabar_holati,
            })

        qarz_jami = sum(r["qarz"] for r in royxat)
        obj = {
            "versiya": "1.0",
            "sana": self.sana,
            "qarzdorlar_soni": len(royxat),
            "qarz_jami": qarz_jami,
            "royxat": royxat,
            "paket_id": p.get("paket_id"),
            "paket_hash": p.get("hash"),
        }

        fayl.json_yoz(konfig.data("qarz", f"{self.sana}.json"), obj)
        fayl.json_yoz(konfig.data("qarz.json"), obj)

        return {
            "kirdi": {"talabalar": len(talabalar)},
            "chiqdi": {"qarzdorlar": len(royxat), "xabar_yuborishga_urindi": len(royxat)},
            "kpi": {"qarzdorlar_soni": len(royxat), "qarz_jami": qarz_jami,
                    **{f"xabar_{k}": v for k, v in holat_hisob.items()}},
        }

    def _eslatma_yubor(self, talaba: dict) -> str:
        talaba_id = talaba.get("talaba_id")
        tolov = talaba.get("tolov") or {}
        kurs = talaba.get("kurs_id") or "kurs"
        sana = tolov.get("keyingi_sana") or "yaqin orada"
        javob = shlyuz_client.yubor(
            kimdan_agent=self.agent_id, kanal=KANAL,
            kimga={"tur": "talaba", "id": talaba_id,
                   "telegram_id": talaba.get("telegram_id"),
                   "telefon": talaba.get("telefon")},
            skript_id=SKRIPT_ID, til="uz",
            ozgaruvchilar={"ism": talaba.get("ism") or "", "kurs": kurs,
                           "summa": _summa_matn(tolov.get("qarz", 0)), "sana": sana},
            idempotent_kalit=f"{self.agent_id}:{SKRIPT_ID}:{talaba_id}:{sana}",
        )
        return javob.get("holat", "xato")


if __name__ == "__main__":
    sys.exit(ishga_tushir(S6))
