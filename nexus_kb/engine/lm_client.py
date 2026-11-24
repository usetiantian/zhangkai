"""
nexus_kb 内置模型客户端 — 基于 LM Studio 的 llama.cpp 后端。
自动启动服务器、加载模型，不依赖 LM Studio GUI。
零外部依赖，2.4GB GGUF → ~2.6GB 显存。
"""

import requests, json, subprocess, os, time, logging, sys

logger = logging.getLogger("nexus_kb.lm")

DEFAULT_BASE = "http://localhost:1234/v1"
LMS_BIN = os.path.expanduser("~/.lmstudio/bin/lms")
MODEL_KEY = "qwen/qwen3-vl-4b"


class LMStudioClient:
    """自启动 LM Studio 后端客户端。首次调用自动加载模型。"""

    def __init__(self, base_url: str = None):
        self.base = (base_url or DEFAULT_BASE).rstrip("/")
        self._available = None
        self._start_attempted = False

    def _ensure_server(self) -> bool:
        """确保服务器在线。不在就自动启动。"""
        if self._check_http():
            return True
        if self._start_attempted:
            return False  # 已经试过，不重复

        self._start_attempted = True
        sys.stderr.write("[lm] LM Studio 服务器未运行，自动启动...\n")
        sys.stderr.flush()

        # Step 1: 启动服务器
        try:
            subprocess.run(
                [LMS_BIN, "server", "start"],
                capture_output=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            time.sleep(2)
        except Exception as e:
            logger.warning(f"lms server start failed: {e}")

        # Step 2: 加载模型
        try:
            subprocess.run(
                [LMS_BIN, "load", MODEL_KEY, "-y", "--gpu", "max"],
                capture_output=True, timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except Exception as e:
            logger.warning(f"lms load failed: {e}")

        # Step 3: 等待模型就绪
        for _ in range(30):
            if self._check_http():
                sys.stderr.write("[lm] 模型就绪\n")
                sys.stderr.flush()
                return True
            time.sleep(1)

        sys.stderr.write("[lm] 启动超时，模型功能将不可用\n")
        sys.stderr.flush()
        return False

    def _check_http(self) -> bool:
        try:
            r = requests.get(f"{self.base}/models", timeout=3)
            if r.status_code == 200 and r.json().get("data"):
                return True
        except:
            pass
        return False

    def is_available(self) -> bool:
        if self._available is not None and self._available[1] > time.time() - 30:
            return self._available[0]
        ok = self._check_http() or self._ensure_server()
        self._available = (ok, time.time())
        return ok

    def ask(self, prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            r = requests.post(
                f"{self.base}/chat/completions",
                json={
                    "model": self.model_name(),
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                },
                timeout=120,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"LM ask failed: {e}")
            raise

    def embed(self, text: str) -> list:
        try:
            r = requests.post(
                f"{self.base}/embeddings",
                json={"input": text[:1000]},
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json().get("data", [])
                if data:
                    return data[0].get("embedding", [])
        except:
            pass
        return None

    def model_name(self) -> str:
        try:
            r = requests.get(f"{self.base}/models", timeout=5)
            return r.json()["data"][0]["id"]
        except:
            return "unknown"
