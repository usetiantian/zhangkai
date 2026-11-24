"""Plugin Marketplace — 动态安装/卸载/启用工具"""

import json, importlib, sys
from pathlib import Path
from dataclasses import dataclass, field

PLUGIN_DIR = Path("D:/qiankun/plugins")
MARKETPLACE_FILE = PLUGIN_DIR / "marketplace.json"


@dataclass
class Plugin:
    """一个插件"""
    name: str
    version: str = "0.1.0"
    description: str = ""
    enabled: bool = True
    entry: str = ""  # module:function
    tools: list = field(default_factory=list)  # [{name, desc}]
    source: str = "local"  # local / marketplace

    def to_dict(self) -> dict:
        return {
            "name": self.name, "version": self.version,
            "description": self.description, "enabled": self.enabled,
            "entry": self.entry, "tools": self.tools,
            "source": self.source,
        }


class PluginMarketplace:
    """插件市场"""

    def __init__(self):
        PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
        self._plugins: dict[str, Plugin] = {}
        self._load()

    def _load(self):
        if MARKETPLACE_FILE.exists():
            data = json.loads(MARKETPLACE_FILE.read_text(encoding="utf-8"))
            for d in data.get("plugins", []):
                p = Plugin(**d)
                self._plugins[p.name] = p

    def _save(self):
        MARKETPLACE_FILE.write_text(
            json.dumps({"plugins": [p.to_dict() for p in self._plugins.values()]},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")

    def install(self, name: str, entry: str,
                tools: list = None, description: str = "") -> Plugin:
        """安装插件"""
        if name in self._plugins:
            raise ValueError(f"插件 {name} 已存在")
        p = Plugin(name=name, entry=entry, tools=tools or [],
                   description=description)
        self._plugins[name] = p
        self._save()
        return p

    def uninstall(self, name: str):
        """卸载"""
        if name in self._plugins:
            del self._plugins[name]
            self._save()

    def enable(self, name: str):
        if name in self._plugins:
            self._plugins[name].enabled = True
            self._save()

    def disable(self, name: str):
        if name in self._plugins:
            self._plugins[name].enabled = False
            self._save()

    def list_enabled(self) -> list[Plugin]:
        return [p for p in self._plugins.values() if p.enabled]

    def list_all(self) -> list[Plugin]:
        return list(self._plugins.values())

    def get(self, name: str) -> Plugin | None:
        return self._plugins.get(name)

    def discover_local(self):
        """扫描本地插件目录"""
        for d in PLUGIN_DIR.iterdir():
            if d.is_dir() and (d / "plugin.json").exists():
                cfg = json.loads((d / "plugin.json").read_text(encoding="utf-8"))
                name = cfg.get("name", d.name)
                if name not in self._plugins:
                    self.install(
                        name=name,
                        entry=cfg.get("entry", ""),
                        tools=cfg.get("tools", []),
                        description=cfg.get("description", ""),
                    )

    def load_tools(self) -> dict:
        """加载所有启用的插件工具 → {tool_name: func}"""
        tools = {}
        for p in self.list_enabled():
            if not p.entry:
                continue
            try:
                mod_name, func_name = p.entry.rsplit(":", 1)
                mod = importlib.import_module(mod_name)
                func = getattr(mod, func_name)
                for t in p.tools:
                    tools[t["name"]] = {"func": func, "desc": t.get("desc", "")}
            except Exception as e:
                print(f"[Plugin] 加载 {p.name} 失败: {e}")
        return tools


# 全局单例
_marketplace: PluginMarketplace | None = None


def get_marketplace() -> PluginMarketplace:
    global _marketplace
    if _marketplace is None:
        _marketplace = PluginMarketplace()
        _marketplace.discover_local()
    return _marketplace
