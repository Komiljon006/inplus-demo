"""Paket kontrakti bilan ishlash. oqi() avtomat uzatish.oldi yozadi."""
from . import konfig, fayl, kontrakt, uzatish


def yol(sana: str):
    return konfig.data("paket", f"{sana}.json")


def joriy_yol():
    return konfig.data("paket", "joriy.json")


def _soni(obj: dict) -> dict:
    return {"lidlar": len(obj.get("lidlar", [])),
            "talabalar": len(obj.get("talabalar", []))}


def _obyekt_nom(sana: str) -> str:
    return f"data/paket/{sana}.json"


def yoz(obj: dict, kim: str = "D1", kutish_daq: int = 180) -> dict:
    """Paketni atomik yozadi, joriy.json symlink, uzatish(berdi, *)."""
    kontrakt.tekshir("paket", obj)
    sana = obj["paket_id"]
    p = yol(sana)
    # idempotent: agar aynan shu hash bilan fayl bor bo'lsa qayta uzatish yozmaymiz
    mavjud = None
    if p.exists():
        try:
            mavjud = fayl.json_oqi(p)
        except Exception:
            mavjud = None
    fayl.json_yoz(p, obj)
    fayl.symlink(p, joriy_yol())
    if not (mavjud and mavjud.get("hash") == obj.get("hash")):
        uzatish.berdi(kim, _obyekt_nom(sana), obj["hash"], tur="fayl",
                      kimga="*", soni=_soni(obj), kutish_daq=kutish_daq, sana=sana)
    return {"fayl": str(p), "hash": obj["hash"], "soni": _soni(obj)}


def oqi(kim: str, sana: str = None) -> dict:
    """joriy.json (yoki <sana>) o'qiydi, tekshiradi, uzatish.oldi yozadi."""
    if sana:
        p = yol(sana)
    else:
        p = joriy_yol()
    obj = fayl.json_oqi(p)
    kontrakt.tekshir("paket", obj)
    uzatish.oldi(kim, _obyekt_nom(obj["paket_id"]), obj["hash"],
                 tur="fayl", soni=_soni(obj))
    return obj
