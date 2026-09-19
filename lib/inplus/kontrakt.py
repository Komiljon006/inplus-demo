"""Kontrakt validatsiyasi — jsonschema. tekshir() dan o'tmagan fayl yozilmaydi/o'qilmaydi."""
import json
import functools

try:
    import jsonschema
except ImportError:  # aniq xabar
    jsonschema = None

from . import konfig


class KontraktXato(Exception):
    """Schema tekshiruvidan o'tmagan obyekt."""


@functools.lru_cache(maxsize=None)
def _schema(nom: str) -> dict:
    p = konfig.kontrakt_yol(f"{nom}.schema.json")
    if not p.exists():
        raise KontraktXato(f"schema topilmadi: {nom} ({p})")
    return json.loads(p.read_text(encoding="utf-8"))


def tekshir(nom: str, obj) -> bool:
    """obj ni <nom>.schema.json bilan tekshiradi. Xato -> KontraktXato."""
    if jsonschema is None:
        raise KontraktXato("jsonschema o'rnatilmagan: pip install jsonschema")
    schema = _schema(nom)
    try:
        jsonschema.validate(instance=obj, schema=schema)
    except jsonschema.ValidationError as e:
        yol = "/".join(str(x) for x in e.absolute_path)
        raise KontraktXato(f"{nom}: {yol or '<root>'}: {e.message}") from None
    return True


def togrimi(nom: str, obj) -> bool:
    """Istisnosiz True/False."""
    try:
        return tekshir(nom, obj)
    except KontraktXato:
        return False
