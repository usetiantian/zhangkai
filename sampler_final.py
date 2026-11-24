"""Sampler — 移植自 grok-build: run_request_task + run_one_attempt + apply_retry_decision (356行源码)"""

import time, threading, re
from dataclasses import dataclass, field
from enum import Enum


class AttemptOutcome(Enum):
    COMPLETED = "completed"
    EMPTY = "empty"
    FAILED = "failed"
    CANCELLED = "cancelled"

class RetryDecision(Enum):
    RETRY = "retry"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    FATAL = "fatal"

@dataclass
class SamplingError:
    message: str
    is_retryable: bool = True
    is_rate_limited: bool = False
    status_code: int = 0

@dataclass
class RetryPolicy:
    max_retries: int = 3
    rate_limit_threshold: int = 3

@dataclass
class CompletionResult:
    text: str = ""
    attempts: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

class SamplingEvent:
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CHUNK = "chunk"


RATE_LIMIT_RETRY_THRESHOLD = 3


def classify_error(err: SamplingError, retry_count: int,
                   max_retries: int, rate_limit_threshold: int) -> RetryDecision:
    """错误分类 — 移植自 grok-build classify_error"""
    if retry_count >= max_retries:
        return RetryDecision.FATAL
    if err.is_rate_limited and retry_count >= rate_limit_threshold:
        return RetryDecision.FATAL
    if err.is_retryable:
        backoff_sec = min(2.0 * (2 ** retry_count), 30.0)
        return RetryDecision.RETRY_WITH_BACKOFF
    return RetryDecision.FATAL


def retry_backoff(retry_count: int) -> float:
    """退避时间: 2s → 4s → 8s → ... → 30s cap"""
    return min(2.0 * (2 ** retry_count), 30.0)


class Sampler:
    """采样器 — 移植自 grok-build SamplerActor + run_request_task"""

    def __init__(self, model_path: str, max_retries: int = 3, max_tokens: int = 2048):
        self.model_path = model_path
        self.max_retries = max_retries
        self.max_tokens = max_tokens
        self._model = None; self._processor = None
        self._cancel = False
        self._listeners: list = []

    def load(self):
        import torch
        from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
        self._model = Qwen3VLForConditionalGeneration.from_pretrained(
            self.model_path, dtype=torch.float16, device_map="auto")
        self._processor = AutoProcessor.from_pretrained(self.model_path)

    def on(self, event: str, callback):
        self._listeners.append((event, callback))

    def _emit(self, event: str, data: dict = None):
        for e, cb in self._listeners:
            if e == event:
                try: cb(data or {})
                except: pass

    def sample(self, messages: list[dict]) -> CompletionResult:
        """run_request_task: 主循环 — 移植自 grok-build"""
        self._cancel = False
        retry_count = 0
        self._emit(SamplingEvent.STARTED)

        while True:
            if self._cancel:
                return CompletionResult(text="已取消", attempts=retry_count)

            try:
                text, prompt_tok, comp_tok = self._run_one(messages)

                if text and len(text.strip()) > 10:
                    self._emit(SamplingEvent.COMPLETED, {"text": text})
                    return CompletionResult(
                        text=text, attempts=retry_count + 1,
                        prompt_tokens=prompt_tok, completion_tokens=comp_tok)

                # Empty response — retry
                err = SamplingError("empty response", is_retryable=True)
            except Exception as e:
                err = SamplingError(str(e), is_retryable=True)

            # apply_retry_decision — 移植自 grok-build
            decision = classify_error(err, retry_count, self.max_retries,
                                      RATE_LIMIT_RETRY_THRESHOLD)

            if decision == RetryDecision.RETRY_WITH_BACKOFF:
                retry_count += 1
                backoff = retry_backoff(retry_count)
                self._emit(SamplingEvent.RETRYING,
                          {"attempt": retry_count, "max": self.max_retries,
                           "backoff": backoff, "error": err.message})
                time.sleep(backoff)
                continue

            if decision == RetryDecision.RETRY:
                retry_count += 1
                self._emit(SamplingEvent.RETRYING,
                          {"attempt": retry_count, "max": self.max_retries})
                continue

            # Fatal
            self._emit(SamplingEvent.FAILED, {"error": err.message})
            return CompletionResult(text=err.message, attempts=retry_count + 1)

    def _run_one(self, messages: list[dict]) -> tuple[str, int, int]:
        """run_one_attempt: 单次推理 — 移植自 grok-build"""
        import torch

        if self._model is None:
            self.load()

        # VL chat template
        vl_msgs = [{"role": m["role"],
                     "content": [{"type": "text", "text": m["content"}]}
                    for m in messages]

        prompt = self._processor.apply_chat_template(
            vl_msgs, tokenize=False, add_generation_prompt=True)
        inputs = self._processor(text=[prompt], return_tensors="pt",
                                 padding=True).to(self._model.device)

        with torch.no_grad():
            generated = self._model.generate(
                **inputs, max_new_tokens=self.max_tokens,
                do_sample=True, temperature=0.7, top_p=0.9)

        output = self._processor.batch_decode(
            generated[:, inputs.input_ids.shape[1]:],
            skip_special_tokens=True)[0].strip()

        # 清理
        output = re.sub(r'<\|.*?\|>', '', output)
        if '</think>' in output:
            output = output.split('</think>', 1)[-1].strip()

        prompt_tok = inputs.input_ids.shape[1]
        comp_tok = generated.shape[1] - prompt_tok

        return output, prompt_tok, comp_tok

    def cancel(self):
        self._cancel = True

    def unload(self):
        if self._model: del self._model; self._model = None
        if self._processor: del self._processor; self._processor = None
        import gc, torch; gc.collect(); torch.cuda.empty_cache()
