#!/usr/bin/env python3
"""Convert agent JSON to Claude Code or OpenCode format.

Reads a JSON file with agent definition (name, description, tools, instructions)
and outputs a valid configuration for the specified AI tool.

Usage:
    python format.py <input.json> <claude-code|opencode> [--output <path>]

Examples:
    python format.py src/agents/worker.json claude-code
    python format.py src/agents/worker.json opencode
    python format.py src/agents/worker.json claude-code --output .claude/agents/worker.md
    python format.py src/agents/worker.json opencode --output opencode-agents.json
"""

import argparse
import json
import os
import sys


def load_agent(path: str) -> dict:
    """Load and validate agent JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    for key in ("name", "description", "instructions"):
        if key not in data:
            raise ValueError(f"Missing required field: {key}")

    if "tools" not in data:
        data["tools"] = []

    return data


def to_claude_code_md(agent: dict) -> str:
    """Convert agent to Claude Code Markdown format with YAML frontmatter."""
    tools_str = ", ".join(agent["tools"]) if agent["tools"] else ""

    lines = ["---", f"name: {agent['name']}", f"description: {agent['description']}"]
    if tools_str:
        lines.append(f"tools: {tools_str}")
    lines += ["---", "", agent["instructions"]]

    return "\n".join(lines)


def to_claude_code_json(agent: dict) -> dict:
    """Convert agent to Claude Code CLI JSON format (--agents flag)."""
    result = {
        agent["name"]: {
            "description": agent["description"],
            "prompt": agent["instructions"],
        }
    }
    if agent["tools"]:
        result[agent["name"]]["tools"] = ", ".join(agent["tools"])
    return result


def to_opencode_json(agent: dict) -> dict:
    """Convert agent to OpenCode JSON format (for opencode.json 'agent' key)."""
    entry = {
        "description": agent["description"],
        "mode": "subagent",
        "prompt": agent["instructions"],
    }
    if agent["tools"]:
        entry["tools"] = {t.lower(): True for t in agent["tools"]}
    return {agent["name"]: entry}


def to_opencode_md(agent: dict) -> str:
    """Convert agent to OpenCode Markdown format with YAML frontmatter."""
    lines = [
        "---",
        f"description: {agent['description']}",
        "mode: subagent",
        "tools:",
    ]

    all_known_tools = [
        "bash", "read", "write", "edit", "glob", "grep", "webfetch", "websearch",
        "codesearch", "skill", "question", "todo",
    ]
    allowed = {t.lower() for t in agent["tools"]}
    for tool in all_known_tools:
        if tool in allowed:
            lines.append(f"  {tool}: true")

    lines += ["", agent["instructions"]]
    return "\n".join(lines)


def determine_output_path(args, agent: dict, fmt: str) -> str:
    """Determine output file path."""
    if args.output:
        if os.path.isdir(args.output):
            ext = "md" if fmt == "claude-code" else "json"
            return os.path.join(args.output, f"{agent['name']}.{ext}")
        return args.output

    ext = "md" if fmt == "claude-code" else "json"
    return f"{agent['name']}.{ext}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="Input agent JSON file")
    parser.add_argument("format", choices=["claude-code", "opencode"], help="Target format")
    parser.add_argument("--output", "-o", help="Output file or directory (default: stdout)")
    parser.add_argument("--style", choices=["markdown", "json"], help="Output style (default: markdown for claude-code, json for opencode)")
    args = parser.parse_args()

    agent = load_agent(args.input)
    fmt = args.format
    style = args.style or ("markdown" if fmt == "claude-code" else "json")

    if fmt == "claude-code":
        output = to_claude_code_md(agent) if style == "markdown" else json.dumps(to_claude_code_json(agent), indent=2, ensure_ascii=False)
    else:
        output = to_opencode_md(agent) if style == "markdown" else json.dumps(to_opencode_json(agent), indent=2, ensure_ascii=False)

    if args.output:
        out_path = determine_output_path(args, agent, fmt)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output)
            f.write("\n")
        print(f"Written: {out_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
