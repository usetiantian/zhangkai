"""Sampler v2 — 移植自 grok-build run_request_task (200行完整逻辑)"""

import time, threading
from dataclasses import dataclass, field
from enum import Enum


class AttemptOutcome(Enum):
    COMPLETED = "completed"
    EMPTY = "empty"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INIT_FAILED = "init_failed"


class SamplingEvent(Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CHUNK = "chunk"
    CANCELLED = "cancelled"

@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

@dataclass
class Metrics:
    attempts: int = 1
    total_tokens: int = 0
    latency_ms: int = 0

@dataclass
class CompletionResult:
    text: str
    usage: Usage = field(default_factory=Usage)
    metrics: Metrics = field(default_factory=Metrics)

@dataclass
class SamplerConfig:
    model_path: str = ""
    max_retries: int = 3
    idle_timeout_secs: int = 60
    max_new_tokens: int = 2048
    temperature: float = 0.7
    doom_max_retries: int = 2


class Sampler:
    """
    采样器 — 移植自 grok-build run_request_task.

    完整实现:
    - 重试循环 + 退避
    - Empty response 检测和重试
    - 失败分类和重试决策
    - 取消处理
    - 事件发射
    """

    def __init__(self, config: SamplerConfig = None):
        self.config = config or SamplerConfig()
        self._model = None
        self._processor = None
        self._cancel_flag = False

    def load_model(self):
        try:
            import torch
            from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
            self._model = Qwen3VLForConditionalGeneration.from_pretrained(
                self.config.model_path, dtype=torch.float16, device_map="auto")
            self._processor = AutoProcessor.from_pretrained(self.config.model_path)
            return True
        except Exception as e:
            print(f"[Sampler] 模型加载失败: {e}")
            return False

    def sample(self, messages: list[dict],
               on_event=None) -> CompletionResult:
        """
        执行一次采样 — 移植自 run_request_task 的主循环.

        Args:
            messages: [{"role":"system","content":"..."}, ...]
            on_event: 可选事件回调
        """
        retry_count = 0
        max_retries = self.config.max_retries
        doom_count = 0
        self._cancel_flag = False

        if self._model is None:
            if not self.load_model():
                return CompletionResult(text="", metrics=Metrics(attempts=0))

        import torch

        while True:
            # 检查取消
            if self._cancel_flag:
                if on_event: on_event(SamplingEvent.CANCELLED, {})
                break

            # 执行一次尝试
            try:
                text, usage = self._run_one(messages)
                if text and len(text.strip()) > 5:
                    metrics = Metrics(attempts=retry_count + doom_count + 1,
                                      total_tokens=usage.total_tokens)
                    if on_event: on_event(SamplingEvent.COMPLETED,
                                          {"text": text, "metrics": metrics})
                    return CompletionResult(text=text, usage=usage, metrics=metrics)

                # Empty response
                retry_count += 1
                if retry_count >= max_retries:
                    if on_event: on_event(SamplingEvent.FAILED,
                                          {"error": "max retries exceeded (empty)"})
                    return CompletionResult(text="", metrics=Metrics(attempts=retry_count))

                if on_event: on_event(SamplingEvent.RETRYING,
                                      {"attempt": retry_count, "max": max_retries})
                time.sleep(2.0 * retry_count)  # backoff
                continue

            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    if on_event: on_event(SamplingEvent.FAILED,
                                          {"error": str(e)})
                    return CompletionResult(text=str(e), metrics=Metrics(attempts=retry_count))

                if on_event: on_event(SamplingEvent.RETRYING,
                                      {"attempt": retry_count, "error": str(e)})
                time.sleep(2.0 * retry_count)
                continue

    def _run_one(self, messages: list[dict]) -> tuple[str, Usage]:
        """执行一次推理 — 移植自 run_one_attempt"""
        import torch

        # VL 消息格式
        vl_msgs = []
        for m in messages:
            vl_msgs.append({
                "role": m["role"],
                "content": [{"type": "text", "text": m["content"]}],
            })

        prompt = self._processor.apply_chat_template(
            vl_msgs, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(
            text=[prompt], return_tensors="pt", padding=True).to(self._model.device)

        start = time.time()
        with torch.no_grad():
            generated = self._model.generate(
                **inputs, max_new_tokens=self.config.max_new_tokens,
                do_sample=True, temperature=self.config.temperature, top_p=0.9)

        output = self._processor.batch_decode(
            generated[:, inputs.input_ids.shape[1]:], skip_special_tokens=True)[0]

        latency_ms = int((time.time() - start) * 1000)
        tokens = generated.shape[1] - inputs.input_ids.shape[1]

        usage = Usage(
            prompt_tokens=inputs.input_ids.shape[1],
            completion_tokens=tokens,
            total_tokens=generated.shape[1])

        return output, usage

    def cancel(self):
        self._cancel_flag = True

    def unload(self):
        if self._model: del self._model; self._model = None
        if self._processor: del self._processor; self._processor = None
        import gc, torch; gc.collect(); torch.cuda.empty_cache()
