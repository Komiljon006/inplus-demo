"""Fayl: atomik yozish (tmp -> os.replace), symlink, json o'qi/yoz, hash."""
import os
import json
import hashlib
import tempfile
from pathlib import Path


def kanonik_json(obj) -> str:
    """Deterministik JSON (hash uchun)."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_obj(obj) -> str:
    h = hashlib.sha256(kanonik_json(obj).encode("utf-8")).hexdigest()
    return "sha256:" + h[:12]


def hash_matn(matn: str) -> str:
    return "sha256:" + hashlib.sha256(matn.encode("utf-8")).hexdigest()[:12]


def _katalog(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)


def yoz(p, matn: str):
    """Atomik yozish: tmp -> os.replace (bir xil FS)."""
    p = Path(p)
    _katalog(p)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".tmp_", suffix=".sw")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(matn)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def json_yoz(p, obj):
    yoz(p, json.dumps(obj, ensure_ascii=False, indent=2))


def json_oqi(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def symlink(nishon, havola):
    """havola -> nishon symlink (atomik almashtirish)."""
    nishon = Path(nishon)
    havola = Path(havola)
    _katalog(havola)
    tmp = havola.with_name(havola.name + ".symtmp")
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    # nishon nisbatan (bir katalog ichida bo'lsa faqat nom)
    try:
        rel = os.path.relpath(nishon, havola.parent)
    except ValueError:
        rel = str(nishon)
    os.symlink(rel, tmp)
    os.replace(tmp, havola)
