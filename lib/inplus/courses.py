"""Courses kontrakti bilan ishlash. oqi() avtomat uzatish.oldi yozadi."""
from . import konfig, fayl, kontrakt, uzatish


def yol():
    return konfig.data("courses.json")


def tarix_yol(sana: str):
    return konfig.data("courses", f"{sana}.json")


def _soni(obj: dict) -> dict:
    guruh = sum(len(k.get("guruhlar", [])) for k in obj.get("kurslar", []))
    return {"kurslar": len(obj.get("kurslar", [])), "guruhlar": guruh}


def yoz(obj: dict, kim: str = "D6", sana: str = None) -> dict:
    """courses.json (validatsiya != xato bo'lsa) + tarix + uzatish(berdi, *).
    validatsiya.holat == 'xato' bo'lsa: courses.json YANGILANMAYDI, faqat <sana>.xato.json."""
    kontrakt.tekshir("courses", obj)
    sana = konfig.bugun(sana)
    xato = obj["validatsiya"]["holat"] == "xato"
    h = fayl.hash_obj(obj)
    if xato:
        fayl.json_yoz(konfig.data("courses", f"{sana}.xato.json"), obj)
        return {"fayl": None, "yangilandi": False, "hash": h, "xato": True}
    fayl.json_yoz(tarix_yol(sana), obj)
    fayl.json_yoz(yol(), obj)
    uzatish.berdi(kim, "data/courses.json", h, tur="fayl",
                  kimga="*", soni=_soni(obj), sana=sana)
    return {"fayl": str(yol()), "yangilandi": True, "hash": h, "xato": False}


def oqi(kim: str) -> dict:
    """courses.json o'qiydi, tekshiradi, uzatish.oldi yozadi."""
    p = yol()
    obj = fayl.json_oqi(p)
    kontrakt.tekshir("courses", obj)
    uzatish.oldi(kim, "data/courses.json", fayl.hash_obj(obj),
                 tur="fayl", soni=_soni(obj))
    return obj


def kurs_idlar(obj: dict = None) -> set:
    """courses ichidagi barcha kurs_id."""
    if obj is None:
        if not yol().exists():
            return set()
        obj = fayl.json_oqi(yol())
    return {k["kurs_id"] for k in obj.get("kurslar", [])}


def guruh_idlar(obj: dict = None) -> set:
    if obj is None:
        if not yol().exists():
            return set()
        obj = fayl.json_oqi(yol())
    return {g["guruh_id"] for k in obj.get("kurslar", []) for g in k.get("guruhlar", [])}
