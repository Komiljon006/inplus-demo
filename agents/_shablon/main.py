#!/usr/bin/env python3
"""SHABLON — yangi agent shu yerdan nusxalanadi.

Yangi agent qanday yoziladi:
  1. Bu papkani `agents/<id>/` ga nusxalang (masalan agents/n5_tabrik/).
  2. `agent_id` ni o'zgartiring (masalan "N5").
  3. `ish(self)` ni yozing — faqat shu. Skelet (heartbeat, KPI, uzatish,
     xatoni ushlash) `lib/inplus/agent.py` da tayyor.
  4. `konfig/agentlar.json` ga bitta yozuv qo'shing (X1/X2/W1 tegilmaydi).
  5. Bu papkaga `SOP.md` yozing (W1 uni wiki'ga oladi).

Qoidalar:
  - Manbaga faqat `adapter.ol(...)` orqali (requests TAQIQ).
  - Boshqa agent fayli faqat lib orqali (paket.oqi / courses.oqi — oldi avtomat).
  - Xabar faqat shlyuz_client.yubor(...) orqali, skript_id bilan.
  - ish() dict qaytaradi: {"kirdi": {...}, "chiqdi": {...}, "kpi": {...}}.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import adapter, paket, shlyuz_client  # noqa: E402,F401
from inplus.agent import Agent, ishga_tushir  # noqa: E402


class Shablon(Agent):
    agent_id = "SHABLON"
    nom = "Shablon agent"

    def ish(self) -> dict:
        # Namuna: joriy paketni o'qish (uzatish.oldi avtomat yoziladi)
        # p = paket.oqi(self.agent_id)
        # ... mantiq ...
        # shlyuz_client.yubor("SHABLON", "tg", {...}, "S-999", {...}, "kalit")
        return {"kirdi": {}, "chiqdi": {}, "kpi": {"bajarildi": 1}}


if __name__ == "__main__":
    sys.exit(ishga_tushir(Shablon))
