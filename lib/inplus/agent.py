"""Agent skeleti. Subklass faqat ish(self) -> dict yozadi.

run() tartibi (§1 qoida): heartbeat(boshladi) -> ish() -> kpi -> heartbeat(tugadi).
Xato bo'lsa: heartbeat(xato) + KPI(holat=xato) + qayta raise (YUTMAYDI) -> exit != 0.

ish() qaytaradigan dict ixtiyoriy `kirdi`, `chiqdi`, `kpi` kalitlariga ega bo'lishi mumkin.
Bo'lmasa — butun dict `kpi` deb olinadi."""
import sys
import time
import argparse
import traceback

from . import konfig, heartbeat, kpi as kpi_mod, jurnal


class Agent:
    agent_id = "AGENT"      # subklass o'zgartiradi
    nom = ""

    def __init__(self, sana: str = None):
        self.sana = konfig.bugun(sana)

    # --- subklass yozadi ---
    def ish(self) -> dict:
        raise NotImplementedError("ish() ni subklass yozadi")

    # --- skelet ---
    def _kpi_bol(self, natija: dict):
        if natija is None:
            natija = {}
        rez = ("kirdi" in natija) or ("chiqdi" in natija) or ("kpi" in natija)
        if rez:
            return natija.get("kirdi", {}), natija.get("chiqdi", {}), natija.get("kpi", {})
        return {}, {}, natija

    def run(self) -> dict:
        boshlandi = konfig.iso()
        t0 = time.monotonic()
        heartbeat.yoz(self.agent_id, "boshladi", boshlandi=boshlandi)
        jurnal.agent_log(self.agent_id, {"vaqt": boshlandi, "voqea": "boshladi",
                                         "sana": self.sana}, sana=self.sana)
        try:
            natija = self.ish()
        except Exception as e:
            dt = round(time.monotonic() - t0, 3)
            xato_matn = f"{type(e).__name__}: {e}"
            ish_yozuv = {
                "boshlandi": boshlandi, "tugadi": konfig.iso(), "davomiylik_s": dt,
                "holat": "xato", "xato_soni": 1, "xato_oxirgi": xato_matn,
                "kirdi": {}, "chiqdi": {}, "kpi": {},
            }
            try:
                kpi_mod.qosh(self.agent_id, ish_yozuv, sana=self.sana)
            finally:
                heartbeat.yoz(self.agent_id, "xato", boshlandi=boshlandi, xabar=xato_matn)
                jurnal.agent_log(self.agent_id, {"vaqt": konfig.iso(), "voqea": "xato",
                                                 "xato": xato_matn,
                                                 "trace": traceback.format_exc()},
                                 sana=self.sana)
            raise  # YUTMAYMIZ

        dt = round(time.monotonic() - t0, 3)
        kirdi, chiqdi, kpi_d = self._kpi_bol(natija)
        ish_yozuv = {
            "boshlandi": boshlandi, "tugadi": konfig.iso(), "davomiylik_s": dt,
            "holat": "ok", "xato_soni": 0, "xato_oxirgi": None,
            "kirdi": kirdi, "chiqdi": chiqdi, "kpi": kpi_d,
        }
        kpi_mod.qosh(self.agent_id, ish_yozuv, sana=self.sana)
        heartbeat.yoz(self.agent_id, "tugadi", boshlandi=boshlandi,
                      keyingi_kutilgan=None)
        jurnal.agent_log(self.agent_id, {"vaqt": konfig.iso(), "voqea": "tugadi",
                                         "davomiylik_s": dt, "kpi": kpi_d},
                         sana=self.sana)
        return ish_yozuv

    # --- CLI ---
    @classmethod
    def cli(cls, argv=None):
        p = argparse.ArgumentParser(description=cls.nom or cls.agent_id)
        p.add_argument("--bir-marta", action="store_true", help="bir marta ishga tushirish")
        p.add_argument("--sana", default=None, help="YYYY-MM-DD")
        p.add_argument("--rejim", default=None, choices=["mock", "real"])
        args = p.parse_args(argv)
        if args.rejim:
            import os
            os.environ["INPLUS_REJIM"] = args.rejim
        agent = cls(sana=args.sana)
        agent.run()
        return 0


def ishga_tushir(cls, argv=None) -> int:
    """CLI kirish nuqtasi — xatoda exit != 0."""
    try:
        return cls.cli(argv)
    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write(f"[{getattr(cls, 'agent_id', '?')}] XATO: "
                         f"{type(e).__name__}: {e}\n")
        return 1
