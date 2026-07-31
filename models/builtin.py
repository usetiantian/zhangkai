"""Built-in model adapters: null, local command, OpenAI-compatible HTTP."""
from __future__ import annotations
import json
import subprocess
from typing import Sequence
from urllib.request import Request, urlopen
from models.protocol import ModelError, ModelRequest, ModelResponse

PLACEHOLDER = "{prompt}"

class NullModelAdapter:
    def complete(self, request, input_text=None, token=None):
        return ModelResponse(text="", prompt_tokens=0, completion_tokens=0, model_id="null")

class CommandModelAdapter:
    def __init__(self, command, *, timeout_seconds=30):
        if not command:
            raise ModelError("command must be non-empty")
        if timeout_seconds < 1:
            raise ModelError("timeout_seconds must be positive")
        self.template = tuple(command)
        self.timeout_seconds = timeout_seconds

    def complete(self, request, input_text=None, token=None):
        body = input_text if input_text is not None else request.prompt
        rendered = tuple(
            body if token == PLACEHOLDER else token
            for token in self.template
        )
        try:
            result = subprocess.run(
                rendered,
                input=body,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ModelError(str(error)) from error
        if result.returncode:
            raise ModelError(result.stderr.strip() or "command failed")
        return ModelResponse(
            text=result.stdout,
            prompt_tokens=0,
            completion_tokens=0,
            model_id="command",
        )

class OpenAICompatibleAdapter:
    def __init__(self, endpoint, *, model_id, timeout_seconds=30):
        if not endpoint.startswith(("http://", "https://")):
            raise ModelError("endpoint must be http or https")
        self.endpoint = endpoint.rstrip("/")
        self.model_id = model_id
        self.timeout_seconds = timeout_seconds

    def complete(self, request, input_text=None, token=None):
        if not token:
            raise ModelError("OpenAI-compatible adapter requires token from environment")
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": input_text or request.prompt},
            ],
            "max_tokens": request.max_tokens,
        }
        body = json.dumps(payload).encode()
        http_request = Request(
            f"{self.endpoint}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urlopen(http_request, timeout=self.timeout_seconds) as response:
            data = json.loads(response.read())
        choice = data["choices"][0]
        text = choice["message"]["content"]
        usage = data.get("usage", {})
        return ModelResponse(
            text=text,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model_id=data.get("model", self.model_id),
        )
