"""Jurnal: jsonl append + fcntl.flock (bir vaqtda ko'p yozuvchi xavfsiz)."""
import os
import json
import fcntl
from pathlib import Path

from . import konfig


def append(p, obj):
    """jsonl faylga bitta satr qo'shadi (flock bilan)."""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    satr = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with open(p, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(satr + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def oqi(p):
    """jsonl faylni ro'yxat qilib o'qiydi (bo'sh satrlar tashlanadi)."""
    p = Path(p)
    if not p.exists():
        return []
    natija = []
    for satr in p.read_text(encoding="utf-8").splitlines():
        satr = satr.strip()
        if satr:
            natija.append(json.loads(satr))
    return natija


def agent_log(agent_id: str, obj, sana: str = None):
    """data/jurnal/agent/<id>/<sana>.log — agent ishining JSON satrlari."""
    sana = konfig.bugun(sana)
    p = konfig.data("jurnal", "agent", agent_id, f"{sana}.log")
    append(p, obj)
