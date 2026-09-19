#!/usr/bin/env python3
"""X2 — Doktor (orkestr/nazorat, И1, `inplus-x2.service`, `Restart=always`).

Har siklda (30 s, `--oraliq` bilan sozlanadi) `konfig/agentlar.json` dagi HAR
BIR agent uchun `run/heartbeat/<id>.json` ni o'qiydi va §5 X2 qoidalariga
ko'ra insident yozadi + qayta yoqadi:
  (a) heartbeat fayli yo'q          -> hali ishga tushmagan, insident EMAS (demo)
  (b) holat == xato                 -> HB_XATO
  (c) holat == ishlayapti, eskirgan -> HB_ESKI (osilib qolgan)
  (d) holat == tugadi, muddat o'tgan -> HB_ESKI (timer o'tib ketti)
  (e) tur == service, heartbeat eski -> HB_ESKI

Qayta yoqish hisobi `data/x2/restart.json` da: har agent uchun {soni, oxirgi}.
`qayta_yoqish.max` dan oshsa -> RESTART_MAX (kritik), qayta yoqilmaydi, S-900
direktorga. Agent tuzalganda hisob nolga tushadi va ochiq insident yopiladi
(yangi jsonl yozuv, `yopildi` maydoni bilan, xuddi shu `insident_id`).

Mac'da systemd yo'q -> SIMULYATSIYA: `systemctl` topilmasa (yoki
`INPLUS_X2_SIMULYATSIYA=1` / `--simulyatsiya`), "qayta yoqish" — agentning
`main.py --bir-marta` ini to'g'ridan-to'g'ri qayta ishga tushirish (natija
heartbeat'dan darhol ko'rinadi). Linux'da `sudo systemctl restart inplus-<id>`.

Har siklda `data/dashboard.json` yoziladi (§6) — `www/index.html` shundan
o'qiydi.

Ishga tushirish:
  bin/inplus ishga X2                 # (--bir-marta bilan, bitta sikl)
  python3 agents/x2_doktor/main.py --sikl 3 --oraliq 5
  python3 agents/x2_doktor/main.py --bir-marta --simulyatsiya
"""
import os
import sys
import json
import time
import shutil
import urllib.request
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import konfig, heartbeat, kontrakt, fayl, jurnal, kpi as kpi_mod, shlyuz_client  # noqa: E402

AGENT_ID = "X2"
STANDART_QAYTA_YOQISH = {"max": 3, "oraliq_daq": 5}


# --------------------------------------------------------------------------
# yordamchi: vaqt
# --------------------------------------------------------------------------
def _daq_farq(vaqt_iso):
    if not vaqt_iso:
        return None
    try:
        vaqt = datetime.fromisoformat(vaqt_iso)
    except Exception:
        return None
    return (konfig.hozir() - vaqt).total_seconds() / 60.0


# --------------------------------------------------------------------------
# restart.json (data/x2/restart.json)
# --------------------------------------------------------------------------
def _restart_fayl():
    return konfig.data("x2", "restart.json")


def _restart_holat_oqi():
    p = _restart_fayl()
    if p.exists():
        try:
            return fayl.json_oqi(p)
        except Exception:
            return {}
    return {}


def _restart_holat_yoz(d):
    fayl.json_yoz(_restart_fayl(), d)


# --------------------------------------------------------------------------
# insident yozish (data/insident/<sana>.jsonl)
# --------------------------------------------------------------------------
def _keyingi_insident_id(sana):
    p = konfig.data("insident", f"{sana}.jsonl")
    n = len(jurnal.oqi(p))
    return f"i-{sana}-{n + 1:04d}"


def _insident_yoz(agent, kod, daraja, xabar, harakat=None, natija=None,
                   yopildi=None, insident_id=None, sana=None):
    sana = konfig.bugun(sana)
    satr = {
        "insident_id": insident_id or _keyingi_insident_id(sana),
        "vaqt": konfig.iso(),
        "kim": AGENT_ID,
        "agent": agent,
        "kod": kod,
        "daraja": daraja,
        "xabar": xabar,
        "harakat": harakat,
        "natija": natija,
        "yopildi": yopildi,
    }
    kontrakt.tekshir("insident", satr)
    jurnal.append(konfig.data("insident", f"{sana}.jsonl"), satr)
    return satr


def _yopish_yozuvi(ochiq_yozuv):
    """Sog'aygan agent uchun bir xil insident_id bilan 'yopildi' yozuvi."""
    return _insident_yoz(
        ochiq_yozuv["agent"], ochiq_yozuv["kod"], ochiq_yozuv["daraja"],
        f"{ochiq_yozuv['agent']} tuzaldi (heartbeat sog'lom)",
        harakat=None, natija="ok", yopildi=konfig.iso(),
        insident_id=ochiq_yozuv["insident_id"],
    )


def _s900_yubor(agent, xabar, muhimlik="jiddiy"):
    try:
        tg_id = int(konfig.env("TG_ADMIN_ID", "0") or 0)
    except ValueError:
        tg_id = 0
    try:
        shlyuz_client.yubor(
            kimdan_agent=AGENT_ID, kanal="tg",
            kimga={"tur": "xodim", "id": "X-001", "telegram_id": tg_id},
            skript_id="S-900", til="uz",
            ozgaruvchilar={"agent": agent, "xabar": xabar, "vaqt": konfig.iso()},
            idempotent_kalit=f"X2:S-900:{agent}:{konfig.bugun()}:{xabar[:40]}",
            muhimlik=muhimlik,
        )
    except Exception:
        pass  # shlyuz yo'q bo'lsa ham X2 yiqilmasin


def _shlyuz_statistika_ol():
    try:
        with urllib.request.urlopen(konfig.shlyuz_url() + "/statistika", timeout=2.0) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


# --------------------------------------------------------------------------
# qayta yoqish: systemctl (Linux/prod) yoki simulyatsiya (Mac/demo)
# --------------------------------------------------------------------------
def _systemctl_bor():
    if konfig.env("INPLUS_X2_SIMULYATSIYA", "0") == "1":
        return False
    return shutil.which("systemctl") is not None


def _agent_main_py(agent_id):
    agents_dir = konfig.yol("agents")
    if not agents_dir.exists():
        return None
    t = agent_id.lower()
    nomzodlar = []
    for d in sorted(agents_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        if d.name == t or d.name.startswith(t + "_"):
            nomzodlar.append(d)
    if not nomzodlar:
        return None
    p = nomzodlar[0] / "main.py"
    return p if p.exists() else None


def _restart_bajar(agent_id, meta):
    """(ok: bool, tafsilot: str) qaytaradi."""
    if _systemctl_bor():
        unit = meta.get("unit", f"inplus-{agent_id.lower()}")
        try:
            cp = subprocess.run(["sudo", "systemctl", "restart", unit],
                                 capture_output=True, text=True, timeout=30)
            return cp.returncode == 0, f"systemctl restart {unit} -> exit {cp.returncode}"
        except Exception as e:
            return False, f"systemctl xato: {type(e).__name__}: {e}"
    # --- simulyatsiya (Mac demo) ---
    main_py = _agent_main_py(agent_id)
    if main_py is None:
        return False, f"simulyatsiya: {agent_id} uchun agents/ ichida main.py topilmadi"
    env = dict(os.environ)
    env["INPLUS_ILDIZ"] = str(konfig.ILDIZ)
    try:
        cp = subprocess.run([sys.executable, str(main_py), "--bir-marta"],
                             capture_output=True, text=True, timeout=60, env=env)
        return True, f"simulyatsiya: {main_py.parent.name}/main.py --bir-marta -> exit {cp.returncode}"
    except Exception as e:
        return False, f"simulyatsiya xato: {type(e).__name__}: {e}"


# --------------------------------------------------------------------------
# muammo topish
# --------------------------------------------------------------------------
def _muammo_top(agent_id, meta):
    """(kod, daraja, xabar) yoki None."""
    hb = heartbeat.oqi(agent_id)
    if hb is None:
        return None  # hali ishga tushmagan (yoki servis hali qurilmagan) — insident emas
    sla = meta.get("sla_daq", 30) or 30
    tur = meta.get("tur", "timer")
    holat = hb.get("holat")
    yosh = _daq_farq(hb.get("vaqt"))

    if holat == "xato":
        return ("HB_XATO", "jiddiy", f"{agent_id}: heartbeat=xato — {hb.get('xabar') or '(xabarsiz)'}")

    if holat == "ishlayapti" and yosh is not None and yosh > sla:
        return ("HB_ESKI", "jiddiy",
                f"{agent_id}: 'ishlayapti' holatida {yosh:.1f} daq osilib qoldi (SLA {sla} daq)")

    if holat == "tugadi":
        keyingi = hb.get("keyingi_kutilgan")
        if keyingi:
            try:
                k = datetime.fromisoformat(keyingi)
                if konfig.hozir() > k + timedelta(minutes=sla):
                    return ("HB_ESKI", "ogoh", f"{agent_id}: keyingi_kutilgan + SLA o'tib ketti")
            except Exception:
                pass
        elif tur == "timer" and yosh is not None and yosh > sla:
            # demo soddalashtirish: `keyingi_kutilgan` hozircha to'ldirilmagan bo'lsa
            # oxirgi 'tugadi'dan SLA daqiqadan ko'p o'tganini belgi deb olamiz.
            return ("HB_ESKI", "ogoh",
                    f"{agent_id}: oxirgi 'tugadi'dan {yosh:.1f} daq o'tti (SLA {sla} daq)")

    if tur == "service" and yosh is not None and yosh > sla:
        return ("HB_ESKI", "jiddiy",
                f"{agent_id}: servis heartbeat {yosh:.1f} daq eski (SLA {sla} daq)")

    return None


def _qayta_yoqish_qarori(agent_id, meta, restart_holat):
    qy = meta.get("qayta_yoqish", STANDART_QAYTA_YOQISH)
    max_ = qy.get("max", 3)
    oraliq_daq = qy.get("oraliq_daq", 5)
    rec = restart_holat.get(agent_id, {"soni": 0, "oxirgi": None})
    if rec.get("soni", 0) >= max_:
        return "max_oshdi", rec, max_
    if rec.get("oxirgi"):
        yosh = _daq_farq(rec["oxirgi"])
        if yosh is not None and yosh < oraliq_daq:
            return "kutmoqda", rec, max_
    return "qayta_yoq", rec, max_


# --------------------------------------------------------------------------
# dashboard.json (§2.4 + §6)
# --------------------------------------------------------------------------
def _www_data_symlink_taminla():
    """www/index.html `data/dashboard.json` ni nisbiy fetch qiladi — nginx `alias www/`
    bo'lgani uchun `www/data -> ../data` symlink kerak. Idempotent, xato bo'lsa jim o'tadi."""
    www_data = konfig.yol("www", "data")
    haqiqiy_data = konfig.yol("data")
    try:
        if www_data.is_symlink() or www_data.exists():
            return
        if not konfig.yol("www").exists():
            return
        os.symlink(os.path.relpath(haqiqiy_data, www_data.parent), www_data)
    except Exception:
        pass


def _dashboard_yoz(agentlar, ochiq, sana):
    _www_data_symlink_taminla()
    satrlar = []
    for aid, meta in agentlar.items():
        hb = heartbeat.oqi(aid)
        sla = meta.get("sla_daq", 0) or 0
        kpi = kpi_mod.oqi(aid, sana)
        kun = (kpi or {}).get("kun", {})
        oc = ochiq.get(aid)
        if hb is None:
            holat, oxirgi, eski = None, None, False
        else:
            holat = hb.get("holat")
            oxirgi = hb.get("vaqt")
            yosh = _daq_farq(oxirgi)
            eski = bool(sla and yosh is not None and yosh > sla)

        if holat == "xato" or (oc and oc.get("daraja") == "kritik"):
            rang = "qizil"
        elif eski or oc:
            rang = "sariq"
        else:
            rang = "yashil"

        satrlar.append({
            "agent": aid, "nom": meta.get("nom", ""), "holat": holat, "oxirgi": oxirgi,
            "sla_daq": sla, "eski": eski,
            "ishlar_ok": kun.get("ok", 0), "ishlar_xato": kun.get("xato", 0),
            "davomiylik_s_jami": kun.get("davomiylik_s_jami", 0),
            "ochiq_insident": 1 if oc else 0,
            "insident_kod": oc.get("kod") if oc else None,
            "rang": rang,
        })

    dash = {
        "yangilandi": konfig.iso(),
        "sana": sana,
        "agentlar": satrlar,
        "shlyuz": _shlyuz_statistika_ol(),
    }
    fayl.json_yoz(konfig.data("dashboard.json"), dash)
    return dash


# --------------------------------------------------------------------------
# bitta sikl
# --------------------------------------------------------------------------
def sikl_bajar():
    sana = konfig.bugun()
    heartbeat.yoz(AGENT_ID, "ishlayapti", boshlandi=_X2.get("boshlandi"))

    agentlar = konfig.konfig_json("agentlar.json")
    restart_holat = _restart_holat_oqi()
    ochiq = restart_holat.get("_ochiq", {})

    natijalar = []
    restart_soni_bu_sikl = 0
    insident_soni_bu_sikl = 0

    for aid, meta in agentlar.items():
        if aid == AGENT_ID:
            continue
        muammo = _muammo_top(aid, meta)

        if muammo is None:
            if aid in ochiq:
                _yopish_yozuvi(ochiq[aid])
                del ochiq[aid]
                restart_holat[aid] = {"soni": 0, "oxirgi": None}
                natijalar.append({"agent": aid, "holat": "sog'aydi", "insident": "yopildi"})
            continue

        kod, daraja, xabar = muammo
        holat_q, rec, max_ = _qayta_yoqish_qarori(aid, meta, restart_holat)

        if holat_q == "kutmoqda":
            natijalar.append({"agent": aid, "kod": kod, "harakat": "kutmoqda (oraliq hali o'tmagan)"})
            continue

        if holat_q == "max_oshdi":
            if ochiq.get(aid, {}).get("kod") != "RESTART_MAX":
                yoz = _insident_yoz(aid, "RESTART_MAX", "kritik",
                                     f"{aid}: qayta yoqish {rec.get('soni', 0)}x (max {max_}) — TO'XTATILDI",
                                     harakat="qayta yoqilmadi (max oshdi)", natija="toxtatildi", sana=sana)
                ochiq[aid] = {"insident_id": yoz["insident_id"], "kod": "RESTART_MAX",
                              "daraja": "kritik", "agent": aid}
                _s900_yubor(aid, yoz["xabar"], muhimlik="kritik")
                insident_soni_bu_sikl += 1
            natijalar.append({"agent": aid, "kod": "RESTART_MAX", "harakat": "yo'q (to'xtatilgan)"})
            continue

        # --- qayta yoqish ---
        ok, tafsilot = _restart_bajar(aid, meta)
        restart_soni_bu_sikl += 1
        rec = restart_holat.get(aid, {"soni": 0, "oxirgi": None})
        rec["soni"] = rec.get("soni", 0) + 1
        rec["oxirgi"] = konfig.iso()
        restart_holat[aid] = rec

        hb2 = heartbeat.oqi(aid)
        sogaydi = bool(ok and hb2 is not None and hb2.get("holat") != "xato")
        natija = "ok" if sogaydi else ("qilindi" if ok else "xato")

        # 1 soatda 1 marta shu (agent,kod) uchun insident — allaqachon ochiq bo'lsa qayta yozmaymiz
        if ochiq.get(aid, {}).get("kod") == kod:
            yoz_id = ochiq[aid]["insident_id"]
        else:
            yoz_id = None
        yoz = _insident_yoz(aid, kod, daraja, xabar, harakat=tafsilot, natija=natija,
                             yopildi=konfig.iso() if sogaydi else None,
                             insident_id=yoz_id, sana=sana)
        insident_soni_bu_sikl += 1

        if sogaydi:
            restart_holat[aid] = {"soni": 0, "oxirgi": None}
            ochiq.pop(aid, None)
        else:
            ochiq[aid] = {"insident_id": yoz["insident_id"], "kod": kod, "daraja": daraja, "agent": aid}
            _s900_yubor(aid, xabar, muhimlik="kritik" if daraja == "kritik" else "jiddiy")

        natijalar.append({"agent": aid, "kod": kod, "harakat": tafsilot, "natija": natija})

    restart_holat["_ochiq"] = ochiq
    _restart_holat_yoz(restart_holat)
    _dashboard_yoz(agentlar, ochiq, sana)

    kpi_mod.qosh(AGENT_ID, {
        "boshlandi": konfig.iso(), "tugadi": konfig.iso(), "davomiylik_s": 0.0,
        "holat": "ok", "xato_soni": 0, "xato_oxirgi": None,
        "kirdi": {"agentlar": len(agentlar)}, "chiqdi": {"tekshirildi": len(agentlar)},
        "kpi": {"sikllar": 1, "restartlar": restart_soni_bu_sikl,
                "insidentlar": insident_soni_bu_sikl, "ochiq_insident": len(ochiq)},
    }, sana=sana)

    heartbeat.yoz(AGENT_ID, "ishlayapti", boshlandi=_X2.get("boshlandi"))
    return natijalar


_X2 = {"boshlandi": None}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(description="X2 — Doktor")
    p.add_argument("--bir-marta", action="store_true", help="bitta sikl, so'ng chiqadi")
    p.add_argument("--sikl", type=int, default=None,
                   help="N sikldan keyin chiqadi (0 = abadiy). --bir-marta dan ustun.")
    p.add_argument("--oraliq", type=float, default=30.0, help="sikllar orasidagi soniya")
    p.add_argument("--simulyatsiya", action="store_true",
                   help="systemctl bor bo'lsa ham simulyatsiya rejimini majburlaydi")
    p.add_argument("--sana", default=None)
    args = p.parse_args(argv)

    if args.simulyatsiya:
        os.environ["INPLUS_X2_SIMULYATSIYA"] = "1"
    if args.sana:
        os.environ.setdefault("INPLUS_SANA_QOLIP", args.sana)

    if args.sikl is not None:
        soni = None if args.sikl == 0 else args.sikl
    elif args.bir_marta:
        soni = 1
    else:
        soni = None  # abadiy (prod systemd service rejimi)

    _X2["boshlandi"] = konfig.iso()
    heartbeat.yoz(AGENT_ID, "boshladi", boshlandi=_X2["boshlandi"])
    jurnal.agent_log(AGENT_ID, {"vaqt": konfig.iso(), "voqea": "boshladi"})

    i = 0
    try:
        while True:
            natija = sikl_bajar()
            print(json.dumps({"sikl": i + 1, "natija": natija}, ensure_ascii=False, indent=2))
            i += 1
            if soni is not None and i >= soni:
                break
            time.sleep(args.oraliq)
    except Exception as e:
        heartbeat.yoz(AGENT_ID, "xato", boshlandi=_X2["boshlandi"], xabar=f"{type(e).__name__}: {e}")
        jurnal.agent_log(AGENT_ID, {"vaqt": konfig.iso(), "voqea": "xato", "xato": str(e)})
        raise

    heartbeat.yoz(AGENT_ID, "tugadi", boshlandi=_X2["boshlandi"], keyingi_kutilgan=None)
    jurnal.agent_log(AGENT_ID, {"vaqt": konfig.iso(), "voqea": "tugadi", "sikllar": i})
    return 0


if __name__ == "__main__":
    sys.exit(main())
