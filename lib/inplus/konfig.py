"""Konfig: env o'qish, ildiz yo'llari, vaqt (Asia/Tashkent). Hardcode yo'q."""
import os
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Asia/Tashkent — doim +05:00, DST yo'q
TASHKENT = timezone(timedelta(hours=5), name="Asia/Tashkent")


def _env_fayldan_yukla():
    """konfig/inplus.env ni o'qib, hali o'rnatilmagan env'larni to'ldiradi."""
    ildiz = _ildiz_top()
    env_fayl = ildiz / "konfig" / "inplus.env"
    if not env_fayl.exists():
        return
    for satr in env_fayl.read_text(encoding="utf-8").splitlines():
        satr = satr.strip()
        if not satr or satr.startswith("#") or "=" not in satr:
            continue
        kalit, _, qiymat = satr.partition("=")
        kalit = kalit.strip()
        qiymat = qiymat.strip()
        if kalit and kalit not in os.environ:
            os.environ[kalit] = qiymat


def _ildiz_top() -> Path:
    """INPLUS_ILDIZ env, aks holda shu fayldan yuqoriga (lib/inplus/.. /..)."""
    e = os.environ.get("INPLUS_ILDIZ")
    if e:
        return Path(e).expanduser().resolve()
    # lib/inplus/konfig.py -> ildiz
    return Path(__file__).resolve().parents[2]


ILDIZ = _ildiz_top()
_env_fayldan_yukla()
ILDIZ = _ildiz_top()  # env fayl INPLUS_ILDIZ ni bergan bo'lishi mumkin


def rejim() -> str:
    return os.environ.get("INPLUS_REJIM", "mock").strip().lower()


def env(nom: str, standart: str = "") -> str:
    return os.environ.get(nom, standart)


def env_bor(nom: str) -> bool:
    return bool(os.environ.get(nom, "").strip())


def hozir() -> datetime:
    """Asia/Tashkent aware datetime. utcnow() TAQIQ."""
    return datetime.now(TASHKENT)


def iso(dt: datetime = None) -> str:
    if dt is None:
        dt = hozir()
    return dt.isoformat(timespec="seconds")


def bugun(sana: str = None) -> str:
    if sana:
        return sana
    return hozir().strftime("%Y-%m-%d")


# --- yo'l yordamchilari ---
def yol(*qismlar) -> Path:
    return ILDIZ.joinpath(*qismlar)


def data(*qismlar) -> Path:
    return ILDIZ.joinpath("data", *qismlar)


def konfig_yol(*qismlar) -> Path:
    return ILDIZ.joinpath("konfig", *qismlar)


def kontrakt_yol(*qismlar) -> Path:
    return ILDIZ.joinpath("kontrakt", *qismlar)


def run_yol(*qismlar) -> Path:
    return ILDIZ.joinpath("run", *qismlar)


def mock_yol(*qismlar) -> Path:
    return ILDIZ.joinpath("mock", *qismlar)


def konfig_json(nom: str) -> dict:
    """konfig/<nom> ni o'qiydi."""
    p = konfig_yol(nom)
    return json.loads(p.read_text(encoding="utf-8"))


def shlyuz_url() -> str:
    port = os.environ.get("INPLUS_SHLYUZ_PORT", "8471")
    return f"http://127.0.0.1:{port}"
