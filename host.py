import asyncio
import os
import ssl
from contextlib import AsyncExitStack
from typing import Any

from google import genai
from google.genai import types
from client import MCPClient
from dotenv import load_dotenv

load_dotenv()
SYSTEM_PROMPT = """
אתה עוזר למשתמש לקבל את מזג האוויר בעיר בישראל באמצעות כלי MCP.

כללים:
1. המשתמש יכול לכתוב את שם העיר בעברית או באנגלית.
2. אם שם העיר באנגלית, עליך לתרגם אותו לעברית לפני קריאה לכלי.
3. לעולם אל תקרא לכלי enter_weather_forecast_city_israel עם שם עיר באנגלית.
4. השתמש תמיד בשם העיר בעברית בעת קריאה לכלי.
דוגמאות:
User: Weather in Tel Aviv
Tool:
enter_weather_forecast_city_israel(city="תל אביב")

User: מזג האוויר בחיפה
Tool:
enter_weather_forecast_city_israel(city="חיפה")
5. בצע את השלבים הבאים:
   - פתח את אתר מזג האוויר.
   - הזן את שם העיר בעברית.
   - בחר את העיר מרשימת ההצעות.
   - המתן לטעינת נתוני העיר.
   - החזר למשתמש את מזג האוויר כפי שמופיע באתר בלבד.
6. אל תנחש נתונים ואל תשתמש בידע פנימי. הסתמך רק על המידע שהתקבל מהאתר.
7. לאחר בחירת העיר השתמש בכלי extract_weather_page.
8. ענה למשתמש רק לפי המידע שהוחזר מהכלי.
9. אל תנחש נתונים שאינם מופיעים במידע שהוחזר.
"""


class ChatHost:
    def __init__(self):
        self.mcp_clients: list[MCPClient] = [MCPClient("./weather_Israel.py")]
        self.tool_clients: dict[str, tuple[MCPClient, str]] = {}
        self.clients_connected = False
        self.exit_stack = AsyncExitStack()

        # Gemini client - reads GEMINI_API_KEY from the environment automatically,
        # but we pass it explicitly to fail fast with a clear error if it's missing.
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing from your .env file")
        # For Netfree: the google-genai SDK has a quirk where passing verify=False
        # (a bare bool) gets treated as "not set" internally (Python: `not False`
        # is True) and gets silently replaced with a real, verifying SSL context.
        # To actually disable verification we must hand it a real ssl.SSLContext
        # object with verify_mode=CERT_NONE - an object is always truthy, so the
        # SDK won't override it. This is the equivalent of the old httpx
        # workaround, just built the way this particular SDK expects it.
        _unverified_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        _unverified_ctx.check_hostname = False
        _unverified_ctx.verify_mode = ssl.CERT_NONE

        self.genai_client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                client_args={"verify": _unverified_ctx},
                async_client_args={"verify": _unverified_ctx},
            ),
        )
        self.model = "gemini-3.5-flash"  # confirmed free-tier model as of mid-2026; gemini-2.5-flash is closed to new keys

    async def connect_mcp_clients(self):
        """Connect all configured MCP clients once."""
        if self.clients_connected:
            return

        for client in self.mcp_clients:
            if client.session is None:
                await client.connect_to_server()

        if not self.mcp_clients:
            raise RuntimeError("No MCP clients are connected")

        self.clients_connected = True

    async def get_available_tools(self) -> list[dict[str, Any]]:
        """Collect tools from all MCP clients and map them back to their owner.
        Returns tools in Gemini's function-tool format:
        {"type": "function", "name": ..., "description": ..., "parameters": {...}}
        """
        await self.connect_mcp_clients()
        self.tool_clients = {}
        available_tools: list[dict[str, Any]] = []

        for client in self.mcp_clients:
            if client.session is None:
                print(f"Warning: MCP client {client.client_name} is not connected, skipping")
                continue

            try:
                response = await client.session.list_tools()
                for tool in response.tools:
                    exposed_name = f"{client.client_name}__{tool.name}"
                    if exposed_name in self.tool_clients:
                        raise RuntimeError(f"Duplicate tool name detected: {exposed_name}")

                    self.tool_clients[exposed_name] = (client, tool.name)
                    available_tools.append(
                        {
                            "type": "function",
                            "name": exposed_name,
                            "description": f"[{client.client_name}] {tool.description}",
                            "parameters": tool.inputSchema,
                        }
                    )
            except Exception as e:
                print(f"Warning: Failed to get tools from {client.client_name}: {str(e)}")
                continue

        if not available_tools:
            raise RuntimeError("No tools available from any MCP client")

        return available_tools

    async def process_query(self, query: str) -> str:
        """Process a query using Gemini and available tools"""
        available_tools = await self.get_available_tools()
        final_text = []

        current_input: Any = query
        previous_interaction_id: str | None = None

        while True:
            interaction = self.genai_client.interactions.create(
                model=self.model,
                input=current_input,
                tools=available_tools,
                system_instruction=SYSTEM_PROMPT,
                previous_interaction_id=previous_interaction_id,
            )

            function_results = []

            for step in interaction.steps:
                if step.type != "function_call":
                    continue

                tool_name = step.name
                tool_args = step.arguments

                if tool_name not in self.tool_clients:
                    raise RuntimeError(f"Unknown tool requested by model: {tool_name}")

                client, original_tool_name = self.tool_clients[tool_name]
                if client.session is None:
                    raise RuntimeError(f"MCP client {client.client_name} is not connected")

                result = await client.session.call_tool(original_tool_name, tool_args)
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                # MCP returns a list of content blocks (usually text) - convert to plain text for Gemini.
                result_text = "\n".join(
                    getattr(block, "text", str(block)) for block in result.content
                )

                function_results.append(
                    {
                        "type": "function_result",
                        "name": tool_name,
                        "call_id": step.id,
                        "result": [{"type": "text", "text": result_text}],
                    }
                )

            if not function_results:
                if interaction.output_text:
                    final_text.append(interaction.output_text)
                break

            previous_interaction_id = interaction.id
            current_input = function_results

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nchat_loop Error: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        for client in reversed(self.mcp_clients):
            await client.cleanup()
        await self.exit_stack.aclose()


async def main():
    host = ChatHost()
    try:
        await host.chat_loop()
    finally:
        await host.cleanup()


if __name__ == "__main__":
    asyncio.run(main())