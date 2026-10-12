#!/usr/bin/env python3
"""极简 YAML 子集解析器。

只支持本技能配置用到的语法：注释、缩进映射、`- ` 列表、行内 `[a, b]` 与 `{k: v}`、
引号字符串、整数/浮点/布尔/null。不支持锚点、块标量、多文档。

有 PyYAML 时由 resolve 优先使用 PyYAML；本模块是零依赖回退路径。
"""
from __future__ import annotations


def _split_flow(text: str) -> list[str]:
    parts, buf, depth, quote = [], [], 0, ""
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _scalar(token: str):
    t = token.strip()
    if t in ("", "~", "null", "Null", "NULL"):
        return None
    low = t.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        return t[1:-1]
    if t.startswith("[") and t.endswith("]"):
        return [_scalar(x) for x in _split_flow(t[1:-1])] if t[1:-1].strip() else []
    if t.startswith("{") and t.endswith("}"):
        out = {}
        for item in _split_flow(t[1:-1]):
            if ":" in item:
                k, v = item.split(":", 1)
                out[str(_scalar(k))] = _scalar(v)
        return out
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    return t


def _lines(text: str) -> list[tuple[int, str]]:
    out = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stripped = raw.lstrip(" \t")
        if stripped.startswith("#"):
            continue
        out.append((len(raw) - len(raw.lstrip(" ")), stripped))
    return out


def _parse_block(lines: list[tuple[int, str]], i: int, indent: int):
    if i >= len(lines):
        return {}, i
    if lines[i][1].startswith("- ") or lines[i][1] == "-":
        return _parse_list(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines: list[tuple[int, str]], i: int, indent: int):
    out: dict = {}
    n = len(lines)
    while i < n:
        cur_indent, content = lines[i]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError(f"缩进异常（第 {i + 1} 行）: {content}")
        if content.startswith("- "):
            break
        if content[:1] in ("\"", "'"):
            q = content[0]
            end = content.find(q, 1)
            if end < 0 or content[end + 1 : end + 2] != ":":
                raise ValueError(f"带引号的键后缺少冒号（第 {i + 1} 行）: {content}")
            key = _scalar(content[: end + 1])
            rest = content[end + 2 :].strip()
        elif ":" not in content:
            raise ValueError(f"缺少冒号（第 {i + 1} 行）: {content}")
        else:
            key, rest = content.split(":", 1)
            key = str(_scalar(key))
            rest = rest.strip()
        if rest:
            out[key] = _scalar(rest)
            i += 1
            continue
        nxt = lines[i + 1] if i + 1 < n else None
        if nxt and nxt[0] > indent:
            out[key], i = _parse_block(lines, i + 1, nxt[0])
        elif nxt and nxt[0] == indent and (nxt[1].startswith("- ") or nxt[1] == "-"):
            out[key], i = _parse_list(lines, i + 1, indent)
        else:
            out[key] = None
            i += 1
    return out, i


def _parse_list(lines: list[tuple[int, str]], i: int, indent: int):
    out: list = []
    n = len(lines)
    while i < n:
        cur_indent, content = lines[i]
        if cur_indent < indent or not (content.startswith("- ") or content == "-"):
            break
        item_src = content[2:].strip() if content.startswith("- ") else ""
        item_indent = cur_indent + 2
        if not item_src:
            nxt = lines[i + 1] if i + 1 < n else None
            if nxt and nxt[0] > cur_indent:
                value, i = _parse_block(lines, i + 1, nxt[0])
                out.append(value)
                continue
            out.append(None)
            i += 1
            continue
        if item_src[:1] in ("\"", "'"):
            out.append(_scalar(item_src))
            i += 1
            continue
        if ":" in item_src and not item_src.startswith(("http://", "https://")):
            key, rest = item_src.split(":", 1)
            key = str(_scalar(key))
            rest = rest.strip()
            node: dict = {key: _scalar(rest) if rest else None}
            i += 1
            while i < n and lines[i][0] > cur_indent:
                sub, i = _parse_map(lines, i, lines[i][0])
                node.update(sub)
                break
            out.append(node)
            continue
        out.append(_scalar(item_src))
        i += 1
    return out, i


def safe_load(text: str):
    """解析 YAML 文本。返回 dict / list / 标量。"""
    lines = _lines(text)
    if not lines:
        return {}
    value, _ = _parse_block(lines, 0, lines[0][0])
    return value


def load(path: str):
    from pathlib import Path

    return safe_load(Path(path).read_text(encoding="utf-8"))
