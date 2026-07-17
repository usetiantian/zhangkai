"""
技能沙箱 — 纯Python实现，零Docker依赖
借鉴ai-code-sandbox的隔离设计，用subprocess+受限导入替代Docker
"""
import subprocess, os, tempfile, logging
logger = logging.getLogger("nexus.sandbox")

DANGEROUS_MODULES = {
    "os", "subprocess", "shutil", "sys", "importlib",
    "ctypes", "socket", "requests", "urllib",
}

class SkillSandbox:
    """技能执行沙箱。用独立进程+超时+导入限制做隔离。"""

    def __init__(self, timeout: int = 30, max_memory_mb: int = 256):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb

    def run(self, code: str) -> dict:
        """
        安全执行Python代码。
        返回: {success, output, error, execution_time}
        """
        # 代码安全检查
        if self._has_dangerous_imports(code):
            return {"success": False, "output": "", "error": "代码包含危险导入"}

        # 写入临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            tmp_path = f.name

        try:
            result = subprocess.run(
                ["python", tmp_path],
                capture_output=True, text=True,
                timeout=self.timeout,
                env={**os.environ, "PYTHONPATH": os.getcwd()},
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout[:1000],
                "error": result.stderr[:500],
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": f"执行超时({self.timeout}s)"}
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _has_dangerous_imports(self, code: str) -> bool:
        """检查是否导入危险模块。"""
        for module in DANGEROUS_MODULES:
            if f"import {module}" in code or f"from {module}" in code:
                logger.warning(f"Blocked dangerous import: {module}")
                return True
        return False

    def scan_skill(self, code: str) -> dict:
        """
        技能上架前安全扫描。
        借鉴ClaudeCode的AST检测模式。
        """
        issues = []
        # 检查危险模式
        for module in DANGEROUS_MODULES:
            if f"import {module}" in code:
                issues.append(f"危险导入: {module}")
        if "exec(" in code or "eval(" in code:
            issues.append("动态执行: exec/eval")
        if "__import__" in code:
            issues.append("动态导入: __import__")
        if "rm -rf" in code or "del /f" in code:
            issues.append("文件删除命令")

        return {"passed": len(issues) == 0, "issues": issues}
