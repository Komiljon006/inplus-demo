"""SMS (ЕТС) adapteri. Mock — mock/ets_server.py ga HAQIQIY HTTP (retry/429/timeout
mockda ham sinaladi). Real — provayder aniqlangach 1 fayl (token/yubor/holat)."""
import abc
import json
import urllib.request
import urllib.error

from .. import konfig


class SmsEts(abc.ABC):
    @abc.abstractmethod
    def token(self) -> str:
        ...

    @abc.abstractmethod
    def yubor(self, telefon: str, matn: str, jonatuvchi: str = None) -> dict:
        """{'provayder_id': ..., 'holat': 'ok'|'xato', 'narx_som': int}"""

    @abc.abstractmethod
    def holat(self, provayder_id: str) -> dict:
        """{'holat': 'yetkazildi'|'yuborildi'|'xato'}"""


class MockSmsEts(SmsEts):
    def __init__(self):
        self.url = konfig.env("ETS_MOCK_URL", "http://127.0.0.1:8472")

    def _post(self, yol, payload, timeout=10):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url + yol, data=data,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), json.loads(r.read().decode("utf-8"))

    def token(self) -> str:
        return "mock-token"

    def yubor(self, telefon: str, matn: str, jonatuvchi: str = None) -> dict:
        try:
            kod, javob = self._post("/send", {"telefon": telefon, "matn": matn,
                                              "jonatuvchi": jonatuvchi or "INPLUS"})
        except urllib.error.HTTPError as e:
            return {"provayder_id": None, "holat": "xato", "narx_som": 0,
                    "http": e.code}
        return {"provayder_id": javob.get("message_id"), "holat": "ok",
                "narx_som": javob.get("narx_som", 95)}

    def holat(self, provayder_id: str) -> dict:
        try:
            kod, javob = self._post("/status", {"message_id": provayder_id})
        except urllib.error.HTTPError as e:
            return {"holat": "xato", "http": e.code}
        return {"holat": javob.get("holat", "yuborildi")}


class RealSmsEts(SmsEts):
    """ЕТС/Eskiz/Play Mobile — mijoz shartnomasi qaysi bo'lsa.
    XAVFSIZLIK: real rejim + ETS_TOKEN bo'lmasa RuntimeError (SMS adashib ketmasin)."""

    def __init__(self):
        if konfig.rejim() != "real" or not konfig.env_bor("ETS_TOKEN"):
            raise RuntimeError("RealSmsEts: INPLUS_REJIM=real VA ETS_TOKEN kerak")
        self.jonatuvchi = konfig.env("ETS_JONATUVCHI", "INPLUS")

    def token(self) -> str:
        raise NotImplementedError("RealSmsEts.token: provayder auth")

    def yubor(self, telefon: str, matn: str, jonatuvchi: str = None) -> dict:
        raise NotImplementedError("RealSmsEts.yubor: provayder send")

    def holat(self, provayder_id: str) -> dict:
        raise NotImplementedError("RealSmsEts.holat: provayder status")
