"""Model Switching — 会话中热切换模型"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModelEntry:
    """一个可用模型"""
    name: str
    path: str
    type: str = "vl"  # vl / text / gguf
    loaded: bool = False
    description: str = ""


AVAILABLE_MODELS = {
    "qwen3-thinking": ModelEntry(
        name="qwen3-thinking",
        path="D:/qiankun/models/qwen3-vl-2b-thinking",
        type="vl",
        description="Qwen3-VL-2B-Thinking — 带推理链，决策质量高，较慢",
    ),
    "qwen2": ModelEntry(
        name="qwen2",
        path="C:/Users/87999/.nexus/models/qwen2-vl-2b-instruct",
        type="vl",
        description="Qwen2-VL-2B — 快速响应，适合简单对话",
    ),
    "qwen3-4b-gguf": ModelEntry(
        name="qwen3-4b-gguf",
        path="C:/Users/87999/.nexus/models/qwen3-vl-4b-gguf/Qwen3-VL-4B-Instruct-Q4_K_M.gguf",
        type="gguf",
        description="Qwen3-VL-4B Q4 GGUF — 更大参数量，需 Ollama",
    ),
}


@dataclass
class ModelSwitch:
    """模型切换管理器"""

    current: str = "qwen3-thinking"

    def switch(self, model_name: str) -> dict:
        """切换模型"""
        if model_name not in AVAILABLE_MODELS:
            return {"ok": False, "error": f"未知模型: {model_name}",
                    "available": list(AVAILABLE_MODELS.keys())}

        entry = AVAILABLE_MODELS[model_name]
        if not Path(entry.path).exists():
            return {"ok": False, "error": f"模型文件不存在: {entry.path}"}

        old = self.current
        self.current = model_name

        # 重新加载
        from coordinator.engine import reload_model
        reload_model(entry.path)

        return {
            "ok": True,
            "switched_from": old,
            "switched_to": model_name,
            "description": entry.description,
        }

    def list_models(self) -> list[dict]:
        """列出可用模型"""
        result = []
        for name, entry in AVAILABLE_MODELS.items():
            exists = Path(entry.path).exists()
            result.append({
                "name": name,
                "description": entry.description,
                "available": exists,
                "current": name == self.current,
            })
        return result


# 全局单例
_model_switch: ModelSwitch | None = None


def get_model_switch() -> ModelSwitch:
    global _model_switch
    if _model_switch is None:
        _model_switch = ModelSwitch()
    return _model_switch
