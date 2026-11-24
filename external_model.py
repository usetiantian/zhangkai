"""External Model Provider — 支持 OpenAI / DeepSeek / 本地 Ollama 等外部模型"""

import json, os, httpx
from dataclasses import dataclass, field
from enum import Enum


class ModelProvider(Enum):
    LOCAL = "local"          # transformers 本地加载
    OPENAI = "openai"        # OpenAI API
    DEEPSEEK = "deepseek"    # DeepSeek API
    OLLAMA = "ollama"        # 本地 Ollama
    CUSTOM = "custom"        # 自定义 OpenAI 兼容 API


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    provider: ModelProvider
    model_id: str = ""          # API 模型名, e.g. "gpt-4o", "deepseek-chat"
    api_key: str = ""
    api_base: str = ""          # 自定义 API 地址
    max_tokens: int = 4096
    temperature: float = 0.7
    local_path: str = ""        # 本地模型路径

    def to_dict(self) -> dict:
        return {
            "name": self.name, "provider": self.provider.value,
            "model_id": self.model_id, "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }


class ExternalModelProvider:
    """
    外部模型提供者.
    支持 OpenAI / DeepSeek / Ollama / 自定义 API.
    """

    def __init__(self):
        self._load_env_keys()

    def _load_env_keys(self):
        """从环境变量加载 API 密钥"""
        self.openai_key = os.environ.get("OPENAI_API_KEY", "")
        self.deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.openai_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
        self.deepseek_base = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")

    def chat(self, config: ModelConfig, messages: list[dict],
             system_prompt: str = "") -> str:
        """调用外部模型"""

        if config.provider == ModelProvider.OLLAMA:
            return self._call_ollama(config, messages, system_prompt)

        # OpenAI 兼容 API (OpenAI / DeepSeek / Custom)
        return self._call_openai_compatible(config, messages, system_prompt)

    def _call_openai_compatible(self, config: ModelConfig,
                                 messages: list[dict],
                                 system_prompt: str = "") -> str:
        """调用 OpenAI 兼容 API"""
        api_key = config.api_key or {
            ModelProvider.OPENAI: self.openai_key,
            ModelProvider.DEEPSEEK: self.deepseek_key,
        }.get(config.provider, "")

        api_base = config.api_base or {
            ModelProvider.OPENAI: self.openai_base,
            ModelProvider.DEEPSEEK: self.deepseek_base,
        }.get(config.provider, "https://api.openai.com/v1")

        if not api_key:
            return json.dumps({
                "action": "reply",
                "answer": f"未配置 {config.provider.value} API Key。"
                          f"请设置环境变量。",
            }, ensure_ascii=False)

        # 构建消息
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        for m in messages[-20:]:  # 最近 20 条
            role = m.get("role", "user")
            if role == "assistant":
                msgs.append({"role": "assistant", "content": m["content"][:2000]})
            elif role == "user":
                msgs.append({"role": "user", "content": m["content"][:2000]})

        try:
            resp = httpx.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.model_id,
                    "messages": msgs,
                    "max_tokens": config.max_tokens,
                    "temperature": config.temperature,
                },
                timeout=60,
            )
            data = resp.json()

            if "choices" in data and data["choices"]:
                return data["choices"][0]["message"]["content"]
            elif "error" in data:
                return json.dumps({
                    "action": "reply",
                    "answer": f"API 错误: {data['error'].get('message', str(data['error']))}",
                }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "action": "reply",
                "answer": f"API 调用失败: {e}",
            }, ensure_ascii=False)

        return json.dumps({"action": "reply", "answer": "无响应"},
                          ensure_ascii=False)

    def _call_ollama(self, config: ModelConfig,
                     messages: list[dict],
                     system_prompt: str = "") -> str:
        """调用本地 Ollama"""
        try:
            import ollama
            msgs = []
            if system_prompt:
                msgs.append({"role": "system", "content": system_prompt})
            for m in messages[-20:]:
                msgs.append({"role": m.get("role", "user"),
                             "content": m["content"][:2000]})

            response = ollama.chat(
                model=config.model_id,
                messages=msgs,
                options={"temperature": config.temperature},
            )
            return response["message"]["content"]
        except Exception as e:
            return json.dumps({
                "action": "reply",
                "answer": f"Ollama 调用失败: {e}",
            }, ensure_ascii=False)


# 内置外部模型配置
BUILTIN_EXTERNAL_MODELS = {
    "deepseek-v3": ModelConfig(
        name="deepseek-v3",
        provider=ModelProvider.DEEPSEEK,
        model_id="deepseek-chat",
        max_tokens=4096,
        temperature=0.7,
    ),
    "deepseek-r1": ModelConfig(
        name="deepseek-r1",
        provider=ModelProvider.DEEPSEEK,
        model_id="deepseek-reasoner",
        max_tokens=8192,
        temperature=0.3,
    ),
    "gpt-4o": ModelConfig(
        name="gpt-4o",
        provider=ModelProvider.OPENAI,
        model_id="gpt-4o",
        max_tokens=4096,
        temperature=0.7,
    ),
    "gpt-4o-mini": ModelConfig(
        name="gpt-4o-mini",
        provider=ModelProvider.OPENAI,
        model_id="gpt-4o-mini",
        max_tokens=4096,
        temperature=0.7,
    ),
    "ollama-local": ModelConfig(
        name="ollama-local",
        provider=ModelProvider.OLLAMA,
        model_id="qiankun:4b",
        max_tokens=4096,
        temperature=0.7,
    ),
}


def get_external_model(name: str) -> ModelConfig | None:
    """获取外部模型配置"""
    if name in BUILTIN_EXTERNAL_MODELS:
        return BUILTIN_EXTERNAL_MODELS[name]
    return None


def list_external_models() -> list[dict]:
    """列出所有可用外部模型"""
    return [
        {
            "name": cfg.name,
            "provider": cfg.provider.value,
            "model_id": cfg.model_id,
            "available": bool(
                cfg.provider == ModelProvider.OLLAMA
                or os.environ.get(f"{cfg.provider.value.upper()}_API_KEY")
            ),
        }
        for cfg in BUILTIN_EXTERNAL_MODELS.values()
    ]
