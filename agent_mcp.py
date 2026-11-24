"""MCP Bridge — 乾坤作为 MCP Client，可连接外部 MCP Server"""

import json, asyncio, subprocess, os
from dataclasses import dataclass, field
from pathlib import Path

MCP_CONFIG_DIR = Path("D:/qiankun/mcp-configs")


@dataclass
class McpServerConfig:
    """一个 MCP Server 配置"""
    name: str
    command: str = ""       # npx / python / node
    args: list = field(default_factory=list)
    env: dict = field(default_factory=dict)
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name, "command": self.command,
            "args": self.args, "env": self.env,
            "enabled": self.enabled, "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "McpServerConfig":
        return cls(**{k: d.get(k) for k in [
            "name", "command", "args", "env", "enabled", "description"
        ] if k in d})


class McpClient:
    """MCP 客户端 — 连接外部 MCP Server，获取工具"""

    def __init__(self):
        MCP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.servers: dict[str, McpServerConfig] = {}
        self.connected_tools: dict = {}  # {tool_name: func}
        self._load_configs()

    def _load_configs(self):
        config_file = MCP_CONFIG_DIR / "servers.json"
        if config_file.exists():
            data = json.loads(config_file.read_text(encoding="utf-8"))
            for d in data.get("servers", []):
                cfg = McpServerConfig.from_dict(d)
                self.servers[cfg.name] = cfg

    def _save_configs(self):
        MCP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config_file = MCP_CONFIG_DIR / "servers.json"
        config_file.write_text(json.dumps({
            "servers": [s.to_dict() for s in self.servers.values()]
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_server(self, name: str, command: str,
                   args: list = None, env: dict = None,
                   description: str = "") -> McpServerConfig:
        """添加 MCP Server"""
        cfg = McpServerConfig(
            name=name, command=command,
            args=args or [], env=env or {},
            description=description,
        )
        self.servers[name] = cfg
        self._save_configs()
        return cfg

    def remove_server(self, name: str):
        if name in self.servers:
            del self.servers[name]
            self._save_configs()

    def connect_all(self) -> dict:
        """连接所有启用的 MCP Server，注册其工具"""
        tools = {}
        for name, cfg in self.servers.items():
            if not cfg.enabled:
                continue
            try:
                server_tools = asyncio.run(
                    self._connect_one(cfg))
                tools.update(server_tools)
            except Exception as e:
                print(f"[MCP] {name}: {e}")
        self.connected_tools = tools
        return tools

    async def _connect_one(self, cfg: McpServerConfig) -> dict:
        """连接单个 MCP Server"""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=cfg.command,
            args=cfg.args,
            env={**os.environ, **cfg.env} if cfg.env else None,
        )

        tools = {}
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                for tool in result.tools:
                    tool_name = f"mcp_{cfg.name}_{tool.name}"

                    async def make_caller(session, t_name):
                        async def caller(**kwargs):
                            r = await session.call_tool(t_name, kwargs)
                            return r.content[0].text if r.content else str(r)
                        return caller

                    tools[tool_name] = {
                        "func": await make_caller(session, tool.name),
                        "desc": f"[MCP:{cfg.name}] {tool.description or tool.name}",
                    }
        return tools

    def get_tools(self) -> dict:
        return self.connected_tools

    def list_servers(self) -> list[dict]:
        return [
            {"name": s.name, "enabled": s.enabled,
             "command": s.command, "description": s.description}
            for s in self.servers.values()
        ]


# 全局
_mcp_client: McpClient | None = None


def get_mcp_client() -> McpClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = McpClient()
    return _mcp_client
