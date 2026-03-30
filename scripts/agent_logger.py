#!/usr/bin/env python3
"""
Логгер токенов для агентов Claude Code.
Вызывается хуком PostToolUse, читает JSON из stdin, пишет в logs/agent_session.log.
"""

import json
import sys
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

SESSION_LOG = os.path.join(LOG_DIR, "agent_session.log")
SUMMARY_LOG = os.path.join(LOG_DIR, "agent_summary.log")

def estimate_tokens(text: str) -> int:
    """Грубая оценка токенов: ~4 символа = 1 токен."""
    return max(1, len(str(text)) // 4)

def format_size(chars: int) -> str:
    if chars < 1000:
        return f"{chars}c"
    return f"{chars/1000:.1f}kc"

def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return

    tool_name = event.get("tool_name", "unknown")
    tool_input = event.get("tool_input", {})
    tool_response = event.get("tool_response", "")
    session_id = event.get("session_id", "")[:8]

    # Размеры
    input_chars = len(json.dumps(tool_input))
    output_chars = len(str(tool_response))
    input_tokens = estimate_tokens(json.dumps(tool_input))
    output_tokens = estimate_tokens(tool_response)

    # Краткое описание вызова для лога
    tool_detail = ""
    if tool_name in ("Read",):
        tool_detail = f" file={tool_input.get('file_path', '')}"
    elif tool_name in ("Bash",):
        cmd = str(tool_input.get("command", ""))[:60]
        tool_detail = f" cmd={cmd!r}"
    elif tool_name in ("Grep",):
        tool_detail = f" pattern={tool_input.get('pattern', '')!r} path={tool_input.get('path', '')}"
    elif tool_name in ("Glob",):
        tool_detail = f" pattern={tool_input.get('pattern', '')!r}"
    elif tool_name.startswith("mcp__"):
        # MCP вызовы — показать ключевые параметры
        keys = list(tool_input.keys())[:3]
        params = {k: str(tool_input[k])[:40] for k in keys}
        tool_detail = f" params={params}"

    ts = datetime.now().strftime("%H:%M:%S")

    line = (
        f"[{ts}] [{session_id}] {tool_name}{tool_detail}\n"
        f"         IN: {format_size(input_chars)} (~{input_tokens} tok) | "
        f"OUT: {format_size(output_chars)} (~{output_tokens} tok)\n"
    )

    with open(SESSION_LOG, "a", encoding="utf-8") as f:
        f.write(line)

    # Отдельный summary — только имя инструмента + размер ответа, для быстрого анализа
    summary_line = f"{ts}\t{tool_name}\t{output_chars}\t{output_tokens}\n"
    with open(SUMMARY_LOG, "a", encoding="utf-8") as f:
        f.write(summary_line)

if __name__ == "__main__":
    main()
