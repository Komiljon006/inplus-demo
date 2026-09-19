"""GetCourse adapteri. Mock — mock/getcourse/*.json REAL export JAVOB FORMATIDA.
Real — export ASINXRON (create -> export_id -> poll -> yuklash)."""
import abc
import json

from .. import konfig


class GetCourse(abc.ABC):
    @abc.abstractmethod
    def talabalar(self) -> dict:
        """export javob formati: {'success': true, 'info': {...}, 'data': {'fields': [...], 'rows': [...]}}"""

    @abc.abstractmethod
    def tolovlar(self, kundan: int = -30) -> dict:
        ...

    @abc.abstractmethod
    def guruhlar(self) -> dict:
        ...


class MockGetCourse(GetCourse):
    def __init__(self):
        self._baza = konfig.mock_yol("getcourse")

    def _oqi(self, nom):
        return json.loads((self._baza / nom).read_text(encoding="utf-8"))

    def talabalar(self) -> dict:
        return self._oqi("users.json")

    def tolovlar(self, kundan: int = -30) -> dict:
        return self._oqi("payments.json")

    def guruhlar(self) -> dict:
        return self._oqi("groups.json")


class RealGetCourse(GetCourse):
    """/pl/api/account/exports/... asinxron. Env: GC_DOMEN, GC_KALIT."""

    def __init__(self):
        self.domen = konfig.env("GC_DOMEN")
        self.kalit = konfig.env("GC_KALIT")
        if not (self.domen and self.kalit):
            raise RuntimeError("RealGetCourse: GC_DOMEN va GC_KALIT kerak")

    def talabalar(self) -> dict:
        raise NotImplementedError("RealGetCourse.talabalar: export create+poll+download")

    def tolovlar(self, kundan: int = -30) -> dict:
        raise NotImplementedError("RealGetCourse.tolovlar")

    def guruhlar(self) -> dict:
        raise NotImplementedError("RealGetCourse.guruhlar")
