"""Lesson 7 - give an agent real tools with an inline MCP server.

Everything so far used the agent's built-in abilities. The way you plug an
agent into a company's *own* systems (a database, an internal API, a ticketing
system, a filesystem) is MCP: you hand the agent one or more MCP servers and it
gains their tools for that conversation.

This lesson wires up a real stdio MCP server - the reference
`@modelcontextprotocol/server-everything` (launched via `npx`) - and asks the
agent to use one of its tools. Then it PROVES the tool actually ran by watching
the message stream for `tool_call` messages, not just trusting the final text.

What to notice:
  - MCP servers go on `AgentOptions.mcp_servers` as a {name: config} map.
  - A tool call shows up in `run.messages()` as a message with
    `type == "tool_call"` and `name == "mcp"`; `args` carries
    {providerIdentifier, toolName, args} and `result` arrives when it finishes.
  - Windows: the stdio command must be `npx.cmd`, not `npx`.
  - Inline MCP servers are NOT persisted across resume (lesson 5) - pass them
    again if you resume an agent that needs them.

Requires Node/npx on PATH (first run downloads the server, ~10-20s).

Run:  python lessons/07_mcp_tools.py
      add --demo for the offline, no-Node, no-key walkthrough
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import (  # noqa: E402
    MODEL,
    WORKSPACE,
    approve,
    banner,
    demo_enabled,
    require_api_key,
)

from cursor_sdk import (  # noqa: E402
    Agent,
    AgentOptions,
    CursorAgentError,
    LocalAgentOptions,
    StdioMcpServerConfig,
)

# The reference MCP test server. It exposes simple, unambiguous tools (a
# two-number sum, echo, etc.) that clearly can't be the agent's built-in
# behavior - so a successful call is real proof MCP is wired up.
MCP_SERVER_NAME = "everything"
NPX = "npx.cmd" if os.name == "nt" else "npx"

TASK = (
    "You have MCP tools from a server named 'everything'. Use its tool that "
    "adds two numbers to compute 40002 + 2000, then tell me the exact result "
    "the tool returned. Use the tool - do not add the numbers yourself."
)


def _mcp_result_text(result: object) -> str:
    """Best-effort pull of human text out of an MCP tool result payload."""
    try:
        content = result["value"]["content"]  # type: ignore[index]
        parts: list[str] = []
        for chunk in content:
            text = chunk.get("text")
            if isinstance(text, dict):
                text = text.get("text")
            if text:
                parts.append(str(text))
        return " ".join(parts) or str(result.get("status"))  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001 - defensive; tool payloads are untyped
        return repr(result)


def stream_with_tools(run) -> str:
    """Stream assistant text AND announce MCP tool calls as they happen.

    Returns the full assistant text. Tool-call messages arrive twice per call
    (status 'running' then 'completed'); we announce the call once and print its
    result when it lands.
    """
    chunks: list[str] = []
    announced: set[str] = set()
    for msg in run.messages():
        mtype = getattr(msg, "type", None)

        if mtype == "assistant":
            inner = getattr(msg, "message", None)
            for block in getattr(inner, "content", None) or ():
                if getattr(block, "type", None) == "text":
                    print(block.text, end="", flush=True)
                    chunks.append(block.text)

        elif mtype == "tool_call" and getattr(msg, "name", None) == "mcp":
            args = getattr(msg, "args", {}) or {}
            call_id = getattr(msg, "call_id", "")
            status = getattr(msg, "status", "")
            if status == "running" and call_id not in announced:
                announced.add(call_id)
                print(
                    f"\n  -> [MCP] {args.get('providerIdentifier')} / "
                    f"{args.get('toolName')}  args={args.get('args')}"
                )
            elif status == "completed":
                print(f"     result: {_mcp_result_text(getattr(msg, 'result', None))}\n")

    run.wait()  # terminal result + releases watchers (always, per lesson 2)
    print()
    return "".join(chunks)


def demo_run() -> None:
    print(f'\nWould send:\n   "{TASK}"\n')
    print("--- streamed run (simulated) ---")
    print("I'll use the everything server's sum tool.")
    print(f"\n  -> [MCP] {MCP_SERVER_NAME} / get-sum  args={{'a': 40002, 'b': 2000}}")
    print("     result: The sum of 40002 and 2000 is 42002.\n")
    print("The get-sum MCP tool returned 42002.")
    print("\n(demo note: a real run launches the server via npx and the agent "
          "actually calls it - watch the [MCP] lines above appear live.)")


def main() -> None:
    demo = demo_enabled()
    banner("Lesson 7: inline MCP tools" + ("  [DEMO]" if demo else ""))

    if demo:
        demo_run()
        return

    api_key = require_api_key()

    if not approve(
        f"Launch the '{MCP_SERVER_NAME}' MCP server (via {NPX}) and let an "
        f"agent call it?\n   Task: {TASK}",
        default_yes=True,
    ):
        print("Cancelled.")
        return

    # MCP servers attach to AgentOptions as a {name: config} map. Here: one
    # stdio server. Swap in HttpMcpServerConfig(url=...) for a hosted server,
    # or point StdioMcpServerConfig at your own company tool server.
    options = AgentOptions(
        api_key=api_key,
        model=MODEL,
        local=LocalAgentOptions(cwd=str(WORKSPACE)),
        mcp_servers={
            MCP_SERVER_NAME: StdioMcpServerConfig(
                command=NPX,
                args=["-y", "@modelcontextprotocol/server-everything"],
            )
        },
    )

    print("\nStarting agent + MCP server (first run downloads the server)...")
    try:
        with Agent.create(options) as agent:
            print(f"(agent={agent.agent_id})\n--- streamed run ---")
            answer = stream_with_tools(agent.send(TASK))
    except CursorAgentError as err:
        print(
            f"\nAgent failed to start: {err.message} "
            f"(retryable={err.is_retryable})\n"
            "If this is a Node/npx problem, make sure `npx --version` works.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return

    if "42002" in answer:
        print("[check] The agent used the MCP tool and reported 42002.")
    else:
        print("[check] Finished, but 42002 wasn't clearly reported - re-read the "
              "[MCP] lines above to see what the tool returned.")


if __name__ == "__main__":
    main()
