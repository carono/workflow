#!/usr/bin/env python3
"""
Анализирует logs/agent_summary.log и показывает топ тяжёлых вызовов.
Использование: python scripts/agent_report.py [--last N]
"""

import os
import sys
from collections import defaultdict

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
SUMMARY_LOG = os.path.join(LOG_DIR, "agent_summary.log")
SESSION_LOG = os.path.join(LOG_DIR, "agent_session.log")

def main():
    last_n = None
    if "--last" in sys.argv:
        idx = sys.argv.index("--last")
        last_n = int(sys.argv[idx + 1])

    if not os.path.exists(SUMMARY_LOG):
        print("Лог не найден. Запустите агента с включёнными хуками.")
        return

    with open(SUMMARY_LOG, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    if last_n:
        lines = lines[-last_n:]

    if not lines:
        print("Лог пустой.")
        return

    entries = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        ts, tool, chars, tokens = parts[0], parts[1], int(parts[2]), int(parts[3])
        entries.append((ts, tool, chars, tokens))

    total_out_tokens = sum(e[3] for e in entries)

    # Топ по размеру ответа
    by_tokens = sorted(entries, key=lambda x: x[3], reverse=True)

    print(f"\n{'='*60}")
    print(f"Всего вызовов: {len(entries)}")
    print(f"Суммарный объём ответов: ~{total_out_tokens} токенов")
    print(f"{'='*60}")

    print(f"\nТОП-15 тяжёлых вызовов (по размеру ответа):")
    print(f"{'Время':<10} {'Инструмент':<35} {'Токены':>8}")
    print("-" * 60)
    for ts, tool, chars, tokens in by_tokens[:15]:
        bar = "█" * min(30, tokens // 500)
        print(f"{ts:<10} {tool:<35} {tokens:>8}  {bar}")

    # Агрегация по инструменту
    print(f"\nАгрегация по инструменту:")
    print(f"{'Инструмент':<35} {'Вызовов':>8} {'Токенов итого':>14} {'Среднее':>10}")
    print("-" * 70)
    by_tool: dict = defaultdict(lambda: {"count": 0, "tokens": 0})
    for _, tool, _, tokens in entries:
        by_tool[tool]["count"] += 1
        by_tool[tool]["tokens"] += tokens
    for tool, stat in sorted(by_tool.items(), key=lambda x: x[1]["tokens"], reverse=True):
        avg = stat["tokens"] // stat["count"]
        print(f"{tool:<35} {stat['count']:>8} {stat['tokens']:>14} {avg:>10}")

    print(f"\nПодробный лог: {SESSION_LOG}")

if __name__ == "__main__":
    main()
