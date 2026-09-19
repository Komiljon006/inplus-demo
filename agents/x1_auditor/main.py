#!/usr/bin/env python3
"""X1 — Zanjirlar auditori (И0, timer 22:00 + `--sana` bilan istalgan kun).

"A berdi = B oldi" sverkasi: `data/uzatish/<sana>.jsonl` (§2.3),
`data/kpi/*/<sana>.json` (§2.4), `konfig/agentlar.json` (§2.6) va
`agents/**/*.py` kod daraxti (statik grep, shlyuzni chetlab o'tishni tutish).

Tekshiruvlar (har biri aniq `kod` bilan insident yozadi):
  UZ_KUTILDI, UZ_HASH, UZ_SONI, UZ_YETIM, KPI_YOQ, KPI_NISBAT, KPI_XATO,
  SHLYUZ_CHETLAB, HB_YOQ

Muhim moslashtirish: `lib/inplus/uzatish.oldi()` bitta `obyekt` uchun ENG
OXIRGI `berdi` yozuvining `uzatish_id`sini oladi — shu sababli X1 har bir
`berdi`/`oldi` juftini `obyekt` emas, aynan `uzatish_id` bo'yicha moslaydi
(bitta faylga bir necha marta yozilganda — masalan X0 sinov jurnali — har bir
yetkazish alohida hisoblansin uchun).

X0 ning to'g'ridan-to'g'ri (`kimga: "X1"`) yuborgan xabarlarini X1 o'zi
"oldi" qiladi (`_oldi_yoz`) — bu X0->X2/X1 kanareyka zanjirini yopadi.

Chiqish: `data/x1/<sana>.json`, `data/insident/<sana>.jsonl`,
`wiki/jurnal/zanjir_<sana>.md`, KPI `X1`.

Ishga tushirish:
  bin/inplus ishga X1
  python3 agents/x1_auditor/main.py --bir-marta --sana 2026-09-19
"""
import re
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import konfig, heartbeat, kpi as kpi_mod, uzatish, kontrakt, jurnal, fayl, shlyuz_client  # noqa: E402
from inplus.agent import Agent, ishga_tushir  # noqa: E402

AGENT_ID = "X1"

_HHMMSS = re.compile(r"(\d{2}):(\d{2}):(\d{2})$")
_SHLYUZ_NAQSH = re.compile(r"api\.telegram\.org|sendMessage|smtplib|requests\.post\(\s*[\"']https?://")


# --------------------------------------------------------------------------
# insident yordamchilari (kontrakt/lib o'zgartirilmaydi — mos yozuv shu yerda)
# --------------------------------------------------------------------------
def _keyingi_insident_id(sana):
    p = konfig.data("insident", f"{sana}.jsonl")
    n = len(jurnal.oqi(p))
    return f"i-{sana}-{n + 1:04d}"


def _insident_yoz(agent, kod, daraja, xabar, sana):
    satr = {
        "insident_id": _keyingi_insident_id(sana),
        "vaqt": konfig.iso(), "kim": AGENT_ID, "agent": agent, "kod": kod,
        "daraja": daraja, "xabar": xabar, "harakat": None, "natija": None, "yopildi": None,
    }
    kontrakt.tekshir("insident", satr)
    jurnal.append(konfig.data("insident", f"{sana}.jsonl"), satr)
    return satr


def _yozilganmi(sana, agent, kod, xabar):
    for i in jurnal.oqi(konfig.data("insident", f"{sana}.jsonl")):
        if i.get("agent") == agent and i.get("kod") == kod and i.get("xabar") == xabar:
            return True
    return False


def _oldi_yoz(sana, kimga, berdi_satr):
    """uzatish.oldi() dagi 'eng oxirgi berdi' noaniqligidan qochish uchun —
    aynan shu berdi yozuvining uzatish_id/hash/soni sini saqlab qoladi."""
    satr = {
        "uzatish_id": berdi_satr["uzatish_id"],
        "vaqt": konfig.iso(),
        "yonalish": "oldi",
        "kimdan": berdi_satr["kimdan"],
        "kimga": kimga,
        "tur": berdi_satr.get("tur", "fayl"),
        "obyekt": berdi_satr["obyekt"],
        "hash": berdi_satr["hash"],
        "soni": berdi_satr.get("soni") or {},
        "kutish_daq": None,
    }
    kontrakt.tekshir("uzatish", satr)
    jurnal.append(uzatish.yol(sana), satr)
    return satr


def _tur_dan_obyekt(obyekt):
    if obyekt.startswith("data/paket/") and not obyekt.endswith("joriy.json"):
        return "paket"
    if obyekt == "data/courses.json":
        return "courses"
    if obyekt.startswith("data/sinov/"):
        return "sinov"
    if obyekt.startswith("data/jurnal/xabar"):
        return "jurnal_xabar"
    if obyekt == "konfig/skriptlar.json":
        return "skriptlar"
    return None


def _bugun_kutilgan_allaqachon_otdimi(jadval):
    m = _HHMMSS.search(jadval or "")
    if not m:
        return False  # noma'lum format (masalan '*:0/5') — tekshiruv o'tkazib yuboriladi
    h, mi, s = (int(x) for x in m.groups())
    hozir = konfig.hozir()
    return (hozir.hour, hozir.minute, hozir.second) >= (h, mi, s)


def _ifoda_baho(ifoda, kirdi, chiqdi):
    """Faqat 'chiqdi.X == kirdi.Y' shakldagi oddiy tenglikni xavfsiz baholaydi."""
    m = re.fullmatch(r"\s*(chiqdi|kirdi)\.(\w+)\s*==\s*(chiqdi|kirdi)\.(\w+)\s*", ifoda or "")
    if not m:
        return None
    src = {"kirdi": kirdi or {}, "chiqdi": chiqdi or {}}
    a = src[m.group(1)].get(m.group(2))
    b = src[m.group(3)].get(m.group(4))
    if a is None or b is None:
        return None
    return a == b


# --------------------------------------------------------------------------
# audit — asosiy mantiq (standalone: testlar ham chaqira oladi)
# --------------------------------------------------------------------------
def audit(sana=None):
    sana = konfig.bugun(sana)
    agentlar = konfig.konfig_json("agentlar.json")

    # 1) X1 ga to'g'ridan-to'g'ri kelgan xabarlarni o'zi "oldi" qiladi (X0 -> X1)
    satrlar = uzatish.oqi(sana)
    mavjud_oldi_idlar = {s["uzatish_id"] for s in satrlar
                          if s["yonalish"] == "oldi" and s["kimga"] == AGENT_ID}
    for b in satrlar:
        if b["yonalish"] == "berdi" and b["kimga"] == AGENT_ID and b["uzatish_id"] not in mavjud_oldi_idlar:
            _oldi_yoz(sana, AGENT_ID, b)

    satrlar = uzatish.oqi(sana)  # yangilangan holat
    berdilar = [s for s in satrlar if s["yonalish"] == "berdi"]
    oldilar = [s for s in satrlar if s["yonalish"] == "oldi"]
    oldi_index = {(o["uzatish_id"], o["kimga"]): o for o in oldilar}

    hozir = konfig.hozir()
    insidentlar = []  # (agent, kod, daraja, xabar)

    # 2) UZ_KUTILDI / UZ_HASH / UZ_SONI
    for b in berdilar:
        # Xabar yetkazilishini N3 tekshiradi (shlyuz->N1/N2 ichki hop) — X1 fayl-sverkasi emas.
        if b.get("tur") == "xabar":
            continue
        tur = _tur_dan_obyekt(b["obyekt"])
        if b["kimga"] == "*":
            kutilganlar = [aid for aid, meta in agentlar.items()
                           if tur and tur in meta.get("oqiydi", []) and aid != b["kimdan"]]
        else:
            kutilganlar = [b["kimga"]]

        muddat_otdimi = True
        if b.get("kutish_daq"):
            try:
                vaqt_b = datetime.fromisoformat(b["vaqt"])
                muddat_otdimi = (hozir - vaqt_b).total_seconds() / 60.0 > b["kutish_daq"]
            except Exception:
                muddat_otdimi = True

        for kim in kutilganlar:
            o = oldi_index.get((b["uzatish_id"], kim))
            if o is None:
                if muddat_otdimi:
                    insidentlar.append((kim, "UZ_KUTILDI", "ogoh",
                        f"{kim}: {b['obyekt']} ({b['uzatish_id']}) hali olinmagan (kimdan {b['kimdan']})"))
                continue
            if o["hash"] != b["hash"]:
                insidentlar.append((kim, "UZ_HASH", "jiddiy",
                    f"{kim}: {b['obyekt']} hash farqi ({b['uzatish_id']}: berdi={b['hash']} oldi={o['hash']})"))
            if (o.get("soni") or {}) != (b.get("soni") or {}):
                insidentlar.append((kim, "UZ_SONI", "ogoh",
                    f"{kim}: {b['obyekt']} soni farqi ({b['uzatish_id']}: berdi={b.get('soni')} oldi={o.get('soni')})"))

    # 3) UZ_YETIM
    berdi_idlar = {b["uzatish_id"] for b in berdilar}
    for o in oldilar:
        if o["uzatish_id"] not in berdi_idlar:
            insidentlar.append((o["kimga"], "UZ_YETIM", "jiddiy",
                f"{o['kimga']}: {o['obyekt']} ({o['uzatish_id']}) oldi qildi, mos berdi topilmadi"))

    # 4) KPI tekshiruvlari + HB_YOQ
    for aid, meta in agentlar.items():
        kpi = kpi_mod.oqi(aid, sana)
        if kpi is None:
            if meta.get("tur") == "timer" and _bugun_kutilgan_allaqachon_otdimi(meta.get("jadval", "")):
                insidentlar.append((aid, "KPI_YOQ", "ogoh", f"{aid}: bugungi KPI fayli yo'q (jadval o'tgan)"))
            continue

        if kpi.get("kun", {}).get("xato", 0) > 0:
            insidentlar.append((aid, "KPI_XATO", "ogoh",
                f"{aid}: bugun {kpi['kun']['xato']} marta xato bilan tugagan"))

        for ish in kpi.get("ishlar", []):
            for ifoda in meta.get("kutilgan_nisbat", []):
                natija = _ifoda_baho(ifoda, ish.get("kirdi"), ish.get("chiqdi"))
                if natija is False:
                    insidentlar.append((aid, "KPI_NISBAT", "jiddiy",
                        f"{aid}: '{ifoda}' buzildi (kirdi={ish.get('kirdi')}, chiqdi={ish.get('chiqdi')})"))

        if heartbeat.oqi(aid) is None:
            insidentlar.append((aid, "HB_YOQ", "jiddiy",
                f"{aid}: KPI bor, lekin heartbeat hech qachon yozilmagan"))

    # 5) SHLYUZ_CHETLAB — statik grep, faqat agents/ (lib/inplus/adapter ichida
    #    real HTTP chaqiruvlar bo'lishi mumkin — bu qonuniy, X1 ularni tekshirmaydi)
    agents_dir = konfig.yol("agents")
    if agents_dir.exists():
        for py in sorted(agents_dir.rglob("*.py")):
            if py.parent.name == "x1_auditor":
                continue  # auditorning o'z pattern satri o'zini "ushlab olmasin"
            try:
                matn = py.read_text(encoding="utf-8")
            except Exception:
                continue
            if _SHLYUZ_NAQSH.search(matn):
                aid = py.parent.name.split("_")[0].upper() if py.parent.name != "agents" else "?"
                try:
                    rel = py.relative_to(konfig.ILDIZ)
                except ValueError:
                    rel = py
                insidentlar.append((aid, "SHLYUZ_CHETLAB", "jiddiy",
                    f"{rel}: shlyuzni chetlab o'tish belgisi topildi (api.telegram.org/sendMessage/smtplib)"))

    # 6) yozish (kontraktdagi 1-soatlik dedup mezoniga yaqin: bir xil satr qayta yozilmaydi)
    yangi = 0
    barcha_kodlar = set()
    for agent, kod, daraja, xabar in insidentlar:
        barcha_kodlar.add(kod)
        if _yozilganmi(sana, agent, kod, xabar):
            continue
        _insident_yoz(agent, kod, daraja, xabar, sana)
        yangi += 1

    matritsa = {}
    for aid in agentlar:
        xatolar = [i for i in insidentlar if i[0] == aid]
        matritsa[aid] = {"buzilgan": len(xatolar), "kodlar": sorted({i[1] for i in xatolar})}
    yashil = sum(1 for aid in agentlar if matritsa[aid]["buzilgan"] == 0)

    natija = {
        "versiya": "1.0", "sana": sana,
        "agentlar": matritsa,
        "jami": {
            "uzatish": len(satrlar), "buzilgan": len(insidentlar),
            "agent_tekshirildi": len(agentlar), "yashil": yashil,
            "yangi_insident": yangi, "kodlar": sorted(barcha_kodlar),
        },
    }
    fayl.json_yoz(konfig.data("x1", f"{sana}.json"), natija)

    # 7) wiki jadval
    md = [f"# Zanjirlar auditi — {sana}", "",
          "| Agent | Berdi | Oldi | Farq | KPI holati |", "|---|---|---|---|---|"]
    for aid in sorted(agentlar):
        b_soni = sum(1 for b in berdilar if b["kimdan"] == aid)
        o_soni = sum(1 for o in oldilar if o["kimga"] == aid)
        farq = matritsa[aid]["buzilgan"]
        belgi = "\U0001F7E2" if farq == 0 else "\U0001F534"
        md.append(f"| {aid} | {b_soni} | {o_soni} | {farq} | {belgi} |")
    fayl.yoz(konfig.yol("wiki", "jurnal", f"zanjir_{sana}.md"), "\n".join(md) + "\n")

    return natija


# --------------------------------------------------------------------------
# Agent skeleti orqali ishga tushirish
# --------------------------------------------------------------------------
class X1(Agent):
    agent_id = AGENT_ID
    nom = "Zanjirlar auditori"

    def ish(self) -> dict:
        natija = audit(self.sana)
        jami = natija["jami"]
        if jami["buzilgan"] > 0:
            try:
                tg_id = int(konfig.env("TG_ADMIN_ID", "0") or 0)
            except ValueError:
                tg_id = 0
            try:
                shlyuz_client.yubor(
                    kimdan_agent=AGENT_ID, kanal="tg",
                    kimga={"tur": "xodim", "id": "X-001", "telegram_id": tg_id},
                    skript_id="S-900", til="uz",
                    ozgaruvchilar={"agent": "X1",
                                   "xabar": f"zanjir auditi: {jami['buzilgan']} buzilgan ({', '.join(jami['kodlar'])})",
                                   "vaqt": konfig.iso()},
                    idempotent_kalit=f"X1:S-900:{self.sana}",
                )
            except Exception:
                pass
        return {
            "chiqdi": {"buzilgan": jami["buzilgan"]},
            "kpi": {"uzatish_jami": jami["uzatish"], "buzilgan": jami["buzilgan"],
                    "agent_tekshirildi": jami["agent_tekshirildi"], "yashil": jami["yashil"]},
        }


if __name__ == "__main__":
    sys.exit(ishga_tushir(X1))
