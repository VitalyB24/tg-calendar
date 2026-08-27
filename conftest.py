"""Puts the repository root on sys.path so `import tg_calendar` works however
pytest is invoked (a bare `pytest` does not add the rootdir by itself)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
