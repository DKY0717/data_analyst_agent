#!/usr/bin/env python3
"""Display a context window usage progress bar for Claude Code status line."""
import json
import sys

def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return

    ctx = data.get("context_window", {})
    used = ctx.get("used_percentage")

    if used is None:
        return

    # Progress bar: 20 segments wide
    bar_width = 20
    filled = round(used / 100 * bar_width)
    empty = bar_width - filled
    bar = "█" * filled + "░" * empty

    # Color: green < 60%, yellow 60-80%, red > 80%
    if used < 60:
        color = "\033[32m"  # green
    elif used < 80:
        color = "\033[33m"  # yellow
    else:
        color = "\033[31m"  # red

    reset = "\033[0m"

    print(f"Context {color}{bar}{reset} {used:.0f}%")

if __name__ == "__main__":
    main()