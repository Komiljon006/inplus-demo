"""Google Sheets adapteri. Mock — mock/sheets/jadval.csv. Real — Sheets API v4."""
import abc
import csv

from .. import konfig


class Sheets(abc.ABC):
    @abc.abstractmethod
    def varaq(self, sheet_id: str, nom: str) -> list:
        """2D ro'yxat (list[list[str]]) — sarlavha + qatorlar."""


class MockSheets(Sheets):
    def __init__(self):
        self._fayl = konfig.mock_yol("sheets", "jadval.csv")

    def varaq(self, sheet_id: str = None, nom: str = "Jadval") -> list:
        with open(self._fayl, encoding="utf-8") as f:
            return [qator for qator in csv.reader(f)]


class RealSheets(Sheets):
    """Sheets API v4 values.get, service account. Env: SHEETS_ID, SHEETS_SA_FAYL."""

    def __init__(self):
        self.sheet_id = konfig.env("SHEETS_ID")
        self.sa_fayl = konfig.env("SHEETS_SA_FAYL")
        if not (self.sheet_id and self.sa_fayl):
            raise RuntimeError("RealSheets: SHEETS_ID va SHEETS_SA_FAYL kerak")

    def varaq(self, sheet_id: str, nom: str) -> list:
        raise NotImplementedError("RealSheets.varaq: Sheets API v4 values.get")
