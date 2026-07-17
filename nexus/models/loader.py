"""
模型加载器 — 纯Python transformers直接加载
借鉴: LlamaFactory的量化管理+模型注册模式
支持: 自动检测显卡选2B/4B，4-bit量化加载
"""
import os, logging
logger = logging.getLogger("nexus.models")

class ModelLoader:
    """Qwen模型加载器。借鉴LlamaFactory的AutoModel模式。"""

    def __init__(self, models_dir: str = None):
        self.models_dir = models_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "..", ".nexus", "models"
        )
        self.current_model = None
        self.current_size = None
        self.model = None
        self.tokenizer = None

    def detect_gpu_memory(self) -> int:
        """检测可用显存(GB)。"""
        try:
            import torch
            if torch.cuda.is_available():
                total = torch.cuda.get_device_properties(0).total_mem
                return total // (1024**3)
        except Exception:
            pass
        return 0

    def auto_select(self) -> str:
        """根据显存自动选模型。"""
        mem = self.detect_gpu_memory()
        if mem >= 10:
            return "qwen2-vl-4b-instruct"
        elif mem >= 8:
            return "qwen2-vl-2b-instruct"
        return "qwen2-vl-2b-instruct"  # CPU fallback

    def load(self, model_name: str = None):
        """
        加载模型。借鉴LlamaFactory的 from_pretrained + load_in_4bit。
        """
        model_name = model_name or self.auto_select()
        model_path = os.path.join(self.models_dir, model_name)

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"模型未找到: {model_path}\n"
                f"请下载: huggingface-cli download Qwen/{model_name}"
            )

        import torch
        from transformers import (
            Qwen2VLForConditionalGeneration,
            AutoTokenizer,
            AutoProcessor
        )

        logger.info(f"Loading {model_name} from {model_path}")

        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_path,
            dtype=torch.float16,
            device_map="auto",
            low_cpu_mem_usage=True,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.processor = AutoProcessor.from_pretrained(model_path)

        self.current_model = model_name
        self.current_size = self._get_param_count()
        logger.info(f"Loaded {self.current_size}B model")

    def _get_param_count(self) -> float:
        """估算参数量(十亿)。"""
        if not self.model:
            return 0
        total = sum(p.numel() for p in self.model.parameters())
        return round(total / 1e9, 1)

    def generate(self, prompt: str, max_tokens=256) -> str:
        """推理——借鉴Qwen2-VL的生成接口。"""
        if not self.model:
            raise RuntimeError("Model not loaded. Call load() first.")

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(**inputs, max_new_tokens=max_tokens)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    def hot_swap(self, new_model_name: str):
        """热切换模型——卸载旧模型，加载新模型。"""
        logger.info(f"Hot-swap: {self.current_model} -> {new_model_name}")
        self.unload()
        self.load(new_model_name)

    def unload(self):
        """卸载模型释放显存。"""
        if self.model:
            del self.model
            del self.tokenizer
            del self.processor
            import torch
            torch.cuda.empty_cache()
        self.model = None
        self.current_model = None

    def status(self) -> dict:
        return {
            "loaded": self.current_model is not None,
            "model": self.current_model,
            "size": f"{self.current_size}B" if self.current_size else None,
            "gpu_memory_gb": self.detect_gpu_memory(),
        }
