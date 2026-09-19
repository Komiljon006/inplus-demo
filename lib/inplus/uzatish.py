"""Uzatish jurnali (peredacha) — data/uzatish/<sana>.jsonl (§2.3).
berdi() yozadi, oldi() ni paket.oqi()/courses.oqi() avtomat yozadi ("unutmaydi").
X1 berdi<->oldi ni obyekt+hash bo'yicha tenglashtiradi."""
from . import konfig, jurnal, kontrakt


def yol(sana: str = None):
    sana = konfig.bugun(sana)
    return konfig.data("uzatish", f"{sana}.jsonl")


def _keyingi_id(kimdan: str, sana: str) -> str:
    """Shu kun, shu produtser bo'yicha berdi satrlar soni + 1."""
    satrlar = jurnal.oqi(yol(sana))
    n = sum(1 for s in satrlar if s.get("yonalish") == "berdi" and s.get("kimdan") == kimdan)
    return f"u-{sana}-{kimdan}-{n + 1:04d}"


def berdi(kimdan: str, obyekt: str, hash: str, tur: str = "fayl",
          kimga: str = "*", soni: dict = None, kutish_daq: int = None,
          sana: str = None) -> str:
    """Fayl/xabar berilganini yozadi. uzatish_id qaytaradi."""
    sana = konfig.bugun(sana)
    uid = _keyingi_id(kimdan, sana)
    satr = {
        "uzatish_id": uid,
        "vaqt": konfig.iso(),
        "yonalish": "berdi",
        "kimdan": kimdan,
        "kimga": kimga,
        "tur": tur,
        "obyekt": obyekt,
        "hash": hash,
        "soni": soni or {},
        "kutish_daq": kutish_daq,
    }
    kontrakt.tekshir("uzatish", satr)
    jurnal.append(yol(sana), satr)
    return uid


def oldi(kimga: str, obyekt: str, hash: str, tur: str = "fayl",
         soni: dict = None, sana: str = None) -> str:
    """Fayl o'qilganini yozadi. Mos berdi satridan uzatish_id/kimdan ni tiklaydi."""
    sana = konfig.bugun(sana)
    kimdan = kimga
    uid = f"u-{sana}-{kimga}-oldi"
    # obyekt bo'yicha oxirgi berdi ni topamiz
    for s in reversed(jurnal.oqi(yol(sana))):
        if s.get("yonalish") == "berdi" and s.get("obyekt") == obyekt:
            uid = s["uzatish_id"]
            kimdan = s["kimdan"]
            if soni is None:
                soni = s.get("soni")
            break
    satr = {
        "uzatish_id": uid,
        "vaqt": konfig.iso(),
        "yonalish": "oldi",
        "kimdan": kimdan,
        "kimga": kimga,
        "tur": tur,
        "obyekt": obyekt,
        "hash": hash,
        "soni": soni or {},
        "kutish_daq": None,
    }
    kontrakt.tekshir("uzatish", satr)
    jurnal.append(yol(sana), satr)
    return uid


def oqi(sana: str = None):
    return jurnal.oqi(yol(sana))
