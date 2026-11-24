"""
文件监听器 — 轮询检测文件变化，自动触发摄入/删除 + 定期整理
"""

import os, time, json, logging

logger = logging.getLogger("nexus_kb.watcher")

SCHEDULE_PATH = "organize_schedule.json"  # 存于 .nexus/ 下
ORGANIZE_INTERVAL_DAYS = 3


class FileWatcher:
    """轮询监听目录变化 + 每3天凌晨自动整理。"""

    def __init__(self, knowledge_base, interval: float = 5.0):
        self.kb = knowledge_base
        self.interval = interval
        self._running = False
        self._snapshot: dict[str, float] = {}
        self._schedule_path = os.path.join(self.kb.index_dir, SCHEDULE_PATH)
        self._last_organize = self._load_schedule()

    def start(self):
        self._running = True
        self._snapshot = self._scan()
        logger.info(f"Watcher started: {self.kb.data_dir} (interval={self.interval}s, auto-organize every {ORGANIZE_INTERVAL_DAYS}d)")

    def stop(self):
        self._running = False

    def run_once(self) -> list:
        """单次扫描：检测变化 + 定时整理。"""
        if not self._snapshot:
            self._snapshot = self._scan()

        current = self._scan()
        events = []

        for path, mtime in current.items():
            if path not in self._snapshot:
                events.append({"type": "added", "path": path})
            elif mtime > self._snapshot[path]:
                events.append({"type": "modified", "path": path})

        for path in self._snapshot:
            if path not in current:
                events.append({"type": "deleted", "path": path})

        self._snapshot = current

        # 凌晨触发整理
        self._maybe_organize()

        return self._process(events)

    def _maybe_organize(self):
        """每 N 天凌晨自动整理。"""
        now = time.localtime()
        # 只在凌晨 1-5 点触发
        if not (1 <= now.tm_hour <= 5):
            return

        # 距上次整理超过 N 天
        days_since = (time.time() - self._last_organize) / 86400
        if days_since < ORGANIZE_INTERVAL_DAYS:
            return

        logger.info(f"Auto-organize triggered (last was {days_since:.1f} days ago)")
        try:
            # 模型驱动的整理——不是规则引擎
            result = self.kb.self.reflect()
            self._last_organize = time.time()
            self._save_schedule()
            logger.info(f"Auto-organize done: model reflected, organize decision left to self.live()")
        except Exception as e:
            logger.warning(f"Auto-organize failed: {e}")

    def _load_schedule(self) -> float:
        try:
            if os.path.exists(self._schedule_path):
                with open(self._schedule_path, "r") as f:
                    return json.load(f).get("last_organize", 0)
        except:
            pass
        return 0

    def _save_schedule(self):
        try:
            with open(self._schedule_path, "w") as f:
                json.dump({"last_organize": self._last_organize, "interval_days": ORGANIZE_INTERVAL_DAYS}, f)
        except:
            pass

    def _scan(self) -> dict[str, float]:
        """扫描目录下所有文件，跳过隐藏文件和索引目录。"""
        snapshot = {}
        for root, dirs, files in os.walk(self.kb.data_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.startswith("."):
                    continue
                fp = os.path.join(root, f)
                fp = os.path.normpath(fp).replace(os.sep, "/")
                try:
                    snapshot[fp] = os.path.getmtime(fp)
                except OSError:
                    pass
        return snapshot

    def _process(self, events: list) -> list:
        """处理检测到的事件。"""
        results = []
        for ev in events:
            try:
                if ev["type"] == "added":
                    r = self.kb.ingest_file(ev["path"])
                    results.append({**ev, "result": r})
                elif ev["type"] == "modified":
                    # 删除旧索引，重新摄入
                    self.kb.remove(ev["path"])
                    r = self.kb.ingest_file(ev["path"])
                    results.append({**ev, "result": r})
                elif ev["type"] == "deleted":
                    self.kb.remove(ev["path"])
                    results.append({**ev, "result": {"status": "removed"}})
            except Exception as e:
                results.append({**ev, "error": str(e)})
                logger.error(f"Watcher error on {ev['path']}: {e}")

        return results
