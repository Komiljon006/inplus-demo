import os
import sys
from pathlib import Path

ILDIZ = Path(__file__).resolve().parents[1]
os.environ.setdefault("INPLUS_ILDIZ", str(ILDIZ))
os.environ.setdefault("INPLUS_REJIM", "mock")
sys.path.insert(0, str(ILDIZ / "lib"))
sys.path.insert(0, str(ILDIZ))  # `mock` (generator) importi uchun
