#!/usr/bin/env python3
"""v0.1 兼容入口，已由 img.py 取代。

旧参数映射：--prompt / --out / --size / --negative / --seed / --timeout 原样转发；
--backend X → --channel X；--hq / --quality high → --profile hq；--env / --proxy 忽略。
新写法见 SKILL.md。本 wrapper 只做转发，不再维护后端链。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PASSTHRU = ("--prompt", "--out", "--size", "--negative", "--seed", "--timeout")


def translate(argv: list[str]) -> list[str]:
    out: list[str] = []
    backend = ""
    profile = ""
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--backend":
            backend = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
            continue
        if a in ("--hq",):
            profile = "hq"
            i += 1
            continue
        if a == "--quality":
            profile = "hq"
            i += 2
            continue
        if a in ("--env", "--proxy"):
            i += 2
            continue
        out.append(a)
        if a in PASSTHRU and i + 1 < len(argv):
            out.append(argv[i + 1])
            i += 2
            continue
        i += 1
    if profile:
        out += ["--profile", profile]
    if backend and backend not in ("auto", ""):
        out += ["--channel", backend]
    return out


def main() -> int:
    print("[deprecated] gen.py 已由 img.py 取代，参数已自动转发。", file=sys.stderr)
    return subprocess.run([sys.executable, str(HERE / "img.py"), *translate(sys.argv[1:])]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
