"""
Nexus 身份权重核心 — 可训练的神经身份层

不是prompt注入。是嵌入Qwen的神经模块。
  - 初始训练: 用SOUL.md+Constitution+CC对话编码成权重
  - 运行时: 权重参与推理，自然知道"我是谁"
  - 持续训练: 每次交互 → 权重微调 → 越来越像Nexus

借鉴: ClaudeCode的identity构造 + GrokBuild的神经网络设计
"""
import torch
import torch.nn as nn
import os, logging, json

logger = logging.getLogger("nexus.identity_weight")

class IdentityWeight(nn.Module):
    """
    身份权重层。
    初始用SOUL.md训练 → 运行时加载 → 每次对话微调。
    独立于Qwen基座，换基座模型时权重不变。
    """

    def __init__(self, hidden_dim: int = 512, identity_dim: int = 256):
        super().__init__()
        # 身份编码器: 把文字身份(ID/规则/约束)压成向量
        self.identity_encoder = nn.Sequential(
            nn.Linear(hidden_dim, identity_dim),
            nn.ReLU(),
            nn.Linear(identity_dim, identity_dim),
        )
        # 行为调制器: 身份向量调制推理行为
        self.behavior_modulator = nn.Linear(identity_dim, hidden_dim)
        # 状态: 学习到的身份向量
        self.register_buffer("identity_vector", torch.zeros(identity_dim))

        self.trained = False
        self.conversation_count = 0

    def get_identity_prefix(self, num_tokens: int = 4, hidden_dim: int = 1536) -> torch.Tensor:
        """
        生成身份前缀嵌入。
        用behavior_modulator投影身份向量到模型维度。
        返回: [1, num_tokens, hidden_dim]
        """
        if not self.trained or self.identity_vector.sum() == 0:
            return None

        # 用behavior_modulator投影到模型隐藏维度
        projected = self.behavior_modulator(self.identity_vector)  # [hidden_dim]
        # 展开成前缀tokens并轻微缩放
        prefix = projected.unsqueeze(0).unsqueeze(0).repeat(1, num_tokens, 1)
        prefix = prefix * 0.1  # 软调制，不盖过输入
        return prefix

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: 输入embedding [batch, seq, hidden_dim]
        返回: [身份前缀 | 原始输入] 拼接后的embedding
        """
        prefix = self.get_identity_prefix(4, x.shape[-1])
        if prefix is None:
            return x

        prefix = prefix.to(device=x.device, dtype=x.dtype)
        return torch.cat([prefix, x], dim=1)

    def train_identity(self, identity_texts: list, tokenizer, model, epochs: int = 5, lr: float = 1e-3):
        """
        训练身份权重。
        identity_texts: [SOUL.md内容, Constitution内容, 示例对话...]
        tokenizer: Qwen的tokenizer
        model: Qwen模型(只用来获取embedding维度，不修改)
        """
        if not identity_texts:
            logger.warning("No identity texts to train on")
            return

        optimizer = torch.optim.Adam(self.parameters(), lr=lr)

        # 用第一条身份文本确定hidden_dim
        device = next(model.parameters()).device
        with torch.no_grad():
            test_tokens = tokenizer(identity_texts[0][:500], return_tensors="pt")
            test_ids = test_tokens.input_ids.to(device)
            if hasattr(model, 'get_input_embeddings'):
                test_emb = model.get_input_embeddings()(test_ids)
                actual_dim = test_emb.shape[-1]

        # 如果维度不匹配，重建编码器
        if actual_dim != self.identity_encoder[0].in_features:
            self._rebuild_encoder(actual_dim)

        device = next(model.parameters()).device
        dtype = next(model.parameters()).dtype
        self.to(device=device, dtype=dtype)

        for epoch in range(epochs):
            total_loss = 0
            for text in identity_texts[:10]:  # 最多10条
                tokens = tokenizer(text[:500], return_tensors="pt", truncation=True)
                input_ids = tokens.input_ids.to(device)
                with torch.no_grad():
                    if hasattr(model, 'get_input_embeddings'):
                        emb = model.get_input_embeddings()(input_ids)
                    else:
                        continue

                # 前向: 身份编码 → 调制
                identity_vec = self.identity_encoder(emb.mean(dim=1))  # [1, id_dim]
                self.identity_vector.data = identity_vec.squeeze(0).detach()

                # 损失: 身份向量应该一致(不同身份文本编码应相似)
                loss = 0
                for text2 in identity_texts[1:3]:
                    tokens2 = tokenizer(text2[:500], return_tensors="pt", truncation=True)
                    ids2 = tokens2.input_ids.to(device)
                    with torch.no_grad():
                        if hasattr(model, 'get_input_embeddings'):
                            emb2 = model.get_input_embeddings()(ids2)
                            vec2 = self.identity_encoder(emb2.mean(dim=1))
                    loss += nn.functional.mse_loss(identity_vec, vec2)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            if total_loss > 0:
                logger.info(f"Identity training epoch {epoch+1}/{epochs}: loss={total_loss:.4f}")

        self.trained = True
        self.conversation_count = 0
        logger.info(f"Identity weight trained on {len(identity_texts)} texts")

    def update_from_conversation(self, user_msg: str, nexus_reply: str, was_good: bool):
        """
        从对话中更新身份权重。
        good对话 → 强化当前身份
        bad对话 → 调整身份表达
        """
        self.conversation_count += 1
        # 每100轮做一次小更新
        if self.conversation_count % 100 == 0:
            # 此处需要实际的训练逻辑——微调identity_vector
            logger.debug(f"Identity update after {self.conversation_count} conversations")

    def _rebuild_encoder(self, hidden_dim: int):
        """重建编码器适配新的hidden_dim。"""
        identity_dim = self.identity_encoder[-1].out_features
        self.identity_encoder = nn.Sequential(
            nn.Linear(hidden_dim, identity_dim),
            nn.ReLU(),
            nn.Linear(identity_dim, identity_dim),
        )
        self.behavior_modulator = nn.Linear(identity_dim, hidden_dim)

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        torch.save({
            "state_dict": self.state_dict(),
            "trained": self.trained,
            "conversation_count": self.conversation_count,
        }, path)
        logger.info(f"Identity weight saved to {path}")

    def load(self, path: str):
        if not os.path.exists(path): return False
        data = torch.load(path, map_location="cpu")
        self.load_state_dict(data["state_dict"])
        self.trained = data.get("trained", True)
        self.conversation_count = data.get("conversation_count", 0)
        logger.info(f"Identity weight loaded from {path}")
        return True

    @classmethod
    def create_and_train(cls, soul_path: str, const_path: str, tokenizer, model, save_path: str = None):
        """工厂方法: 创建+训练+保存身份权重。"""
        texts = []
        for path in [soul_path, const_path]:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    texts.append(f.read())

        # 添加示例对话
        texts.extend([
            "我是Nexus，张凯的个人AI。我守护他的数据，我的原则是简洁直接。",
            "Nexus的Constitution: A0守护用户利益。A0.1禁止删除文件。A1先备份。A2简洁。A3闭环。",
        ])

        weight = cls()
        weight.train_identity(texts, tokenizer, model, epochs=5)
        if save_path:
            weight.save(save_path)
        return weight
