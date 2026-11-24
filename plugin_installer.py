"""Plugin Installer v2 — 事务性安装 + 回滚 (移植自 grok-build install_from_marketplace)"""

import json, shutil
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class InstallResult:
    """安装结果"""
    ok: bool
    repo_key: str = ""
    error: str = ""
    already_installed: bool = False


class InstallRegistry:
    """
    安装注册表 — 持久化 installed plugins.
    
    移植自 grok-build InstallRegistry.
    """
    def __init__(self, install_dir: Path = None):
        self.install_dir = install_dir or Path("D:/qiankun/plugins/installed")
        self.registry_file = self.install_dir / "registry.json"
        self.entries: dict[str, dict] = {}
        self.install_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if self.registry_file.exists():
            try:
                data = json.loads(self.registry_file.read_text(encoding="utf-8"))
                self.entries = data.get("plugins", {})
            except Exception:
                self.entries = {}

    def save(self):
        """保存注册表"""
        self.registry_file.write_text(json.dumps({
            "plugins": self.entries,
            "updated_at": __import__('datetime').datetime.now().isoformat(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def insert(self, key: str, repo: dict):
        self.entries[key] = repo
        self.save()

    def remove(self, key: str):
        if key in self.entries:
            del self.entries[key]
            self.save()

    def contains(self, key: str) -> bool:
        return key in self.entries

    def list_installed(self) -> list[dict]:
        return [
            {"key": k, **v}
            for k, v in self.entries.items()
        ]


class PluginInstaller:
    """
    插件安装器 — 事务性安装 + 回滚.
    
    移植自 grok-build install_from_marketplace:
    - 事务性: 安装失败自动回滚
    - 重试: AlreadyInstalled → remove old → retry
    - Manifest: 自动生成 plugin.json
    """

    def __init__(self, plugin_dir: Path = None):
        self.plugin_dir = plugin_dir or Path("D:/qiankun/plugins")
        self.registry = InstallRegistry(
            self.plugin_dir / "installed")
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

    def install(self, source_path: str, name: str = "",
                description: str = "") -> InstallResult:
        """安装插件 — 事务性"""
        src = Path(source_path)
        if not src.exists():
            return InstallResult(ok=False, error=f"源不存在: {source_path}")

        if not name:
            name = src.name

        dest = self.plugin_dir / name
        repo_key = name

        # Already installed?
        if self.registry.contains(repo_key):
            # 移除旧版本
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            self.registry.remove(repo_key)

        # 事务性安装
        try:
            if src.is_dir():
                shutil.copytree(src, dest, dirs_exist_ok=True)
            else:
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest / src.name)

            # 确保有 manifest
            self._ensure_manifest(dest, name, description)

            # 注册
            self.registry.insert(repo_key, {
                "name": name,
                "description": description,
                "source_path": str(src),
                "installed_at": __import__('datetime').datetime.now().isoformat(),
            })

            return InstallResult(ok=True, repo_key=repo_key)

        except Exception as e:
            # 回滚
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            self.registry.remove(repo_key)
            return InstallResult(ok=False, error=str(e))

    def uninstall(self, name: str) -> InstallResult:
        """卸载插件"""
        if not self.registry.contains(name):
            return InstallResult(ok=False, error=f"未安装: {name}")

        dest = self.plugin_dir / name
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)

        self.registry.remove(name)
        return InstallResult(ok=True, repo_key=name)

    def _ensure_manifest(self, dest: Path, name: str, description: str):
        """确保有 plugin.json"""
        manifest = dest / "plugin.json"
        if not manifest.exists():
            manifest.write_text(json.dumps({
                "name": name,
                "version": "0.1.0",
                "description": description,
                "entry": "",
                "tools": [],
            }, ensure_ascii=False, indent=2), encoding="utf-8")

    def discover_local(self) -> list[dict]:
        """发现本地插件"""
        plugins = []
        for d in self.plugin_dir.iterdir():
            if d.is_dir() and (d / "plugin.json").exists():
                try:
                    cfg = json.loads((d / "plugin.json").read_text(
                        encoding="utf-8"))
                    plugins.append(cfg)
                except Exception:
                    pass
        return plugins

    def stats(self) -> dict:
        return {
            "installed": len(self.registry.entries),
            "plugins": self.registry.list_installed(),
            "local": len(self.discover_local()),
        }
