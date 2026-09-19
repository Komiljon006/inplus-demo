#!/usr/bin/env python3
"""N3 — Skriptlar reestri + post-audit.

Ikki mustaqil buyruq:
  python3 main.py tekshir [--fayl konfig/skriptlar.json]
      Reestr sintaksisini tekshiradi (git-hook/qo'lda). Xato bo'lsa exit 1 —
      shlyuz eski reestrni ishlatishda davom etadi.
  python3 main.py audit [--bir-marta] [--sana 2026-09-19] [--rejim mock]
      Kunlik post-audit (timer 21:00): jurnal x skriptlar x shlyuz.db sverka.
  python3 main.py --bir-marta ...
      Subkomandasiz chaqirilsa ham `audit` (bin/inplus ishga N3 shu holatda
      chaqiradi — Agent skeleti bilan bir xil interfeys).
"""
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import konfig, kontrakt, jurnal, shlyuz_client  # noqa: E402
from inplus.agent import Agent, ishga_tushir  # noqa: E402

PLACEHOLDER = re.compile(r"\{(\w+)\}")


# ----------------------------------------------------------------------
# tekshir — reestr sintaksisi
# ----------------------------------------------------------------------
def tekshir(fayl_path: str = None) -> dict:
    """{'ok': bool, 'xatolar': [...], 'ogohlantirishlar': [...]}"""
    p = Path(fayl_path) if fayl_path else konfig.konfig_yol("skriptlar.json")
    obj = json.loads(p.read_text(encoding="utf-8"))

    xatolar = []
    ogohlantirishlar = []

    try:
        kontrakt.tekshir("skript", obj)
    except kontrakt.KontraktXato as e:
        xatolar.append(f"SXEMA: {e}")
        return {"ok": False, "xatolar": xatolar, "ogohlantirishlar": ogohlantirishlar}

    korilgan_id = set()
    for s in obj.get("skriptlar", []):
        sid = s.get("skript_id")
        if sid in korilgan_id:
            xatolar.append(f"{sid}: skript_id takror")
        korilgan_id.add(sid)

        ozgaruvchilar = set(s.get("ozgaruvchilar", []))
        matnlar = s.get("matn") or {}
        for til, shablon in matnlar.items():
            topilgan = set(PLACEHOLDER.findall(shablon))
            if topilgan != ozgaruvchilar:
                yetishmagan = sorted(ozgaruvchilar - topilgan)
                ortiqcha = sorted(topilgan - ozgaruvchilar)
                xatolar.append(
                    f"{sid}[{til}]: {{…}} <-> ozgaruvchilar mos emas "
                    f"(matnda yo'q: {yetishmagan}, ozgaruvchilarda ortiqcha: {ortiqcha})"
                )

        if s.get("holat") == "arxiv" and s.get("ruxsat_agentlar"):
            ogohlantirishlar.append(f"{sid}: arxiv skriptda ruxsat_agentlar hali bor")

        if "sms" in s.get("kanallar", []):
            maxlen = s.get("sms_uzunlik_max")
            if maxlen:
                shablon = matnlar.get("uz") or (next(iter(matnlar.values())) if matnlar else "")
                taxminiy = PLACEHOLDER.sub(lambda m: "x" * 15, shablon)
                if len(taxminiy) > maxlen:
                    xatolar.append(
                        f"{sid}: taxminiy SMS uzunligi {len(taxminiy)} > {maxlen} "
                        f"(o'zgaruvchilar 15 belgi deb hisoblanganda)"
                    )

    return {"ok": not xatolar, "xatolar": xatolar, "ogohlantirishlar": ogohlantirishlar}


def cmd_tekshir(argv):
    ap = argparse.ArgumentParser(prog="n3 tekshir")
    ap.add_argument("--fayl", default=None)
    args = ap.parse_args(argv)
    natija = tekshir(args.fayl)
    for x in natija["xatolar"]:
        print(f"XATO: {x}")
    for o in natija["ogohlantirishlar"]:
        print(f"OGOH: {o}")
    print("tekshir: OK" if natija["ok"] else f"tekshir: XATO ({len(natija['xatolar'])})")
    return 0 if natija["ok"] else 1


# ----------------------------------------------------------------------
# audit — kunlik post-audit
# ----------------------------------------------------------------------
def _db_qatorlar(sana: str):
    db_yol = konfig.data("shlyuz.db")
    if not db_yol.exists():
        return []
    conn = sqlite3.connect(str(db_yol))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM xabarlar WHERE yaratildi LIKE ? ORDER BY yaratildi",
            (f"{sana}%",)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _jurnal_yozuvlar(sana: str):
    p = konfig.data("jurnal", "xabar", f"{sana}.jsonl")
    return jurnal.oqi(p)


def _matnga_mos(shablon: str, ozgaruvchilar_royxati, matn_tayyor: str) -> bool:
    escaped = re.escape(shablon)
    for var in ozgaruvchilar_royxati:
        escaped = escaped.replace(re.escape("{" + var + "}"), ".+?")
    pattern = "^" + escaped + "$"
    try:
        return re.match(pattern, matn_tayyor, re.DOTALL) is not None
    except re.error:
        return True  # shubhali holatda tutib qolmaymiz


def audit(sana: str = None) -> dict:
    sana = konfig.bugun(sana)
    reestr = konfig.konfig_json("skriptlar.json")
    skriptlar = {s["skript_id"]: s for s in reestr.get("skriptlar", [])}

    db_qatorlar = _db_qatorlar(sana)
    jsonl_yozuvlar = _jurnal_yozuvlar(sana)

    db_id = {r["xabar_id"] for r in db_qatorlar if r.get("xabar_id")}
    jsonl_id = {r["xabar_id"] for r in jsonl_yozuvlar if r.get("xabar_id")}

    nomuvofiqliklar = []

    for xid in sorted(jsonl_id - db_id):
        nomuvofiqliklar.append({"kod": "JURNAL_DB_FARQ", "xabar_id": xid,
                                "tafsilot": "jurnalda bor, shlyuz.db da yo'q"})
    for xid in sorted(db_id - jsonl_id):
        nomuvofiqliklar.append({"kod": "JURNAL_DB_FARQ", "xabar_id": xid,
                                "tafsilot": "shlyuz.db da bor, jurnalda yo'q"})

    kunlik_hisob = {}  # (skript_id, manzil) -> son (bir_odamga_kunlik uchun)
    skript_kunlik_hisob = {}  # skript_id -> son (kunlik_jami uchun)

    for row in db_qatorlar:
        skript_id = row.get("skript_id")
        skript = skriptlar.get(skript_id)
        holat = row.get("holat")

        if holat != "rad":
            kalit = (skript_id, row.get("manzil"))
            kunlik_hisob[kalit] = kunlik_hisob.get(kalit, 0) + 1
            skript_kunlik_hisob[skript_id] = skript_kunlik_hisob.get(skript_id, 0) + 1

        if skript is None:
            continue

        if holat not in ("rad",) and row.get("matn_tayyor"):
            matnlar = skript.get("matn") or {}
            shablon = matnlar.get(row.get("til"))
            if shablon is not None:
                ozgaruvchilar_royxati = skript.get("ozgaruvchilar", [])
                if not _matnga_mos(shablon, ozgaruvchilar_royxati, row["matn_tayyor"]):
                    nomuvofiqliklar.append({
                        "kod": "SHABLON_FARQ", "xabar_id": row["xabar_id"],
                        "tafsilot": f"matn_tayyor joriy shablonga mos emas (skript {skript_id})",
                    })

        if holat != "rad":
            ruxsat_agentlar = skript.get("ruxsat_agentlar", [])
            if "*" not in ruxsat_agentlar and row.get("kimdan_agent") not in ruxsat_agentlar:
                nomuvofiqliklar.append({
                    "kod": "RUXSAT_BUZILDI", "xabar_id": row["xabar_id"],
                    "tafsilot": f"{row.get('kimdan_agent')} {skript_id} yuborishga ruxsatsiz",
                })

        if holat == "yuborildi" and row.get("yuborildi"):
            try:
                from datetime import datetime, timedelta
                yuborildi_vaqt = datetime.fromisoformat(row["yuborildi"])
                hozir = konfig.hozir()
                if (hozir - yuborildi_vaqt) > timedelta(hours=24):
                    nomuvofiqliklar.append({
                        "kod": "ESKI_YUBORILDI", "xabar_id": row["xabar_id"],
                        "tafsilot": "24 soatdan ortiq 'yuborildi' holatida qolgan",
                    })
            except Exception:
                pass

    for (skript_id, manzil), son in kunlik_hisob.items():
        skript = skriptlar.get(skript_id)
        if not skript:
            continue
        limit = (skript.get("limit") or {}).get("bir_odamga_kunlik")
        if limit and son > limit:
            nomuvofiqliklar.append({
                "kod": "LIMIT_OSHIB_KETDI", "skript_id": skript_id, "manzil": manzil,
                "tafsilot": f"bir_odamga_kunlik={limit}, haqiqatda {son}",
            })
    for skript_id, son in skript_kunlik_hisob.items():
        skript = skriptlar.get(skript_id)
        if not skript:
            continue
        limit = (skript.get("limit") or {}).get("kunlik_jami")
        if limit and son > limit:
            nomuvofiqliklar.append({
                "kod": "LIMIT_OSHIB_KETDI", "skript_id": skript_id,
                "tafsilot": f"kunlik_jami={limit}, haqiqatda {son}",
            })

    kesim = {}
    for row in db_qatorlar:
        kalit = (row.get("skript_id"), row.get("holat"))
        kesim[kalit] = kesim.get(kalit, 0) + 1

    kpi = {
        "xabar_jami": len(db_qatorlar),
        "yuborildi": sum(1 for r in db_qatorlar if r.get("holat") in ("yuborildi", "yetkazildi")),
        "yetkazildi": sum(1 for r in db_qatorlar if r.get("holat") == "yetkazildi"),
        "rad": sum(1 for r in db_qatorlar if r.get("holat") == "rad"),
        "xato": sum(1 for r in db_qatorlar if r.get("holat") == "xato"),
        "narx_som": sum(r.get("narx_som") or 0 for r in db_qatorlar),
        "nomuvofiq": len(nomuvofiqliklar),
    }

    natija = {
        "sana": sana, "kpi": kpi,
        "kesim": [{"skript_id": sid, "holat": hol, "son": son}
                  for (sid, hol), son in sorted(kesim.items(), key=lambda x: (x[0][0] or "", x[0][1] or ""))],
        "nomuvofiqliklar": nomuvofiqliklar,
    }

    n3_fayl = konfig.data("n3", f"{sana}.json")
    n3_fayl.parent.mkdir(parents=True, exist_ok=True)
    n3_fayl.write_text(json.dumps(natija, ensure_ascii=False, indent=2), encoding="utf-8")

    _wiki_yoz(sana, natija)

    if kpi["nomuvofiq"] > 0:
        royxat = ", ".join(f"{n['kod']}:{n.get('xabar_id') or n.get('skript_id')}"
                           for n in nomuvofiqliklar[:10])
        tg_admin = konfig.env("TG_ADMIN_ID", "")
        shlyuz_client.yubor(
            "N3", "tg",
            {"tur": "xodim", "id": "X-001",
             "telegram_id": int(tg_admin) if tg_admin else None, "telefon": None},
            "S-900",
            {"agent": "N3", "xabar": f"post-audit: {kpi['nomuvofiq']} nomuvofiqlik ({royxat})",
             "vaqt": konfig.iso()},
            idempotent_kalit=f"N3:S-900:{sana}",
            muhimlik="kritik",
        )

    return {
        "kirdi": {"jurnal_satr": len(jsonl_yozuvlar), "db_qator": len(db_qatorlar)},
        "chiqdi": {"fayl": f"data/n3/{sana}.json"},
        "kpi": kpi,
    }


def _wiki_yoz(sana: str, natija: dict):
    p = konfig.yol("wiki", "reestr", f"xabar_audit_{sana}.md")
    p.parent.mkdir(parents=True, exist_ok=True)
    satrlar = [f"# Xabar auditi — {sana}", "", "## KPI", ""]
    for k, v in natija["kpi"].items():
        satrlar.append(f"- **{k}**: {v}")
    satrlar += ["", "## Skript x holat", "", "| skript_id | holat | son |", "|---|---|---|"]
    for row in natija["kesim"]:
        satrlar.append(f"| {row['skript_id']} | {row['holat']} | {row['son']} |")
    satrlar += ["", "## Nomuvofiqliklar", ""]
    if natija["nomuvofiqliklar"]:
        satrlar.append("| kod | obyekt | tafsilot |")
        satrlar.append("|---|---|---|")
        for n in natija["nomuvofiqliklar"]:
            obyekt = n.get("xabar_id") or n.get("skript_id") or ""
            satrlar.append(f"| {n['kod']} | {obyekt} | {n.get('tafsilot', '')} |")
    else:
        satrlar.append("Yo'q — hammasi mos.")
    p.write_text("\n".join(satrlar) + "\n", encoding="utf-8")


class N3Audit(Agent):
    agent_id = "N3"
    nom = "Skript reestri + post-audit"

    def ish(self) -> dict:
        return audit(self.sana)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "tekshir":
        return cmd_tekshir(argv[1:])
    if argv and argv[0] == "audit":
        argv = argv[1:]
    return ishga_tushir(N3Audit, argv)


if __name__ == "__main__":
    sys.exit(main())
