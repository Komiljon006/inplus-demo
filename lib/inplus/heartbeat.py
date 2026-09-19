"""Heartbeat: run/heartbeat/<agent>.json (§2.5)."""
import os

from . import konfig, fayl, kontrakt


def yol(agent_id: str):
    return konfig.run_yol("heartbeat", f"{agent_id}.json")


def yoz(agent_id: str, holat: str, boshlandi: str = None, xabar: str = "",
        keyingi_kutilgan: str = None):
    """holat: boshladi | ishlayapti | tugadi | xato."""
    hb = {
        "agent": agent_id,
        "vaqt": konfig.iso(),
        "holat": holat,
        "pid": os.getpid(),
        "boshlandi": boshlandi,
        "xabar": xabar or "",
        "keyingi_kutilgan": keyingi_kutilgan,
    }
    kontrakt.tekshir("heartbeat", hb)
    fayl.json_yoz(yol(agent_id), hb)
    return hb


def oqi(agent_id: str):
    p = yol(agent_id)
    if not p.exists():
        return None
    return fayl.json_oqi(p)
