"""Shlyuz mijozi: yagona xabar chiqish nuqtasi. Bevosita telegram/sms TAQIQ.
Shlyuz yo'q bo'lsa — jurnalga `shlyuz_yoq`, agent YIQILMAYDI."""
import json
import urllib.request
import urllib.error

from . import konfig, jurnal


class ShlyuzYoq(Exception):
    pass


def yubor(kimdan_agent: str, kanal: str, kimga: dict, skript_id: str,
          ozgaruvchilar: dict, idempotent_kalit: str, til: str = "uz",
          muhimlik: str = "oddiy", timeout: float = 5.0) -> dict:
    """POST /yubor. Javob dict qaytaradi yoki shlyuz yo'q bo'lsa {'holat':'shlyuz_yoq'}."""
    sorov = {
        "kimdan_agent": kimdan_agent,
        "kanal": kanal,
        "kimga": kimga,
        "skript_id": skript_id,
        "til": til,
        "ozgaruvchilar": ozgaruvchilar,
        "idempotent_kalit": idempotent_kalit,
        "muhimlik": muhimlik,
    }
    data = json.dumps(sorov, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        konfig.shlyuz_url() + "/yubor",
        data=data,
        headers={"Content-Type": "application/json",
                 "X-Idempotency-Key": idempotent_kalit},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Shlyuz javob berdi lekin xato kod — javobni qaytaramiz
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"holat": "xato", "sabab": f"HTTP {e.code}"}
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        # Shlyuz yo'q — yiqitmaymiz, jurnalga yozamiz
        jurnal.agent_log(kimdan_agent, {
            "vaqt": konfig.iso(), "voqea": "shlyuz_yoq",
            "skript_id": skript_id, "kanal": kanal, "sabab": str(e),
        })
        return {"holat": "shlyuz_yoq", "sabab": str(e)}
