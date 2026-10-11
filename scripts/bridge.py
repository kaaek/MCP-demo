import asyncio, json, sys
import ollama
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MODEL = "qwen3-4b-mcp"  # the 8192-context model you built

async def main(prompt, url):
    async with streamable_http_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            try:
                await session.discover()  # 2026-07-28 stateless protocol
            except Exception as e:
                print(f"[discover failed: {e!r}; falling back to legacy initialize]")
                await session.initialize()

            tools = (await session.list_tools()).tools
            print(f"[server tools] {[t.name for t in tools]}")
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