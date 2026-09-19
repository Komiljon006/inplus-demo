"""KPI: data/kpi/<agent>/<sana>.json — kun bo'yicha bitta fayl, ishlar[] ga qo'shiladi.
`kun` bloki har yozishda qayta hisoblanadi (agregat)."""
from . import konfig, fayl, kontrakt


def yol(agent_id: str, sana: str):
    return konfig.data("kpi", agent_id, f"{sana}.json")


def _agregat(ishlar):
    kun = {
        "ishlar_soni": len(ishlar),
        "ok": sum(1 for i in ishlar if i.get("holat") == "ok"),
        "xato": sum(1 for i in ishlar if i.get("holat") == "xato"),
        "davomiylik_s_jami": round(sum(float(i.get("davomiylik_s", 0)) for i in ishlar), 3),
        "kpi": {},
    }
    for ish in ishlar:
        for k, v in (ish.get("kpi") or {}).items():
            if isinstance(v, (int, float)):
                kun["kpi"][k] = kun["kpi"].get(k, 0) + v
    return kun


def qosh(agent_id: str, ish: dict, sana: str = None):
    """Bitta ish natijasini KPI ga qo'shadi va kun blokini qayta hisoblaydi.

    ish: {boshlandi, tugadi, davomiylik_s, holat, xato_soni, xato_oxirgi,
          kirdi, chiqdi, kpi}
    """
    sana = konfig.bugun(sana)
    p = yol(agent_id, sana)
    if p.exists():
        obj = fayl.json_oqi(p)
    else:
        obj = {"versiya": "1.0", "agent": agent_id, "sana": sana, "ishlar": [], "kun": {}}
    obj["ishlar"].append(ish)
    obj["kun"] = _agregat(obj["ishlar"])
    kontrakt.tekshir("kpi", obj)
    fayl.json_yoz(p, obj)
    return obj


def oqi(agent_id: str, sana: str = None):
    sana = konfig.bugun(sana)
    p = yol(agent_id, sana)
    if not p.exists():
        return None
    return fayl.json_oqi(p)
