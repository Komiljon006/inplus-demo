#!/usr/bin/env python3
"""D6 — Kurslar jadvalini o'qish (И0, timer 05:50).

Kirish : adapter.ol("sheets").varaq(SHEETS_ID, "Jadval") -> 2D ro'yxat
         (mock: mock/sheets/jadval.csv; real: Google Sheets API v4).
Ish    : sarlavhani tekshiradi -> har qatorni parslaydi -> validatsiya
         (sana haqiqiyligi, tugash>boshlanish, kurs_id/guruh_id regex,
         sigim>=band, xona+vaqt+kunlar to'qnashuvi, ustoz bir vaqtda 2 guruhda,
         narx>0, dublikat guruh_id) -> courses.json (§2.2).
Chiqish: data/courses.json (xato bo'lmasa) + data/courses/<sana>.json (yoki
         <sana>.xato.json), uzatish(berdi, courses, *), KPI, xato>0 bo'lsa
         shlyuz.yubor(S-902, direktor).

Qoida: bevosita `requests` yo'q (adapter orqali), boshqa agent bilan faylda
gaplashadi, xabar faqat shlyuz orqali.
"""
import re
import sys
import time
import hashlib
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import konfig, adapter, courses, shlyuz_client  # noqa: E402
from inplus.agent import Agent, ishga_tushir  # noqa: E402

KUTILGAN_USTUNLAR = [
    "kurs_id", "nom", "format", "narx", "davomiylik_oy", "ustoz_id", "guruh_id",
    "boshlanish", "tugash", "kunlar", "vaqt", "xona", "sigim",
]
KURS_ID_RE = re.compile(r"^K-[A-Z]{2,5}-\d{2}$")
GURUH_ID_RE = re.compile(r"^G-[A-Z]{2,5}-\d{2}-[A-Z]{3}$")
FORMAT_ENUM = {"offline", "online", "gibrid"}


def _sana_iso(matn: str):
    """dd.mm.yyyy -> YYYY-MM-DD. Mavjud bo'lmagan sana (masalan 31.09) -> None."""
    matn = (matn or "").strip()
    try:
        dt = datetime.strptime(matn, "%d.%m.%Y")
    except ValueError:
        return None
    return dt.strftime("%Y-%m-%d")


def _int_yoki_none(matn):
    try:
        return int(str(matn).strip())
    except (TypeError, ValueError):
        return None


def _band(guruh_id: str, sigim: int) -> int:
    """Sigimdan oshmaydigan deterministik 'band' soni (mock uchun; sheetda yo'q)."""
    if not sigim or sigim <= 0:
        return 0
    h = int(hashlib.sha256(guruh_id.encode("utf-8")).hexdigest(), 16)
    return h % (sigim + 1)


def _qator_parse(nomer: int, qator: list) -> dict:
    """Bitta CSV qatorini dict + shu qatorning xatolar/ogohlantirish ro'yxatiga aylantiradi."""
    d = dict(zip(KUTILGAN_USTUNLAR, qator + [""] * (len(KUTILGAN_USTUNLAR) - len(qator))))
    muammolar = []

    kurs_id = (d.get("kurs_id") or "").strip()
    if not KURS_ID_RE.match(kurs_id):
        muammolar.append((nomer, "kurs_id", kurs_id, "kurs_id formati noto'g'ri (K-XXX-00)", "xato"))

    guruh_id = (d.get("guruh_id") or "").strip()
    if not GURUH_ID_RE.match(guruh_id):
        muammolar.append((nomer, "guruh_id", guruh_id, "guruh_id formati noto'g'ri (G-XXX-00-AAA)", "xato"))

    narx = _int_yoki_none(d.get("narx"))
    if narx is None or narx <= 0:
        muammolar.append((nomer, "narx", d.get("narx"), "narx > 0 bo'lishi shart", "xato"))

    sigim = _int_yoki_none(d.get("sigim"))
    if sigim is None or sigim < 0:
        muammolar.append((nomer, "sigim", d.get("sigim"), "sigim butun son bo'lishi shart", "xato"))

    boshlanish = _sana_iso(d.get("boshlanish"))
    if boshlanish is None:
        muammolar.append((nomer, "boshlanish", d.get("boshlanish"), "sana mavjud emas", "xato"))

    tugash = _sana_iso(d.get("tugash"))
    if tugash is None:
        muammolar.append((nomer, "tugash", d.get("tugash"), "sana mavjud emas", "xato"))

    if boshlanish and tugash and tugash <= boshlanish:
        muammolar.append((nomer, "tugash", d.get("tugash"), "tugash boshlanishdan keyin bo'lishi shart", "xato"))

    fmt = (d.get("format") or "").strip()
    if fmt not in FORMAT_ENUM:
        muammolar.append((nomer, "format", fmt, f"format {sorted(FORMAT_ENUM)} dan biri bo'lishi shart", "xato"))

    davomiylik_oy = _int_yoki_none(d.get("davomiylik_oy"))
    kunlar = [k.strip() for k in (d.get("kunlar") or "").split(",") if k.strip()]
    ustoz_id = (d.get("ustoz_id") or "").strip() or None
    vaqt = (d.get("vaqt") or "").strip()
    xona = (d.get("xona") or "").strip()

    band = _band(guruh_id, sigim or 0)
    if sigim is not None and band > sigim:
        muammolar.append((nomer, "sigim", sigim, f"sigim ({sigim}) < band ({band})", "xato"))

    rekord = {
        "qator": nomer, "kurs_id": kurs_id, "nom": (d.get("nom") or "").strip(),
        "format": fmt, "narx": narx, "davomiylik_oy": davomiylik_oy, "ustoz_id": ustoz_id,
        "guruh_id": guruh_id, "boshlanish": boshlanish, "tugash": tugash,
        "kunlar": kunlar, "kunlar_set": frozenset(kunlar), "vaqt": vaqt, "xona": xona,
        "sigim": sigim, "band": band,
    }
    return rekord, muammolar


def _toqnashuv_tekshir(qatorlar: list) -> list:
    """Bir xil kun+vaqt slotida bir xil xona yoki bir xil ustoz -> ogohlantirish.
    Ikkinchi (keyingi) qatorga yoziladi, birinchisi 'toza' qoladi."""
    natija = []
    for i in range(len(qatorlar)):
        for j in range(i + 1, len(qatorlar)):
            a, b = qatorlar[i], qatorlar[j]
            if not a["vaqt"] or a["vaqt"] != b["vaqt"]:
                continue
            if not a["kunlar_set"] or a["kunlar_set"] != b["kunlar_set"]:
                continue
            sabablar = []
            if a["xona"] and a["xona"] == b["xona"]:
                sabablar.append(f"xona {a['xona']}")
            if a["ustoz_id"] and a["ustoz_id"] == b["ustoz_id"]:
                sabablar.append(f"ustoz {a['ustoz_id']}")
            if sabablar:
                natija.append((
                    b["qator"], "xona" if "xona" in sabablar[0] else "ustoz_id", b["xona"],
                    f"{b['guruh_id']}: {a['guruh_id']} bilan bir vaqtda {', '.join(sabablar)} to'qnashuvi",
                    "ogohlantirish",
                ))
    return natija


def _dublikat_guruh_tekshir(qatorlar: list) -> list:
    korilgan = {}
    natija = []
    for r in qatorlar:
        gid = r["guruh_id"]
        if gid in korilgan:
            natija.append((r["qator"], "guruh_id", gid, f"dublikat guruh_id ({gid})", "xato"))
        else:
            korilgan[gid] = r["qator"]
    return natija


def _xatolar_dict(muammolar: list) -> list:
    return [{"qator": q, "maydon": m, "qiymat": (None if v is None else str(v)),
             "xabar": x, "daraja": d} for (q, m, v, x, d) in muammolar]


class D6(Agent):
    agent_id = "D6"
    nom = "Kurslar jadvali"

    def ish(self) -> dict:
        t0 = time.monotonic()
        sheets = adapter.ol("sheets")
        varaq = sheets.varaq(konfig.env("SHEETS_ID"), "Jadval")
        if not varaq:
            raise RuntimeError("D6: sheets.varaq bo'sh qaytdi")

        sarlavha = [c.strip() for c in varaq[0]]
        satrlar = varaq[1:]
        qator_soni = len(satrlar)

        barcha_muammolar = []
        toza_qatorlar = []

        if sarlavha != KUTILGAN_USTUNLAR:
            barcha_muammolar.append((
                1, "sarlavha", ",".join(sarlavha),
                f"kutilgan ustunlarga mos kelmadi ({','.join(KUTILGAN_USTUNLAR)})", "xato",
            ))
        else:
            for i, qator in enumerate(satrlar):
                nomer = i + 2  # 1-qator sarlavha
                rekord, muammolar = _qator_parse(nomer, qator)
                barcha_muammolar.extend(muammolar)
                if not any(d == "xato" for (_, _, _, _, d) in muammolar):
                    toza_qatorlar.append(rekord)
            barcha_muammolar.extend(_dublikat_guruh_tekshir(toza_qatorlar))
            barcha_muammolar.extend(_toqnashuv_tekshir(toza_qatorlar))
            # dublikat sifatida topilganlarni chiqindiga chiqarib tashlaymiz
            dublikat_qatorlar = {q for (q, maydon, _qiymat, xabar, daraja) in barcha_muammolar
                                  if daraja == "xato" and maydon == "guruh_id" and "dublikat" in xabar}
            if dublikat_qatorlar:
                toza_qatorlar = [r for r in toza_qatorlar if r["qator"] not in dublikat_qatorlar]

        # kurs_id bo'yicha guruhlash (birinchi ko'ringan tartibda)
        kurslar_tartib = []
        kurslar_map = {}
        for r in toza_qatorlar:
            kid = r["kurs_id"]
            if kid not in kurslar_map:
                kurslar_map[kid] = {
                    "kurs_id": kid, "nom": r["nom"], "format": r["format"],
                    "narx": r["narx"], "valyuta": "UZS", "davomiylik_oy": r["davomiylik_oy"],
                    "ustoz_id": r["ustoz_id"], "faol": True, "guruhlar": [],
                }
                kurslar_tartib.append(kid)
            holat = self._guruh_holati(r["boshlanish"], r["tugash"])
            kurslar_map[kid]["guruhlar"].append({
                "guruh_id": r["guruh_id"], "boshlanish": r["boshlanish"], "tugash": r["tugash"],
                "kunlar": r["kunlar"], "vaqt": r["vaqt"], "xona": r["xona"],
                "sigim": r["sigim"], "band": r["band"], "holat": holat,
            })
        kurslar = [kurslar_map[k] for k in kurslar_tartib]

        xato_soni = sum(1 for m in barcha_muammolar if m[4] == "xato")
        ogoh_soni = sum(1 for m in barcha_muammolar if m[4] == "ogohlantirish")
        holat = "xato" if xato_soni else ("ogohlantirish" if ogoh_soni else "ok")

        obj = {
            "versiya": "1.0",
            "yaratildi": konfig.iso(),
            "manba": {"tur": "sheets", "id": konfig.env("SHEETS_ID") or None,
                      "varaq": "Jadval", "qator": qator_soni},
            "validatsiya": {"holat": holat, "xatolar": _xatolar_dict(barcha_muammolar)},
            "kurslar": kurslar,
        }

        natija = courses.yoz(obj, kim=self.agent_id, sana=self.sana)

        kpi = {
            "qator": qator_soni, "kurs": len(kurslar),
            "guruh": sum(len(k["guruhlar"]) for k in kurslar),
            "xato": xato_soni, "ogohlantirish": ogoh_soni,
        }

        if xato_soni:
            self._s902_yubor(xato_soni, [m for m in barcha_muammolar if m[4] == "xato"])

        return {
            "kirdi": {"sheets": qator_soni},
            "chiqdi": {"kurs": len(kurslar), "guruh": kpi["guruh"], "courses": 1 if natija["yangilandi"] else 0},
            "kpi": kpi,
        }

    def _guruh_holati(self, boshlanish, tugash):
        sana = self.sana
        if boshlanish and sana < boshlanish:
            return "yangi"
        if tugash and sana > tugash:
            return "tugadi"
        return "davom"

    def _s902_yubor(self, soni, xato_royxati):
        royxat = "; ".join(f"qator {q}: {x}" for (q, _, _, x, _) in xato_royxati[:5])
        tg_admin = konfig.env("TG_ADMIN_ID")
        telegram_id = int(tg_admin) if tg_admin.strip().isdigit() else None
        shlyuz_client.yubor(
            kimdan_agent=self.agent_id, kanal="tg",
            kimga={"tur": "xodim", "id": "direktor", "telegram_id": telegram_id, "telefon": None},
            skript_id="S-902", til="uz",
            ozgaruvchilar={"soni": str(soni), "royxat": royxat},
            idempotent_kalit=f"D6:S-902:{self.sana}:{soni}",
        )


if __name__ == "__main__":
    sys.exit(ishga_tushir(D6))
