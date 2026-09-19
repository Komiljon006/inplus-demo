"""amoCRM adapteri. Mock — mock/amocrm/*.json ni REAL API JAVOB FORMATIDA qaytaradi
(shunda D1 normalizatsiyasi mock va realda bir xil sinaladi). Real — skelet."""
import abc
import json

from .. import konfig


class AmoCRM(abc.ABC):
    """Interfeys: lidlar(kundan), xodimlar(), bosqichlar()."""

    @abc.abstractmethod
    def lidlar(self, kundan: int = -90) -> dict:
        """amoCRM /api/v4/leads javob formati: {'_embedded': {'leads': [...]}}"""

    @abc.abstractmethod
    def xodimlar(self) -> dict:
        """/api/v4/users formati: {'_embedded': {'users': [...]}}"""

    @abc.abstractmethod
    def bosqichlar(self) -> dict:
        """/api/v4/leads/pipelines formati."""


class MockAmoCRM(AmoCRM):
    def __init__(self):
        self._baza = konfig.mock_yol("amocrm")

    def _oqi(self, nom):
        return json.loads((self._baza / nom).read_text(encoding="utf-8"))

    def lidlar(self, kundan: int = -90) -> dict:
        return self._oqi("leads.json")

    def xodimlar(self) -> dict:
        return self._oqi("users.json")

    def bosqichlar(self) -> dict:
        return self._oqi("pipelines.json")


class RealAmoCRM(AmoCRM):
    """OAuth2 long-lived token, GET /api/v4/leads?with=contacts, 250/sahifa, 7 req/s.
    Env: AMO_DOMEN, AMO_TOKEN. Maydon xaritasi mijoz akkauntida aniqlanadi."""

    def __init__(self):
        self.domen = konfig.env("AMO_DOMEN")
        self.token = konfig.env("AMO_TOKEN")
        if not (self.domen and self.token):
            raise RuntimeError("RealAmoCRM: AMO_DOMEN va AMO_TOKEN kerak")

    def lidlar(self, kundan: int = -90) -> dict:
        raise NotImplementedError("RealAmoCRM.lidlar: pagination + filter[updated_at]")

    def xodimlar(self) -> dict:
        raise NotImplementedError("RealAmoCRM.xodimlar")

    def bosqichlar(self) -> dict:
        raise NotImplementedError("RealAmoCRM.bosqichlar")
