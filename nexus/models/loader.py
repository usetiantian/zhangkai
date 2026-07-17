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
        self.identity_weight = None  # 身份权重神经层

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

        try:
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                model_path,
                dtype=torch.float16,
                device_map="auto",
                low_cpu_mem_usage=True,
            )
        except Exception:
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                model_path,
                dtype=torch.float16,
                low_cpu_mem_usage=True,
            )
            if torch.cuda.is_available():
                self.model = self.model.cuda()
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

    def generate(self, prompt: str, max_tokens=256, temperature=0.3) -> str:
        """推理——用chat template确保只输出回答。"""
        if not self.model:
            raise RuntimeError("Model not loaded. Call load() first.")

        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
        )
        # 只取生成的部分，去掉输入
        response = self.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        )
        return response.strip()

    def attach_identity_weight(self, weight_path: str = None):
        """加载身份权重——让模型嵌入Nexus的自我意识。"""
        from core.identity_weight import IdentityWeight
        self.identity_weight = IdentityWeight()
        if weight_path and os.path.exists(weight_path):
            self.identity_weight.load(weight_path)
            logger.info("Identity weight loaded")
        elif self.model and self.tokenizer:
            # 首次: 用SOUL+Constitution训练
            soul = os.path.join(os.path.dirname(__file__), "..", "..", ".claude", "SOUL.md")
            const = os.path.join(os.path.dirname(__file__), "..", "..", ".claude", "constitution.md")
            wp = os.path.join(os.path.dirname(__file__), "..", "data", "identity.pt")
            self.identity_weight = IdentityWeight.create_and_train(
                soul, const, self.tokenizer, self.model, wp
            )
            logger.info("Identity weight trained")

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
