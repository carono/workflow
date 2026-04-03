#!/usr/bin/env python3
"""Build dist/<platform>/ from src/.

For each platform (claude-code, opencode):
  1. Reads rules/ and templates/ as inline content
  2. Substitutes template variables in agents/tools (e.g. {{RULES_SECURITY}})
  3. Converts src/agents/*.md and src/tools/*.md via format.py

Usage:
    python build.py              # build all platforms
    python build.py claude-code  # build only claude-code
    python build.py opencode     # build only opencode
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
SRC = os.path.join(ROOT, "src")
DIST = os.path.join(ROOT, "dist")
FORMAT_SCRIPT = os.path.join(SCRIPT_DIR, "format.py")

ALL_PLATFORMS = ["claude-code", "opencode"]


def load_template_variables() -> dict:
    """Read rules and templates files and return as template variables."""
    variables = {}

    # rules/security.md
    sec_path = os.path.join(SRC, "rules", "security.md")
    if os.path.isfile(sec_path):
        with open(sec_path, encoding="utf-8") as f:
            variables["{{RULES_SECURITY}}"] = f.read()

    # templates/
    for tpl_name in ("WORKFLOW", "PROJECT", "TECH", "BOT"):
        tpl_path = os.path.join(SRC, "templates", f"{tpl_name}.md")
        if os.path.isfile(tpl_path):
            with open(tpl_path, encoding="utf-8") as f:
                variables[f"{{{{TEMPLATE_{tpl_name}}}}}"] = f.read()

    return variables


def substitute_variables(content: str, variables: dict) -> str:
    """Replace all {{VAR}} placeholders with their content."""
    for placeholder, value in variables.items():
        content = content.replace(placeholder, value)
    return content


def clean_platform_dir(platform: str):
    """Remove dist/<platform>/ if it exists."""
    path = os.path.join(DIST, platform)
    if os.path.isdir(path):
        shutil.rmtree(path)


def run_format(input_path: str, platform: str, output_path: str, variables: dict) -> bool:
    """Run format.py to convert a Markdown file to a platform format.

    Before passing to format.py, substitute template variables in the input file
    by writing a temporary file with resolved content.
    """
    # Read input, substitute variables
    with open(input_path, encoding="utf-8") as f:
        content = f.read()
    content = substitute_variables(content, variables)

    # Write to a temp file for format.py to consume
    tmp_path = input_path + ".tmp.resolved"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)

    ext = ".md"
    style = "markdown"

    cmd = [
        sys.executable, FORMAT_SCRIPT,
        tmp_path, platform,
        "--style", style,
        "--output", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Clean up temp file
    os.remove(tmp_path)

    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}", file=sys.stderr)
        return False

    rel_in = os.path.relpath(input_path, ROOT)
    rel_out = os.path.relpath(output_path, ROOT)
    print(f"  {rel_in} -> {rel_out}")
    return True


def build_platform(platform: str) -> int:
    """Build dist/<platform>/ from src/. Returns file count."""
    base = os.path.join(DIST, platform)
    total = 0

    # Load template variables once per platform
    variables = load_template_variables()

    # Convert agents and tools via format.py with variable substitution
    agents_src = os.path.join(SRC, "agents")
    agents_dst = os.path.join(base, "agents")
    if os.path.isdir(agents_src):
        os.makedirs(agents_dst, exist_ok=True)
        for fname in sorted(os.listdir(agents_src)):
            if fname.endswith(".md"):
                if run_format(
                    os.path.join(agents_src, fname),
                    platform,
                    os.path.join(agents_dst, fname),
                    variables,
                ):
                    total += 1

    tools_src = os.path.join(SRC, "tools")
    tools_dst = os.path.join(base, "tools")
    if os.path.isdir(tools_src):
        os.makedirs(tools_dst, exist_ok=True)
        for fname in sorted(os.listdir(tools_src)):
            if fname.endswith(".md"):
                if run_format(
                    os.path.join(tools_src, fname),
                    platform,
                    os.path.join(tools_dst, fname),
                    variables,
                ):
                    total += 1

    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "platform",
        nargs="?",
        choices=ALL_PLATFORMS,
        help="Build only this platform (default: all)",
    )
    args = parser.parse_args()

    platforms = [args.platform] if args.platform else ALL_PLATFORMS

    print("Building dist/ from src/")

    total = 0

    for platform in platforms:
        print(f"\n[{platform}]")
        clean_platform_dir(platform)
        total += build_platform(platform)

    print(f"\nDone. {total} file(s) processed.")


if __name__ == "__main__":
    main()
