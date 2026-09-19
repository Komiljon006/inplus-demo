"""Telegram adapteri. Mock — data/jurnal/xabar/mock_tg/<sana>.jsonl ga yozadi.
Real — sendMessage (requests). Bot faqat /start bosganga yozadi."""
import abc
import itertools

from .. import konfig, jurnal


class Telegram(abc.ABC):
    @abc.abstractmethod
    def yubor(self, chat_id, matn: str) -> dict:
        """{'provayder_id': message_id, 'holat': 'ok'|'xato', 'sabab': ...}"""

    @abc.abstractmethod
    def yangiliklar(self) -> list:
        """getUpdates — /start bosganlar (opt-in)."""


_hisoblagich = itertools.count(1)


class MockTelegram(Telegram):
    def yubor(self, chat_id, matn: str) -> dict:
        n = next(_hisoblagich)
        pid = f"mock-tg-{n}"
        jurnal.append(
            konfig.data("jurnal", "xabar", "mock_tg", f"{konfig.bugun()}.jsonl"),
            {"vaqt": konfig.iso(), "chat_id": chat_id, "matn": matn, "provayder_id": pid},
        )
        return {"provayder_id": pid, "holat": "ok"}

    def yangiliklar(self) -> list:
        return []


class RealTelegram(Telegram):
    """sendMessage. Env: TG_BOT_TOKEN. 429 -> retry_after; 400 chat not found -> xato."""

    def __init__(self):
        self.token = konfig.env("TG_BOT_TOKEN")
        if not self.token:
            raise RuntimeError("RealTelegram: TG_BOT_TOKEN kerak")

    def _api(self, metod):
        return f"https://api.telegram.org/bot{self.token}/{metod}"

    def yubor(self, chat_id, matn: str) -> dict:
        import requests  # faqat real yo'lda import
        r = requests.post(self._api("sendMessage"),
                          json={"chat_id": chat_id, "text": matn}, timeout=10)
        if r.status_code == 200:
            mid = r.json().get("result", {}).get("message_id")
            return {"provayder_id": mid, "holat": "ok"}
        if r.status_code == 429:
            retry = r.json().get("parameters", {}).get("retry_after", 1)
            return {"provayder_id": None, "holat": "kechiktir", "retry_after": retry}
        return {"provayder_id": None, "holat": "xato", "sabab": r.text[:200]}

    def yangiliklar(self) -> list:
        import requests
        r = requests.get(self._api("getUpdates"), timeout=65)
        return r.json().get("result", []) if r.status_code == 200 else []
