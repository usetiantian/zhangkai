"""
LoRA 训练引擎 — 微调 Qwen3-VL-4B

用知识库内容做微调数据，让模型更懂你的知识。
PEFT + QLoRA 4-bit，显存占用 ~5GB。

显存保护: 训练前检查 VRAM，不足则拒绝（不偷偷降级到 CPU）。
"""

import os, json, logging, torch, sys

logger = logging.getLogger("nexus_kb.lora")

# 训练显存估算（GB）
EST_BASE_MODEL_GB = 8     # Qwen3-VL-4B fp16
EST_PEFT_OVERHEAD_GB = 4  # LoRA params + gradients + optimizer states (Adam)
EST_ACTIVATION_GB = 4     # batch + gradient accumulation
EST_SAFE_TOTAL_GB = EST_BASE_MODEL_GB + EST_PEFT_OVERHEAD_GB + EST_ACTIVATION_GB  # ~16GB
MAX_TRAIN_TEXTS = 5000    # 单次训练最多文本数，防止 OOM


class LoRATrainer:
    """LoRA 微调 Qwen3-VL-4B。带显存保护。"""

    def __init__(self, adapter_dir: str = None):
        self.adapter_dir = adapter_dir or os.path.join(os.path.expanduser("~"), ".nexus_kb", "adapters")
        os.makedirs(self.adapter_dir, exist_ok=True)
        self.model = None
        self.processor = None
        self._peft_model = None

    def load(self):
        """复用已加载的 Qwen3-VL-4B。"""
        from ..engine.local_model import get_model
        m = get_model()
        if not m.is_loaded():
            m.load()
        self.model = m.model
        self.processor = m.processor
        logger.info("Using loaded Qwen3-VL-4B for LoRA")

    def prepare(self, r: int = 8, lora_alpha: int = 16):
        """应用 LoRA 到语言模型层。不动视觉编码器。"""
        if not self.model:
            self.load()

        from peft import LoraConfig, get_peft_model
        from peft.utils import TRANSFORMERS_MODELS_TO_LORA_TARGET_MODULES_MAPPING

        # Qwen3VL 的语言模型层
        target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

        self._peft_model = get_peft_model(self.model, LoraConfig(
            r=r, lora_alpha=lora_alpha, lora_dropout=0.05,
            target_modules=target_modules,
            bias="none",
            task_type="CAUSAL_LM",
        ))
        trainable = sum(p.numel() for p in self._peft_model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in self._peft_model.parameters())
        logger.info(f"LoRA applied: {trainable:,}/{total:,} params ({100*trainable/total:.2f}%)")

    def estimate_vram(self) -> dict:
        """估算训练所需显存。"""
        import torch
        if not torch.cuda.is_available():
            return {"cuda": False, "warning": "无 CUDA，训练不可行"}

        free = torch.cuda.mem_get_info()[0] / (1024**3)
        total = torch.cuda.mem_get_info()[1] / (1024**3)
        # 如果模型已加载，减掉已占用
        if self.model is not None and hasattr(self.model, 'device'):
            used = torch.cuda.memory_allocated() / (1024**3)
            available = free - max(0, used - EST_BASE_MODEL_GB)  # 粗略修正
        else:
            available = free

        ok = available >= EST_SAFE_TOTAL_GB
        return {
            "cuda": True,
            "total_gb": round(total, 1),
            "free_gb": round(free, 1),
            "available_for_training_gb": round(available, 1),
            "estimated_need_gb": EST_SAFE_TOTAL_GB,
            "ok": ok,
            "warning": None if ok else (
                f"显存不足以训练: 可用 {available:.1f}GB < 预估需要 {EST_SAFE_TOTAL_GB}GB。"
                f"请先卸载其他模型 (kb.model.unload()) 或减少训练数据量。"
            ),
        }

    def train(self, texts: list, epochs: int = 2, lr: float = 2e-4, force: bool = False):
        """用知识库文本微调。texts: 文档内容列表。force=True 跳过显存检查（危险）。"""
        if not texts:
            return False

        # 显存保护
        if not force:
            est = self.estimate_vram()
            if not est["ok"]:
                msg = est["warning"]
                logger.error(msg)
                sys.stderr.write(f"\n[VRAM GUARD] {msg}\n")
                sys.stderr.write("[VRAM GUARD] 拒绝训练，防止系统重启。\n")
                sys.stderr.flush()
                raise MemoryError(msg)

        # 数据量保护
        if len(texts) > MAX_TRAIN_TEXTS:
            sys.stderr.write(
                f"[TRAIN] {len(texts)} texts > {MAX_TRAIN_TEXTS} limit, "
                f"sampling to {MAX_TRAIN_TEXTS}\n"
            )
            sys.stderr.flush()
            import random
            texts = random.sample(texts, MAX_TRAIN_TEXTS)

        # 数据集内存估算
        est_dataset_mb = len(texts) * 512 * 3 * 4 / (1024 * 1024)  # 512 tokens × 3 tensors × 4 bytes
        if est_dataset_mb > 2048:  # >2GB 数据集告警
            sys.stderr.write(
                f"[TRAIN] Dataset ~{est_dataset_mb:.0f}MB in RAM, this is large but proceeding\n"
            )
            sys.stderr.flush()

        if not self._peft_model:
            self.prepare()

        from transformers import Trainer, TrainingArguments, DataCollatorForLanguageModeling
        from torch.utils.data import Dataset

        tokenizer = self.processor.tokenizer

        class KBDataset(Dataset):
            def __init__(self, texts, tok, max_len=512):
                self.data = []
                for t in texts:
                    encoded = tok(t[:2000], truncation=True, max_length=max_len,
                                  padding="max_length", return_tensors="pt")
                    self.data.append({
                        "input_ids": encoded["input_ids"][0],
                        "attention_mask": encoded["attention_mask"][0],
                        "labels": encoded["input_ids"][0],
                    })
            def __len__(self): return len(self.data)
            def __getitem__(self, i): return self.data[i]

        dataset = KBDataset(texts, tokenizer)
        data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

        trainer = Trainer(
            model=self._peft_model,
            args=TrainingArguments(
                output_dir=self.adapter_dir,
                num_train_epochs=epochs,
                per_device_train_batch_size=1,
                gradient_accumulation_steps=4,
                learning_rate=lr,
                logging_steps=10,
                save_strategy="no",
                report_to="none",
                remove_unused_columns=False,
            ),
            train_dataset=dataset,
            data_collator=data_collator,
        )
        logger.info(f"Training: {len(texts)} texts, {epochs} epochs")
        sys.stderr.write(f"[TRAIN] Starting: {len(texts)} texts, {epochs} epochs\n")
        sys.stderr.flush()
        trainer.train()
        self._peft_model.save_pretrained(self.adapter_dir)
        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(self.adapter_dir) for f in fs)
        logger.info(f"Adapter saved: {size/1024/1024:.1f}MB")
        sys.stderr.write(f"[TRAIN] Done. Adapter: {size/1024/1024:.1f}MB\n")
        sys.stderr.flush()

    def merge_and_save(self, output_path: str):
        """合并 LoRA 权重到模型，保存完整模型。"""
        if not self._peft_model:
            return
        merged = self._peft_model.merge_and_unload()
        merged.save_pretrained(output_path)
        self.processor.save_pretrained(output_path)
        logger.info(f"Merged model saved to {output_path}")
