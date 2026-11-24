"""Crash Handler — 崩溃捕获 + 恢复 (移植自 grok-build crash-handler)"""

import sys, signal, traceback, os, time, json
from pathlib import Path
from datetime import datetime

CRASH_DIR = Path("D:/qiankun/data/crashes")


class CrashHandler:
    """
    崩溃处理器.
    
    移植自 grok-build crash_handler:
    - 注册崩溃信号 (SIGSEGV, SIGBUS → Python 的异常捕获)
    - 写入 crash blob (堆栈 + 状态)
    - 优雅关闭
    """
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.crash_count: int = 0
        self._original_excepthook = sys.excepthook

        if enabled:
            self._register()

    def _register(self):
        """注册信号处理器"""
        sys.excepthook = self._crash_handler
        CRASH_DIR.mkdir(parents=True, exist_ok=True)

    def _crash_handler(self, exc_type, exc_value, exc_tb):
        """崩溃处理 — 写入 crash blob"""
        self.crash_count += 1

        crash_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        crash_file = CRASH_DIR / f"crash_{crash_id}.json"

        blob = {
            "crash_id": crash_id,
            "timestamp": datetime.now().isoformat(),
            "exception_type": str(exc_type.__name__ if exc_type else "unknown"),
            "exception_message": str(exc_value)[:1000],
            "traceback": traceback.format_tb(exc_tb) if exc_tb else [],
            "crash_count": self.crash_count,
            "python_version": sys.version,
            "platform": sys.platform,
        }

        try:
            crash_file.write_text(json.dumps(blob, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        except Exception:
            pass

        # 调用原始处理器
        self._original_excepthook(exc_type, exc_value, exc_tb)

    def last_crash(self) -> dict | None:
        """最近一次崩溃"""
        files = sorted(CRASH_DIR.glob("crash_*.json"), reverse=True)
        if files:
            return json.loads(files[0].read_text(encoding="utf-8"))
        return None

    def stats(self) -> dict:
        return {
            "enabled": self.enabled,
            "crash_count": self.crash_count,
            "crash_dir": str(CRASH_DIR),
            "crashes_on_disk": len(list(CRASH_DIR.glob("crash_*.json"))),
        }


class HealthMonitor:
    """
    健康监控 — 定期检查系统状态.
    
    移植自 grok-build health_monitor / telemetry.
    """
    def __init__(self, agent=None, interval_sec: float = 60.0):
        self.agent = agent
        self.interval_sec = interval_sec
        self.checks: list = []
        self._running = False

    def add_check(self, name: str, func):
        """添加健康检查"""
        self.checks.append({"name": name, "func": func})

    def check_all(self) -> dict:
        """运行所有检查"""
        results = {}
        for check in self.checks:
            try:
                results[check["name"]] = check["func"]()
            except Exception as e:
                results[check["name"]] = {"error": str(e)}
        return results

    def start(self):
        """启动后台监控"""
        import threading
        self._running = True

        def _loop():
            while self._running:
                results = self.check_all()
                # 记录
                snapshot_file = CRASH_DIR / "health_snapshot.json"
                try:
                    snapshot_file.write_text(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "results": results,
                    }, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass
                time.sleep(self.interval_sec)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def stop(self):
        self._running = False


# 全局
_handler: CrashHandler | None = None


def get_crash_handler() -> CrashHandler:
    global _handler
    if _handler is None:
        _handler = CrashHandler()
    return _handler
