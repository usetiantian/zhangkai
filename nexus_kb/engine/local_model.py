"""
本地模型引擎 — Qwen3-VL-4B (transformers fp16)
内置推理，零外部依赖。显存保护：加载前检查，不足则拒绝。
"""

import os, json, logging, torch, base64, sys
import numpy as np

logger = logging.getLogger("nexus_kb.model")

QWEN_MODEL_PATH = os.path.expanduser("~/.nexus/models/qwen3-vl-4b-instruct")
QWEN_FALLBACK = os.path.expanduser("~/.nexus/models/qwen2-vl-2b-instruct")

# 显存安全阈值（GB）
MIN_VRAM_FREE_GB = 10   # fp16 4B 模型 ~8GB + 推理开销 ~2GB
MIN_RAM_FREE_GB = 8     # 加载过程需要额外系统内存
LARGE_FILE_WARN_GB = 4  # 单个大文件超过此值告警


def check_vram(min_free_gb: float = MIN_VRAM_FREE_GB) -> dict:
    """检查显存是否充足。不足时返回告警信息，不阻止但强烈建议卸载。"""
    if not torch.cuda.is_available():
        return {"cuda": False, "warning": "没有 CUDA，将使用 CPU（极慢）"}
    free = torch.cuda.mem_get_info()[0] / (1024**3)
    total = torch.cuda.mem_get_info()[1] / (1024**3)
    ok = free >= min_free_gb
    return {
        "cuda": True,
        "total_gb": round(total, 1),
        "free_gb": round(free, 1),
        "min_required_gb": min_free_gb,
        "ok": ok,
        "warning": None if ok else (
            f"显存不足: 空闲 {free:.1f}GB < 需要 {min_free_gb}GB。"
            f"请先卸载其他模型或关闭 GPU 应用。"
        ),
    }


def check_ram(min_free_gb: float = MIN_RAM_FREE_GB) -> dict:
    """检查系统内存。"""
    import psutil
    mem = psutil.virtual_memory()
    free = mem.available / (1024**3)
    ok = free >= min_free_gb
    return {
        "free_gb": round(free, 1),
        "min_required_gb": min_free_gb,
        "ok": ok,
        "warning": None if ok else f"内存不足: 空闲 {free:.1f}GB < 需要 {min_free_gb}GB",
    }


class LocalModel:
    """知识库内置模型 — Qwen3-VL-4B，transformers 直载。带显存保护。"""

    def __init__(self, model_path: str = None):
        self.model_path = model_path or QWEN_MODEL_PATH
        self.model = None
        self.processor = None
        self._loaded = False

    def load(self, force: bool = False):
        """加载模型。force=True 跳过显存检查（危险）。"""
        if self._loaded:
            return

        # 显存保护
        if not force:
            vram = check_vram()
            if not vram["ok"]:
                msg = vram["warning"]
                logger.error(msg)
                sys.stderr.write(f"\n[VRAM GUARD] {msg}\n")
                sys.stderr.write("[VRAM GUARD] 拒绝加载模型，防止系统重启。\n")
                sys.stderr.write("[VRAM GUARD] 解决后重试，或调用 kb.model.unload() 释放后 load(force=True)。\n")
                sys.stderr.flush()
                raise MemoryError(msg)

            ram = check_ram()
            if not ram["ok"]:
                logger.warning(ram["warning"])
                sys.stderr.write(f"\n[RAM WARNING] {ram['warning']}（继续尝试，但可能很慢）\n")
                sys.stderr.flush()

        from transformers import Qwen3VLForConditionalGeneration, AutoProcessor

        logger.info(f"Loading Qwen3-VL-4B from {self.model_path}")
        sys.stderr.write(f"[model] Loading Qwen3-VL-4B (fp16)...\n")
        sys.stderr.flush()

        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            self.model_path,
            dtype=torch.float16,
            device_map="auto",
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
        self.processor = AutoProcessor.from_pretrained(
            self.model_path, trust_remote_code=True
        )
        self._loaded = True
        params = sum(p.numel() for p in self.model.parameters()) / 1e9

        # 加载后报告显存
        if torch.cuda.is_available():
            free_after = torch.cuda.mem_get_info()[0] / (1024**3)
            sys.stderr.write(f"[model] Loaded {params:.1f}B params, VRAM free: {free_after:.1f}GB\n")
            sys.stderr.flush()

        logger.info(f"Model loaded: {params:.1f}B params")

    def ask(self, prompt: str, system: str = "", images: list = None) -> str:
        """问答。images=[filepath,...] 时使用视觉能力。"""
        if not self._loaded:
            self.load()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        if images:
            content = []
            for img_path in images:
                try:
                    from PIL import Image
                    img = Image.open(img_path).convert("RGB")
                    content.append({"type": "image", "image": img})
                except Exception as e:
                    logger.warning(f"Image load failed {img_path}: {e}")
            content.append({"type": "text", "text": prompt})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(
            text=text, images=[c["image"] for c in messages[-1]["content"] if c.get("type") == "image"] if images else None,
            return_tensors="pt", padding=True
        ).to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs, max_new_tokens=4096, do_sample=False,
            )
        response = self.processor.decode(
            outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )
        return response.strip()

    def generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.3) -> str:
        """文本生成。"""
        if not self._loaded:
            self.load()

        messages = [{"role": "user", "content": prompt}]
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(
            text=[text], return_tensors="pt", padding=True
        ).to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs, max_new_tokens=max_tokens, temperature=temperature,
                do_sample=temperature > 0,
            )
        response = self.processor.decode(
            outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )
        return response.strip()

    def embed(self, text: str) -> list:
        """文本向量化 — last hidden state mean pooling。"""
        if not self._loaded:
            self.load()

        inputs = self.processor.tokenizer(
            text[:1000], return_tensors="pt", truncation=True, max_length=512
        ).to(self.model.device)

        with torch.no_grad():
            outputs = self.model(**inputs, output_hidden_states=True)
            last_hidden = outputs.hidden_states[-1]
            pooled = last_hidden.mean(dim=1).squeeze()
        return pooled.cpu().tolist()

    def describe_image(self, image_path: str, question: str = "描述这张图片的内容") -> str:
        """VL 模型描述图片内容。"""
        return self.ask(question, images=[image_path])

    def unload(self):
        if self.model:
            del self.model
            del self.processor
            torch.cuda.empty_cache()
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def get_embedding_dim(self) -> int:
        if not self._loaded:
            self.load()
        return self.model.config.hidden_size


_model: LocalModel = None


def get_model(model_path: str = None) -> LocalModel:
    global _model
    if _model is None:
        _model = LocalModel(model_path)
    return _model
