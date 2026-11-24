"""External Model Provider v2 — DeepSeek 上下文缓存 + 128K 上下文窗口优化"""

import json, os, time, httpx
from dataclasses import dataclass, field
from enum import Enum


class ModelProvider(Enum):
    LOCAL = "local"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    CUSTOM = "custom"


@dataclass
class ModelConfig:
    """模型配置 — 含完整的 DeepSeek 参数"""
    name: str
    provider: ModelProvider
    model_id: str = ""
    api_key: str = ""
    api_base: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7

    # DeepSeek 特有配置
    context_window: int = 128000       # DeepSeek 支持 128K
    cache_enabled: bool = True         # 启用上下文硬盘缓存
    thinking_mode: bool = False        # 思考模式 (deepseek-r1)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "provider": self.provider.value,
            "model_id": self.model_id, "context_window": self.context_window,
            "cache_enabled": self.cache_enabled,
        }


class ExternalModelProviderV2:
    """
    外部模型提供者 v2 — DeepSeek 优化版.

    DeepSeek 特性:
    - 上下文硬盘缓存: 重复前缀自动命中, 输入 token 费用降至 10%
    - 128K 上下文窗口
    - 思考模式 (deepseek-reasoner)
    - 缓存命中追踪
    """

    def __init__(self):
        self._load_env_keys()
        self.cache_stats = {"hits": 0, "misses": 0, "total_calls": 0}
        # 保持 system prompt 稳定以最大化缓存命中
        self._cached_system_prompt: str = ""
        self._cached_prefix_hash: str = ""

    def _load_env_keys(self):
        """加载密钥 + 从 Nexus .env"""
        env_paths = ["C:/Users/87999/.nexus/.env", ".env"]
        for p in env_paths:
            try:
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and "=" in line and not line.startswith("#"):
                            k, v = line.split("=", 1)
                            if k.strip() not in os.environ:
                                os.environ[k.strip()] = v.strip()
            except FileNotFoundError:
                continue

        self.deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.deepseek_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        self.openai_key = os.environ.get("OPENAI_API_KEY", "")

    def chat(self, config: ModelConfig, messages: list[dict],
             system_prompt: str = "") -> dict:
        """
        调用外部模型 — 返回 {text, cache_hit, tokens_used, latency_ms}
        """
        self.cache_stats["total_calls"] += 1

        if config.provider == ModelProvider.OLLAMA:
            return self._call_ollama(config, messages, system_prompt)

        return self._call_deepseek(config, messages, system_prompt)

    def _call_deepseek(self, config: ModelConfig,
                       messages: list[dict],
                       system_prompt: str = "") -> dict:
        """调用 DeepSeek API — 含缓存追踪"""

        api_key = config.api_key or self.deepseek_key
        model_id = config.model_id or self.deepseek_model
        api_base = config.api_base or "https://api.deepseek.com"

        if not api_key:
            return {"text": "", "error": "未配置 DeepSeek API Key",
                    "cache_hit": False, "tokens_used": 0, "latency_ms": 0}

        # 构建消息 — system prompt 放在最前面以最大化缓存命中
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        for m in messages[-40:]:  # 128K 可以放更多
            msgs.append({
                "role": m.get("role", "user"),
                "content": m["content"][:4000],
            })

        # 缓存优化: system prompt 不变时, 整个前缀都会命中
        start = time.time()
        try:
            resp = httpx.post(
                f"{api_base}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "messages": msgs,
                    "max_tokens": config.max_tokens,
                    "temperature": config.temperature,
                    "stream": False,
                },
                timeout=120,
            )

            latency_ms = int((time.time() - start) * 1000)
            data = resp.json()

            # 检查缓存命中
            cache_hit = resp.headers.get("X-DS-Cache-Hit", "").lower() == "true"

            if cache_hit:
                self.cache_stats["hits"] += 1
            else:
                self.cache_stats["misses"] += 1

            if "choices" in data and data["choices"]:
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return {
                    "text": text,
                    "cache_hit": cache_hit,
                    "tokens_used": usage.get("total_tokens", 0),
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "cached_tokens": usage.get("prompt_tokens_details", {}).get("cached_tokens", 0),
                    "latency_ms": latency_ms,
                }

            if "error" in data:
                return {
                    "text": f"API 错误: {data['error'].get('message', str(data['error']))}",
                    "error": data["error"].get("message", ""),
                    "cache_hit": False,
                    "tokens_used": 0,
                    "latency_ms": latency_ms,
                }

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            return {
                "text": f"API 调用失败: {e}",
                "error": str(e),
                "cache_hit": False,
                "tokens_used": 0,
                "latency_ms": latency_ms,
            }

        return {"text": "无响应", "cache_hit": False,
                "tokens_used": 0, "latency_ms": 0}

    def _call_ollama(self, config: ModelConfig,
                     messages: list[dict],
                     system_prompt: str = "") -> dict:
        try:
            import ollama
            msgs = []
            if system_prompt:
                msgs.append({"role": "system", "content": system_prompt})
            for m in messages[-20:]:
                msgs.append({"role": m.get("role", "user"),
                             "content": m["content"][:2000]})
            start = time.time()
            response = ollama.chat(
                model=config.model_id, messages=msgs,
                options={"temperature": config.temperature},
            )
            latency_ms = int((time.time() - start) * 1000)
            return {
                "text": response["message"]["content"],
                "cache_hit": False,
                "tokens_used": response.get("eval_count", 0),
                "latency_ms": latency_ms,
            }
        except Exception as e:
            return {"text": f"Ollama 失败: {e}", "error": str(e),
                    "cache_hit": False, "tokens_used": 0, "latency_ms": 0}

    def get_cache_stats(self) -> dict:
        """缓存统计"""
        total = self.cache_stats["total_calls"]
        hit_rate = (self.cache_stats["hits"] / total * 100
                     if total > 0 else 0)
        return {
            **self.cache_stats,
            "hit_rate_pct": round(hit_rate, 1),
            "cost_saved": (f"{self.cache_stats['hits'] * 90}% 输入费用节省"
                           if self.cache_stats["hits"] > 0 else "0"),
        }
