"""MCP Server — 乾坤作为 MCP Server，对外暴露工具"""

import json, asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


class QianKunMcpServer:
    """乾坤 MCP Server — 让其他 Agent 可以调用乾坤的工具"""

    def __init__(self, agent):
        self.agent = agent
        self.server = Server("qiankun")

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """列出乾坤的工具"""
            tools = []
            for name, info in self.agent.tools.items():
                tools.append(Tool(
                    name=name,
                    description=info.get("desc", ""),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ))
            # 添加元工具
            tools.append(Tool(
                name="qiankun_chat",
                description="直接和乾坤对话",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "输入消息"},
                    },
                    "required": ["message"],
                },
            ))
            return tools

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
            """执行工具"""
            if name == "qiankun_chat":
                reply = self.agent.handle(arguments.get("message", ""))
                return [TextContent(type="text", text=reply)]

            if name not in self.agent.tools:
                return [TextContent(type="text",
                    text=json.dumps({"error": f"unknown tool: {name}"},
                                    ensure_ascii=False))]

            try:
                func = self.agent.tools[name]["func"]
                result = func(**arguments) if arguments else func()
                return [TextContent(type="text",
                    text=json.dumps(result, ensure_ascii=False, default=str))]
            except Exception as e:
                return [TextContent(type="text",
                    text=json.dumps({"error": str(e)}, ensure_ascii=False))]

    async def run(self):
        """启动 MCP Server"""
        print("[MCP Server] 乾坤 MCP Server 已启动")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream,
                self.server.create_initialization_options()
            )

    def start(self):
        """同步启动"""
        asyncio.run(self.run())
