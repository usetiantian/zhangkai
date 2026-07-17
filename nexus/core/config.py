"""Nexus 配置加载器"""
import json, os

DEFAULT_CONFIG = {
    "version": "1.0",
    "model": {"name": "qwen2-vl-2b-instruct", "auto_select": True, "quantization": "float16"},
    "learner": {"auto_learn": True, "lora_rank": 8, "dream_hour": 3},
    "memory": {"max_context_turns": 50, "auto_summary_threshold": 20},
    "recovery": {"max_retries": 5, "circuit_breaker_threshold": 5, "model_fallback_chain": ["4B","2B","rules"]},
}

def load_config(path: str = None) -> dict:
    path = path or os.path.join(os.path.dirname(__file__), "..", "nexus_config.json")
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
        _deep_merge(config, user)
    return config

def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
