#!/usr/bin/env python3
"""X0 — sinov agenti (kanareyka). 5 daqiqada bir ishga tushadi.
10% ehtimol bilan ataylab yiqiladi (X2 ni sinash), aks holda KPI+uzatish yozadi.
X2/X1/W1 ni haqiqiy agentlarsiz ham har kuni sinab turadi. Prodda ham qoladi.

Boshqarish:
  INPLUS_X0_YIQIL=1 -> doim yiqiladi;  =0 -> hech qachon; unset -> 10%
  INPLUS_X0_EHTIMOL=0.1
"""
import os
import sys
import time
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from inplus import konfig, uzatish, jurnal, fayl  # noqa: E402
from inplus.agent import Agent, ishga_tushir  # noqa: E402


class X0(Agent):
    agent_id = "X0"
    nom = "Sinov agenti"

    def ish(self) -> dict:
        majbur = os.environ.get("INPLUS_X0_YIQIL")
        ehtimol = float(os.environ.get("INPLUS_X0_EHTIMOL", "0.1"))
        yiqil = (majbur == "1") or (majbur != "0" and random.random() < ehtimol)
        if yiqil:
            raise RuntimeError("X0 ataylab yiqildi (sinov)")

        time.sleep(random.uniform(0, 1.0))  # demo: qisqa (prodda 1-20 s)
        satr = {"vaqt": konfig.iso(), "agent": "X0", "sinov": 1}
        p = konfig.data("sinov", f"{konfig.bugun(self.sana)}.jsonl")
        jurnal.append(p, satr)
        h = fayl.hash_matn(konfig.iso())
        uzatish.berdi("X0", f"data/sinov/{konfig.bugun(self.sana)}.jsonl", h,
                      tur="fayl", kimga="X1", soni={"sinov": 1}, sana=self.sana)
        return {"chiqdi": {"sinov": 1}, "kpi": {"sinov": 1}}


if __name__ == "__main__":
    sys.exit(ishga_tushir(X0))
