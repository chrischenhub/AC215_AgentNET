from __future__ import annotations

import sys
from pathlib import Path


# Ensure the src/models directory is importable when running tests locally.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_PATH = PROJECT_ROOT / "src" / "models"
if str(MODELS_PATH) not in sys.path:
    sys.path.insert(0, str(MODELS_PATH))
