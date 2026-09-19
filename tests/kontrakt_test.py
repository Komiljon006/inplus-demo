"""Har schema _ok namunani qabul qiladi, _xato ni rad etadi."""
import json
from pathlib import Path

import pytest

from inplus import kontrakt, konfig

SCHEMALAR = ["paket", "courses", "uzatish", "kpi", "heartbeat", "skript",
             "xabar", "insident"]


def _namuna(nom, tur):
    p = konfig.kontrakt_yol("namuna", f"{nom}_{tur}.json")
    return json.loads(Path(p).read_text(encoding="utf-8"))


@pytest.mark.parametrize("nom", SCHEMALAR)
def test_ok_namuna_qabul(nom):
    obj = _namuna(nom, "ok")
    assert kontrakt.tekshir(nom, obj) is True


@pytest.mark.parametrize("nom", SCHEMALAR)
def test_xato_namuna_rad(nom):
    obj = _namuna(nom, "xato")
    assert kontrakt.togrimi(nom, obj) is False
    with pytest.raises(kontrakt.KontraktXato):
        kontrakt.tekshir(nom, obj)


def test_har_schema_uchun_ikki_namuna_bor():
    for nom in SCHEMALAR:
        for tur in ("ok", "xato"):
            p = konfig.kontrakt_yol("namuna", f"{nom}_{tur}.json")
            assert Path(p).exists(), f"namuna yo'q: {nom}_{tur}"
