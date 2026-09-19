"""Adapter fabrikasi: ol(nom) rejimga qarab Mock*/Real* qaytaradi.
Agent kodi rejimni bilmaydi. TG uchun TG_REAL=1 kanal override (§N2)."""
from .. import konfig
from . import amocrm, getcourse, sheets, sms_ets, telegram

_XARITA = {
    "amocrm": (amocrm.MockAmoCRM, amocrm.RealAmoCRM),
    "getcourse": (getcourse.MockGetCourse, getcourse.RealGetCourse),
    "sheets": (sheets.MockSheets, sheets.RealSheets),
    "sms": (sms_ets.MockSmsEts, sms_ets.RealSmsEts),
    "telegram": (telegram.MockTelegram, telegram.RealTelegram),
}


def ol(nom: str):
    """nom: amocrm|getcourse|sheets|sms|telegram."""
    if nom not in _XARITA:
        raise KeyError(f"noma'lum adapter: {nom}")
    mock_cls, real_cls = _XARITA[nom]
    real = konfig.rejim() == "real"
    # Telegram uchun kanal darajasidagi override: TG_REAL=1
    if nom == "telegram" and konfig.env("TG_REAL", "0") == "1":
        real = True
    return real_cls() if real else mock_cls()
