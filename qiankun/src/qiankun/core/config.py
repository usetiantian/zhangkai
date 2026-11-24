"""QianKun A-stock AI trading — config (2026-07-30: switch to MiniMax M3)."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# 2026-07-30: switched from LMStudio (qwen3-vl-4b) to MiniMax M3 (via mmx CLI).
# mmx auto-manages the API key, no need to store it here.
MINIMAX_MODEL = "MiniMax-M3"
MINIMAX_VISION_MODEL = None  # None = use mmx default

INITIAL_CAPITAL = 1_000_000
MAX_POSITIONS = 5
STOP_LOSS = -0.08
TAKE_PROFIT = 0.20
