#!/usr/bin/env python3
"""出图后处理：trim（裁白边）/ resize（统一宽度）/ sheet（多张拼对比图）。

需要 Pillow；缺失时按降级处理——跳过并打印原因，不中断出图。
"""
from __future__ import annotations

import sys
from pathlib import Path


def _pil():
    try:
        from PIL import Image  # type: ignore

        return Image
    except ImportError:
        return None


def has_pillow() -> bool:
    return _pil() is not None


def trim(path: Path) -> str:
    Image = _pil()
    if not Image:
        return "跳过 trim（未装 Pillow）"
    with Image.open(path) as im:
        im = im.convert("RGB")
        bg = im.getpixel((0, 0))
        width, height = im.size
        px = im.load()
        left = next((x for x in range(width) if any(px[x, y] != bg for y in range(0, height, max(1, height // 50)))), 0)
        right = next((x for x in range(width - 1, -1, -1) if any(px[x, y] != bg for y in range(0, height, max(1, height // 50)))), width - 1)
        top = next((y for y in range(height) if any(px[x, y] != bg for x in range(0, width, max(1, width // 50)))), 0)
        bottom = next((y for y in range(height - 1, -1, -1) if any(px[x, y] != bg for x in range(0, width, max(1, width // 50)))), height - 1)
        if right > left and bottom > top:
            im.crop((left, top, right + 1, bottom + 1)).save(path)
            return f"trim -> {right - left + 1}x{bottom - top + 1}"
    return "trim 无变化"


def resize(path: Path, width: int) -> str:
    Image = _pil()
    if not Image:
        return "跳过 resize（未装 Pillow）"
    with Image.open(path) as im:
        if im.width <= width:
            return "resize 无变化"
        ratio = width / im.width
        im.resize((width, int(im.height * ratio))).save(path)
        return f"resize -> {width}x{int(im.height * ratio)}"


def sheet(paths: list[Path], out: Path) -> str:
    Image = _pil()
    if not Image:
        return "跳过 sheet（未装 Pillow）"
    imgs = []
    for p in paths:
        with Image.open(p) as im:
            imgs.append(im.convert("RGB").copy())
    if not imgs:
        return "sheet 无输入"
    w = max(i.width for i in imgs)
    total_h = sum(int(i.height * w / i.width) for i in imgs)
    canvas = Image.new("RGB", (w, total_h), "white")
    y = 0
    for im in imgs:
        h = int(im.height * w / im.width)
        canvas.paste(im.resize((w, h)), (0, y))
        y += h
    canvas.save(out)
    return f"sheet -> {out} ({w}x{total_h})"


def apply(path: Path, steps: list[str], width: int = 0) -> list[str]:
    report = []
    for step in steps or []:
        name = step.split(":")[0].strip()
        if name == "trim":
            report.append(trim(path))
        elif name == "resize" and width:
            report.append(resize(path, width))
        else:
            report.append(f"未识别的后处理：{step}")
    return report


if __name__ == "__main__":
    target = Path(sys.argv[1])
    steps = sys.argv[2].split(",") if len(sys.argv) > 2 else []
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    for line in apply(target, steps, width):
        print(line)
