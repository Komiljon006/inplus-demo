#!/usr/bin/env python3
"""W1 — Xotira agenti (И1, timer 23:00 + `qayta` qo'lda).

Wiki manbasi:
  - `konfig/agentlar.json`  -> wiki/reestr/agentlar.md
  - `konfig/skriptlar.json` -> wiki/reestr/skriptlar.md
  - har agent papkasidagi `SOP.md`                -> wiki/agentlar/<id>.md
  - KPI + insident + (N3/X1 natijalari)           -> wiki/jurnal/<sana>.md
  - `data/insident/<sana>.jsonl`                  -> wiki/insident/<sana>.md
  - hammasi Markdown -> HTML (`wiki/_html/`), `markdown` paketi bo'lmasa
    oddiy `<pre>` bilan o'raladi.

Arxiv: `data/{uzatish,kpi,insident,jurnal}` 30 kundan eski fayllar oy bo'yicha
`data/arxiv/<YYYY-MM>.tar.gz` ga; `data/paket/` 14 kundan eski fayllar
`data/paket/arxiv/` ga oddiy ko'chiriladi.

Kunlik xulosa (S-901) direktorga TG orqali.

Ishga tushirish:
  bin/inplus ishga W1
  python3 agents/w1_xotira/main.py --bir-marta --sana 2026-09-19
"""
import html
import io
import re
import sys
import json
import shutil
import tarfile
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import konfig, kpi as kpi_mod, jurnal, fayl, paket, shlyuz_client  # noqa: E402
from inplus.agent import Agent, ishga_tushir  # noqa: E402

try:
    import markdown as _md
except ImportError:
    _md = None

AGENT_ID = "W1"
_SANA_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


# --------------------------------------------------------------------------
# markdown -> html
# --------------------------------------------------------------------------
_STIL = (
    "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
    "<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>"
    "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?"
    "family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Mono:wght@500&"
    "family=IBM+Plex+Sans:wght@400;500;600&display=swap\">"
    "<style>"
    ":root{--bg:#eef0f4;--s:#fff;--ink:#141b2b;--mut:#5c6678;--ln:#dde1e9;--ac:#236c78;--code:#0d1220;--codeink:#d7e0ec}"
    "@media(prefers-color-scheme:dark){:root{--bg:#0e1420;--s:#161e2c;--ink:#eef1f7;--mut:#9aa5b8;--ln:#2a3547;--ac:#5bb4c0;--code:#0a0f18;--codeink:#cdd6e4}}"
    "*{box-sizing:border-box}"
    "body{background:var(--bg);color:var(--ink);font-family:'IBM Plex Sans',system-ui,sans-serif;"
    "line-height:1.6;max-width:860px;margin:0 auto;padding:28px 16px 48px}"
    "h1,h2,h3{font-family:'Fraunces',Georgia,serif;font-weight:600;line-height:1.2;margin:1.4em 0 .4em}"
    "h1{font-size:clamp(24px,5vw,34px);margin-top:.2em}h2{font-size:20px}h3{font-size:16px}"
    "a{color:var(--ac);text-decoration:none}a:hover{text-decoration:underline}"
    "p,li{font-size:15px}ul{padding-left:20px}li{margin:.3em 0}"
    "code{font-family:'IBM Plex Mono',monospace;font-size:.9em;background:var(--bg);padding:1px 5px;border-radius:5px}"
    "pre{background:var(--code);color:var(--codeink);padding:14px;border-radius:12px;overflow:auto;"
    "font-family:'IBM Plex Mono',monospace;font-size:12px;line-height:1.5}pre code{background:none;padding:0}"
    "table{border-collapse:collapse;width:100%;font-size:13.5px;margin:10px 0}"
    "td,th{border-bottom:1px solid var(--ln);padding:7px 8px;text-align:left;vertical-align:top}"
    "th{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em;font-weight:600}"
    ".back{display:inline-block;font-size:13px;font-weight:600;color:var(--ac);"
    "border:1px solid var(--ln);border-radius:20px;padding:4px 12px;margin-bottom:6px}"
    "</style>"
)


def _md_to_html(matn: str, sarlavha: str, orqaga: str = "index.html") -> str:
    if _md is not None:
        try:
            tana = _md.markdown(matn, extensions=["tables"])
        except Exception:
            tana = f"<pre>{html.escape(matn)}</pre>"
    else:
        tana = f"<pre>{html.escape(matn)}</pre>"
    return (
        "<!doctype html><html lang=\"uz\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(sarlavha)}</title>{_STIL}</head><body>"
        f"<p><a class=\"back\" href=\"{orqaga}\">← wiki bosh sahifa</a></p>"
        f"{tana}</body></html>"
    )


def _html_yoz(rel_yol: str, matn: str, sarlavha: str):
    p = konfig.yol("wiki", "_html", rel_yol)
    # subpapka chuqurligiga qarab bosh sahifaga to'g'ri nisbiy yo'l
    chuqur = rel_yol.replace("\\", "/").count("/")
    orqaga = "../" * chuqur + "index.html"
    fayl.yoz(p, _md_to_html(matn, sarlavha, orqaga))


# --------------------------------------------------------------------------
# reestrlar
# --------------------------------------------------------------------------
def _jadval_md(sarlavha, ustunlar, qatorlar):
    lines = [f"# {sarlavha}", "", "| " + " | ".join(ustunlar) + " |",
             "|" + "|".join(["---"] * len(ustunlar)) + "|"]
    for q in qatorlar:
        lines.append("| " + " | ".join("" if x is None else str(x) for x in q) + " |")
    return "\n".join(lines) + "\n"


def _agentlar_reestr_md(agentlar):
    qatorlar = []
    for aid, meta in sorted(agentlar.items()):
        qatorlar.append([aid, meta.get("nom", ""), meta.get("tur", ""),
                          meta.get("jadval", meta.get("unit", "")), meta.get("sla_daq", ""),
                          meta.get("egasi", "—"), meta.get("ijro", "")])
    return _jadval_md("Agentlar reestri", ["ID", "Nom", "Tur", "Jadval/Unit", "SLA (daq)", "Egasi", "Ijro"], qatorlar)


def _skriptlar_reestr_md(reestr):
    qatorlar = []
    for s in reestr.get("skriptlar", []):
        qatorlar.append([s["skript_id"], s.get("nom", ""), ",".join(s.get("kanallar", [])),
                          s.get("holat", ""), ",".join(s.get("ruxsat_agentlar", []))])
    return _jadval_md("Skriptlar reestri", ["ID", "Nom", "Kanallar", "Holat", "Ruxsat"], qatorlar)


# --------------------------------------------------------------------------
# SOP yig'ish
# --------------------------------------------------------------------------
def _agent_id_papkadan(dir_nomi):
    return dir_nomi.split("_")[0].upper()


def _sop_larni_yigish():
    agents_dir = konfig.yol("agents")
    natija = {}
    if not agents_dir.exists():
        return natija
    for d in sorted(agents_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        sop = d / "SOP.md"
        if sop.exists():
            try:
                natija[_agent_id_papkadan(d.name)] = sop.read_text(encoding="utf-8")
            except Exception:
                continue
    return natija


# --------------------------------------------------------------------------
# kunlik xulosa
# --------------------------------------------------------------------------
def _kunlik_xulosa_md(sana, agentlar):
    satr = [f"# Kunlik jurnal — {sana}", "", "## Agentlar KPI",
            "| Agent | Ishlar | OK | Xato |", "|---|---|---|---|"]
    for aid in sorted(agentlar):
        kpi = kpi_mod.oqi(aid, sana)
        kun = (kpi or {}).get("kun", {})
        satr.append(f"| {aid} | {kun.get('ishlar_soni', 0)} | {kun.get('ok', 0)} | {kun.get('xato', 0)} |")

    x2_kpi = kpi_mod.oqi("X2", sana)
    if x2_kpi:
        x2_kun = x2_kpi.get("kun", {}).get("kpi", {})
        satr += ["", f"## X2 doktor: sikllar={x2_kun.get('sikllar', 0)}, "
                     f"restartlar={x2_kun.get('restartlar', 0)}, "
                     f"insidentlar={x2_kun.get('insidentlar', 0)}, "
                     f"ochiq={x2_kun.get('ochiq_insident', 0)}"]

    insidentlar = jurnal.oqi(konfig.data("insident", f"{sana}.jsonl"))
    ochiq = [i for i in insidentlar if not i.get("yopildi")]
    satr += ["", f"## Insidentlar ({len(insidentlar)} jami, {len(ochiq)} ochiq)"]
    if not insidentlar:
        satr.append("Bugun insident yo'q.")
    for i in insidentlar:
        holat_belgi = "yopiq" if i.get("yopildi") else "OCHIQ"
        satr.append(f"- `{i['kod']}` **{i['agent']}** ({i['kim']}) — {i['xabar']} [{holat_belgi}]")

    x1_p = konfig.data("x1", f"{sana}.json")
    if x1_p.exists():
        try:
            x1_natija = fayl.json_oqi(x1_p)
            jami = x1_natija.get("jami", {})
            satr += ["", f"## X1 audit: buzilgan={jami.get('buzilgan', 0)}, "
                         f"yashil={jami.get('yashil', 0)}/{jami.get('agent_tekshirildi', 0)}"]
        except Exception:
            pass

    n3_p = konfig.data("n3", f"{sana}.json")
    if n3_p.exists():
        try:
            n3_natija = fayl.json_oqi(n3_p)
            satr += ["", "## N3 post-audit", "```json", json.dumps(n3_natija, ensure_ascii=False, indent=2), "```"]
        except Exception:
            pass

    return "\n".join(satr) + "\n"


def _insident_md(sana, insidentlar):
    lines = [f"# Insidentlar — {sana}", ""]
    if not insidentlar:
        lines.append("Bugun insident yo'q.")
    else:
        lines += ["| ID | Kim | Agent | Kod | Daraja | Xabar | Yopildi |",
                   "|---|---|---|---|---|---|---|"]
        for i in insidentlar:
            yopiq_belgi = "✅" if i.get('yopildi') else "—"
            lines.append(f"| {i['insident_id']} | {i['kim']} | {i['agent']} | {i['kod']} | "
                         f"{i['daraja']} | {i['xabar']} | {yopiq_belgi} |")
    return "\n".join(lines) + "\n"


def _index_html(sana, sop_lar):
    lar = "".join(f'<li><a href="agentlar/{aid}.html">{aid}</a></li>' for aid in sorted(sop_lar))
    return (
        "<!doctype html><html lang=\"uz\"><head><meta charset=\"utf-8\">"
        f"<title>IN PLUS wiki</title>{_STIL}</head><body>"
        "<h1>IN PLUS — wiki</h1>"
        "<h2>Reestr</h2>"
        "<ul><li><a href=\"reestr/agentlar.html\">Agentlar reestri</a></li>"
        "<li><a href=\"reestr/skriptlar.html\">Skriptlar reestri</a></li></ul>"
        f"<h2>Agentlar (SOP) — {len(sop_lar)}</h2><ul>{lar}</ul>"
        f"<h2>Bugungi kun — {sana}</h2>"
        f"<ul><li><a href=\"jurnal/{sana}.html\">Kunlik jurnal</a></li>"
        f"<li><a href=\"insident/{sana}.html\">Insidentlar</a></li></ul>"
        "</body></html>"
    )


# --------------------------------------------------------------------------
# arxiv
# --------------------------------------------------------------------------
def _sana_dan(nom):
    m = _SANA_RE.search(nom)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except Exception:
        return None


def _eskimi(fayl_sanasi, bugun, kunlar):
    return fayl_sanasi is not None and (bugun - fayl_sanasi).days > kunlar


def arxivla(bugun=None):
    bugun = bugun or konfig.hozir().date()
    natija = {"tar": 0, "kochirilgan": 0}

    # 1) data/paket/*.json (joriy.json dan tashqari) -> arxiv/ (14 kun, oddiy ko'chirish)
    paket_dir = konfig.data("paket")
    if paket_dir.exists():
        arxiv_dir = paket_dir / "arxiv"
        for p in list(paket_dir.glob("*.json")):
            if p.name == "joriy.json":
                continue
            if _eskimi(_sana_dan(p.name), bugun, 14):
                arxiv_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(arxiv_dir / p.name))
                natija["kochirilgan"] += 1

    # 2) uzatish / kpi / insident / jurnal-agent / jurnal-xabar -> 30 kun -> tar.gz (oyma-oy)
    nomzodlar = []
    if konfig.data("uzatish").exists():
        nomzodlar += list(konfig.data("uzatish").glob("*.jsonl"))
    if konfig.data("insident").exists():
        nomzodlar += list(konfig.data("insident").glob("*.jsonl"))
    kpi_dir = konfig.data("kpi")
    if kpi_dir.exists():
        for agent_dir in kpi_dir.iterdir():
            if agent_dir.is_dir():
                nomzodlar += list(agent_dir.glob("*.json"))
    jurnal_agent_dir = konfig.data("jurnal", "agent")
    if jurnal_agent_dir.exists():
        for agent_dir in jurnal_agent_dir.iterdir():
            if agent_dir.is_dir():
                nomzodlar += list(agent_dir.glob("*.log"))
    jurnal_xabar_dir = konfig.data("jurnal", "xabar")
    if jurnal_xabar_dir.exists():
        nomzodlar += list(jurnal_xabar_dir.glob("*.jsonl"))

    oy_guruh = {}
    for p in nomzodlar:
        sanasi = _sana_dan(p.name)
        if not _eskimi(sanasi, bugun, 30):
            continue
        oy_guruh.setdefault(sanasi.strftime("%Y-%m"), []).append(p)

    if oy_guruh:
        arxiv_dir = konfig.data("arxiv")
        arxiv_dir.mkdir(parents=True, exist_ok=True)
        for oy, fayllar in oy_guruh.items():
            tar_p = arxiv_dir / f"{oy}.tar.gz"
            mavjud_azolar = {}
            if tar_p.exists():
                with tarfile.open(tar_p, "r:gz") as t:
                    for m in t.getmembers():
                        f = t.extractfile(m)
                        if f is not None:
                            mavjud_azolar[m.name] = f.read()
            with tarfile.open(tar_p, "w:gz") as t:
                for nom, malumot in mavjud_azolar.items():
                    info = tarfile.TarInfo(nom)
                    info.size = len(malumot)
                    t.addfile(info, io.BytesIO(malumot))
                for p in fayllar:
                    arcname = str(p.relative_to(konfig.ILDIZ / "data"))
                    t.add(p, arcname=arcname)
            for p in fayllar:
                p.unlink()
            natija["tar"] += len(fayllar)

    return natija


def arxiv_oqi(nisbiy_yol: str):
    """`data/<nisbiy_yol>` ni o'qiydi; topilmasa arxiv tar.gz'lardan qidiradi.
    `bin/inplus arxiv oqi <nisbiy_yol>` shu funksiyani chaqiradi."""
    qismlar = nisbiy_yol.strip("/").split("/")
    p = konfig.data(*qismlar)
    if p.exists():
        return p.read_text(encoding="utf-8")
    sanasi = _sana_dan(Path(nisbiy_yol).name)
    if sanasi is None:
        return None
    tar_p = konfig.data("arxiv", f"{sanasi.strftime('%Y-%m')}.tar.gz")
    if not tar_p.exists():
        return None
    with tarfile.open(tar_p, "r:gz") as t:
        try:
            a = t.getmember(nisbiy_yol.strip("/"))
        except KeyError:
            return None
        f = t.extractfile(a)
        return f.read().decode("utf-8") if f else None


# --------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------
class W1(Agent):
    agent_id = AGENT_ID
    nom = "Xotira"

    def ish(self) -> dict:
        sana = self.sana
        agentlar = konfig.konfig_json("agentlar.json")
        skriptlar = konfig.konfig_json("skriptlar.json")

        agentlar_md = _agentlar_reestr_md(agentlar)
        fayl.yoz(konfig.yol("wiki", "reestr", "agentlar.md"), agentlar_md)
        skript_md = _skriptlar_reestr_md(skriptlar)
        fayl.yoz(konfig.yol("wiki", "reestr", "skriptlar.md"), skript_md)

        sop_lar = _sop_larni_yigish()
        for aid, matn in sop_lar.items():
            fayl.yoz(konfig.yol("wiki", "agentlar", f"{aid}.md"), matn)

        kunlik_md = _kunlik_xulosa_md(sana, agentlar)
        fayl.yoz(konfig.yol("wiki", "jurnal", f"{sana}.md"), kunlik_md)

        insidentlar = jurnal.oqi(konfig.data("insident", f"{sana}.jsonl"))
        insident_md = _insident_md(sana, insidentlar)
        fayl.yoz(konfig.yol("wiki", "insident", f"{sana}.md"), insident_md)

        # HTML
        _html_yoz("reestr/agentlar.html", agentlar_md, "Agentlar reestri")
        _html_yoz("reestr/skriptlar.html", skript_md, "Skriptlar reestri")
        for aid, matn in sop_lar.items():
            _html_yoz(f"agentlar/{aid}.html", matn, f"SOP — {aid}")
        _html_yoz(f"jurnal/{sana}.html", kunlik_md, f"Kunlik jurnal {sana}")
        _html_yoz(f"insident/{sana}.html", insident_md, f"Insidentlar {sana}")
        fayl.yoz(konfig.yol("wiki", "_html", "index.html"), _index_html(sana, sop_lar))

        arxiv_natija = arxivla()

        # S-901 kunlik xulosa (direktor)
        paket_stat = {}
        try:
            p = paket.oqi(AGENT_ID)
            paket_stat = p.get("statistika", {})
        except Exception:
            pass
        ok_agentlar = 0
        for aid in agentlar:
            kun = (kpi_mod.oqi(aid, sana) or {}).get("kun", {})
            if kun and kun.get("xato", 0) == 0:
                ok_agentlar += 1
        try:
            tg_id = int(konfig.env("TG_ADMIN_ID", "0") or 0)
        except ValueError:
            tg_id = 0
        try:
            shlyuz_client.yubor(
                kimdan_agent=AGENT_ID, kanal="tg",
                kimga={"tur": "xodim", "id": "X-001", "telegram_id": tg_id},
                skript_id="S-901", til="uz",
                ozgaruvchilar={"sana": sana, "lidlar": paket_stat.get("lidlar", 0),
                               "faol": paket_stat.get("faol_talabalar", 0),
                               "qarzdor": paket_stat.get("qarzdorlar", 0),
                               "ok": ok_agentlar, "jami": len(agentlar)},
                idempotent_kalit=f"W1:S-901:{sana}",
            )
        except Exception:
            pass

        return {
            "chiqdi": {"sop": len(sop_lar), "html": len(sop_lar) + 4},
            "kpi": {"sop_yozildi": len(sop_lar), "arxiv_tar": arxiv_natija.get("tar", 0),
                    "arxiv_kochirilgan": arxiv_natija.get("kochirilgan", 0)},
        }


if __name__ == "__main__":
    sys.exit(ishga_tushir(W1))
