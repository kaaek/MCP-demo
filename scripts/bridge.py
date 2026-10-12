"""MCP client/host that lets a local Ollama model (Qwen) use tools from an MCP server.

Why this script exists: `ollama run` is only a chat client. It sends text to the
model and prints the reply; it does not speak MCP. A model cannot call tools on
its own either: it can only emit a structured tool-call request as text, and
something else must act on it. This script is that something. It:

  1. Connects to the MCP server and lists its tools and prompts.
  2. Converts the MCP tool schemas to Ollama's `tools` format and passes them
     to the model so it knows what it can call.
  3. Detects tool calls in the model's response.
  4. Executes them on the MCP server via `tools/call`.
  5. Appends the results to the conversation as `tool` messages and calls the
     model again, repeating until it answers in plain text (capped at 6 rounds).

It can also expand a server-side MCP prompt: pass "--prompt <name> key=value ..."
as the prompt argument.

Usage: python bridge.py "your prompt" [server url]
Set BRIDGE_PROXY=http://127.0.0.1:8080 to route the MCP traffic (not Ollama's)
through a proxy such as Burp Suite.
"""
import asyncio, json, os, sys
import httpx2
import ollama
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import MCP_DEFAULT_SSE_READ_TIMEOUT, MCP_DEFAULT_TIMEOUT

MODEL = "qwen3-4b-mcp"  # the 8192-context model you built

async def main(prompt, url):
    proxy = os.environ.get("BRIDGE_PROXY")
    http_client = httpx2.AsyncClient(
        proxy=proxy,
        timeout=httpx2.Timeout(MCP_DEFAULT_TIMEOUT, read=MCP_DEFAULT_SSE_READ_TIMEOUT),
    ) if proxy else None
    async with streamable_http_client(url, http_client=http_client) as (read, write):
        async with ClientSession(read, write) as session:
            try:
                await session.discover()  # 2026-07-28 stateless protocol
            except Exception as e:
                print(f"[discover failed: {e!r}; falling back to legacy initialize]")
                await session.initialize()

            tools = (await session.list_tools()).tools
            print(f"[server tools] {[t.name for t in tools]}")
            prompts = (await session.list_prompts()).prompts
            for p in prompts:
                args = [a.name + ("*" if a.required else "") for a in p.arguments or []]
                print(f"[server prompt] {p.name}({', '.join(args)}) - {p.description}")
            ollama_tools = [{
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.input_schema,
                },
            } for t in tools]

            if prompt.startswith("--prompt "):  # e.g. "--prompt investigate_domain domain=example.com"
                _, pname, *kv = prompt.split()
                got = await session.get_prompt(pname, dict(p.split("=", 1) for p in kv))
                prompt = got.messages[0].content.text
                print(f"[prompts/get {pname}] {prompt}")

            client = ollama.AsyncClient()
            messages = [{"role": "user", "content": prompt}]
            for _ in range(6):  # cap the loop so a confused model can't spin forever
                resp = await client.chat(model=MODEL, messages=messages, tools=ollama_tools)
                msg = resp.message
                messages.append(msg)

                if not msg.tool_calls:
                    print(f"\n[final answer] {msg.content}")
                    return

                for call in msg.tool_calls:
                    name, arguments = call.function.name, dict(call.function.arguments)
                    print(f"[tool call] {name}({json.dumps(arguments)})")
                    result = await session.call_tool(name, arguments)
                    text = "\n".join(c.text for c in result.content if hasattr(c, "text"))
                    print(f"[tool result] {text}")
                    messages.append({"role": "tool", "tool_name": name, "content": text})

            print("[stopped] hit the loop cap without a final answer")

if __name__ == "__main__":
    # usage: python bridge.py "your prompt" [server url]
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000/mcp"))