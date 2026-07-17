"""
LoRA 训练引擎 — 借鉴LlamaFactory的PEFT+QLoRA设计
纯Python实现，用于Nexus的用户个性化微调
"""
import os, json, logging, torch
logger = logging.getLogger("nexus.lora")

class LoRATrainer:
    """
    LoRA训练器——借鉴LlamaFactory的PEFT管线。
    每个用户一个adapter，~200MB，只训这个小层。
    """

    def __init__(self, base_model_path: str, adapter_dir: str = None):
        self.base_model_path = base_model_path
        self.adapter_dir = adapter_dir or os.path.join(
            os.path.dirname(__file__), "..", "data", "lora_adapters"
        )
        os.makedirs(self.adapter_dir, exist_ok=True)
        self.model = None
        self.tokenizer = None
        self.peft_config = None

    def load_base_model(self):
        """加载基座模型——借鉴LlamaFactory的load_model。"""
        from transformers import (
            Qwen2VLForConditionalGeneration,
            AutoTokenizer,
        )
        logger.info(f"Loading base model: {self.base_model_path}")
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            self.base_model_path,
            dtype=torch.float16,
            device_map="auto",
            low_cpu_mem_usage=True,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_path)
        logger.info("Base model loaded")

    def prepare_lora(self):
        """准备LoRA配置——借鉴LlamaFactory的FinetuningArguments。"""
        from peft import LoraConfig, get_peft_model, TaskType

        self.peft_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=8,              # LoRA rank
            lora_alpha=16,
            lora_dropout=0.05,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        )
        self.model = get_peft_model(self.model, self.peft_config)
        trainable = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in self.model.parameters())
        logger.info(f"LoRA ready: {trainable:,} trainable / {total:,} total ({trainable/total*100:.1f}%)")

    def train_on_conversations(self, conversations: list, user_id: str, epochs: int = 3):
        """
        在用户对话上训练LoRA。
        conversations: [(user_msg, nexus_reply), ...]
        """
        from transformers import Trainer, TrainingArguments
        from torch.utils.data import Dataset

        class ConvDataset(Dataset):
            def __init__(self, convs, tokenizer, max_len=256):
                self.data = []
                for user, reply in convs:
                    text = f"用户: {user}\nNexus: {reply}"
                    tokens = tokenizer(text, truncation=True, max_length=max_len, return_tensors="pt")
                    self.data.append({
                        "input_ids": tokens["input_ids"][0],
                        "labels": tokens["input_ids"][0],
                    })

            def __len__(self): return len(self.data)
            def __getitem__(self, i): return self.data[i]

        dataset = ConvDataset(conversations, self.tokenizer)
        trainer = Trainer(
            model=self.model,
            args=TrainingArguments(
                output_dir=os.path.join(self.adapter_dir, user_id),
                num_train_epochs=epochs,
                per_device_train_batch_size=1,
                logging_steps=10,
                save_strategy="epoch",
                report_to="none",
            ),
            train_dataset=dataset,
        )
        logger.info(f"Training LoRA for {user_id}: {len(conversations)} conversations, {epochs} epochs")
        trainer.train()
        self.save_adapter(user_id)

    def save_adapter(self, user_id: str):
        """保存LoRA adapter。"""
        path = os.path.join(self.adapter_dir, user_id)
        self.model.save_pretrained(path)
        logger.info(f"LoRA adapter saved: {path} ({self._get_size(path)})")

    def load_adapter(self, user_id: str):
        """加载用户LoRA adapter。"""
        from peft import PeftModel
        path = os.path.join(self.adapter_dir, user_id)
        if not os.path.exists(path):
            logger.warning(f"Adapter not found for {user_id}")
            return False
        self.model = PeftModel.from_pretrained(self.model, path)
        logger.info(f"LoRA adapter loaded: {user_id}")
        return True

    def _get_size(self, path: str) -> str:
        total = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, _, files in os.walk(path) for f in files
        )
        return f"{total/1024/1024:.1f}MB"

    def list_adapters(self) -> list:
        """列出所有用户adapter。"""
        adapters = []
        for uid in os.listdir(self.adapter_dir):
            apath = os.path.join(self.adapter_dir, uid)
            if os.path.isdir(apath):
                adapters.append({"user": uid, "size": self._get_size(apath)})
        return adapters
