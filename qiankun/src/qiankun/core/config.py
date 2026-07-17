# 乾坤 (QianKun) — A 股 AI 研究助手
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODEL = "qwen/qwen3-vl-4b"

INITIAL_CAPITAL = 1_000_000
MAX_POSITIONS = 5
STOP_LOSS = -0.08
TAKE_PROFIT = 0.20
