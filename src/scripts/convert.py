#!/usr/bin/env python3
"""Convert Claude Code agent .md files to JSON format.

Parses frontmatter (name, description, tools) and body (instructions)
from .md files and writes corresponding .json files.

Usage:
    python convert.py <input_dir> <output_dir>

Example:
    python convert.py dist/agents src/agents
    python convert.py dist/tools src/tools
"""

import json
import os
import re
import sys


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML-like frontmatter from markdown content.

    Returns (metadata_dict, remaining_body).
    """
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        raise ValueError("No frontmatter found (missing --- delimiters)")

    raw_meta, body = match.group(1), match.group(2).lstrip('\n')
    meta: dict[str, str] = {}

    for line in raw_meta.splitlines():
        if ':' not in line:
            continue
        key, _, value = line.partition(':')
        meta[key.strip()] = value.strip()

    return meta, body


def parse_tools(raw: str) -> list[str]:
    """Parse comma-separated tools string into a list."""
    return [t.strip() for t in raw.split(',') if t.strip()]


def convert_md_to_json(md_content: str) -> dict:
    """Convert a single agent markdown file content to JSON dict."""
    meta, instructions = parse_frontmatter(md_content)

    tools = parse_tools(meta.get('tools', ''))

    return {
        'name': meta.get('name', ''),
        'description': meta.get('description', ''),
        'tools': tools,
        'instructions': instructions,
    }


def convert_file(input_path: str, output_path: str) -> None:
    """Convert a single .md file to .json."""
    with open(input_path, encoding='utf-8') as f:
        md_content = f.read()

    data = convert_md_to_json(md_content)

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')

    print(f"  {os.path.basename(input_path)} -> {os.path.basename(output_path)}")


def convert_directory(input_dir: str, output_dir: str) -> None:
    """Convert all .md files in input_dir to .json files in output_dir."""
    if not os.path.isdir(input_dir):
        print(f"Error: input directory does not exist: {input_dir}", file=sys.stderr)
        sys.exit(1)

    md_files = sorted(f for f in os.listdir(input_dir) if f.endswith('.md'))
    if not md_files:
        print(f"No .md files found in {input_dir}")
        return

    os.makedirs(output_dir, exist_ok=True)
    print(f"Converting {len(md_files)} file(s) from {input_dir} to {output_dir}")

    for md_file in md_files:
        input_path = os.path.join(input_dir, md_file)
        json_file = md_file[:-3] + '.json'
        output_path = os.path.join(output_dir, json_file)
        convert_file(input_path, output_path)

    print(f"Done. {len(md_files)} file(s) converted.")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    convert_directory(input_dir, output_dir)


if __name__ == '__main__':
    main()
