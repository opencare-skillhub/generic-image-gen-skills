#!/usr/bin/env python3
"""生图接口适配器。

5 种 adapter：openai_images / openai_chat / dashscope / generic / builtin。
只用标准库；代理按渠道的 proxy 字段生效。
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

BUILTIN_SIGNAL = "builtin-handoff"


def _opener(proxy: str):
    if proxy:
        return urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener()


def _post(url: str, payload: dict, headers: dict, timeout: float, proxy: str):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with _opener(proxy).open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def _save_b64(payload: bytes, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    return True


def _save_url(url: str, out: Path, proxy: str, timeout: float):
    out.parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("data:"):
        return _save_b64(base64.b64decode(url.split(",", 1)[1]), out)
    with _opener(proxy).open(urllib.request.Request(url), timeout=timeout) as resp:
        return _save_b64(resp.read(), out)


def _first_image(payload: dict) -> str:
    for item in payload.get("data") or []:
        if item.get("b64_json"):
            return "data:image/png;base64," + item["b64_json"]
        if item.get("url"):
            return item["url"]
    for item in payload.get("images") or []:
        if isinstance(item, dict) and item.get("url"):
            return item["url"]
    return ""


def clamp_size(size: str, max_side: int) -> str:
    try:
        w, h = (int(x) for x in str(size).lower().split("x"))
    except Exception:
        return size
    scale = min(1.0, (max_side - 1) / max(w, h))
    if scale < 1.0:
        w, h = int(w * scale) // 8 * 8, int(h * scale) // 8 * 8
    return f"{max(w, 8)}x{max(h, 8)}"


# ---------------------------------------------------------------- adapters
def gen_openai_images(ch: dict, req: dict) -> bool:
    payload = {
        "model": req["model"],
        "prompt": req["prompt"],
        "n": req.get("n", 1),
        "size": req["size"],
        "response_format": "b64_json",
    }
    if ch["caps"].get("negative_prompt") and req.get("negative"):
        payload["negative_prompt"] = req["negative"]
    if ch["caps"].get("seed") and req.get("seed") is not None:
        payload["seed"] = req["seed"]
    data = _post(
        f"{ch['base_url']}/images/generations",
        payload,
        {"Authorization": f"Bearer {ch['key']}", "Content-Type": "application/json"},
        req["timeout"],
        ch.get("proxy", ""),
    )
    url = _first_image(data)
    return bool(url) and _save_url(url, req["out"], ch.get("proxy", ""), req["timeout"])


def gen_openai_chat(ch: dict, req: dict) -> bool:
    message = {"role": "user", "content": req["prompt"]}
    payload = {
        "model": req["model"],
        "messages": [message],
        "modalities": ["image", "text"],
    }
    if req.get("reference_image"):
        payload["messages"] = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": req["prompt"]},
                    {"type": "image_url", "image_url": {"url": req["reference_image"]}},
                ],
            }
        ]
    data = _post(
        f"{ch['base_url']}/chat/completions",
        payload,
        {"Authorization": f"Bearer {ch['key']}", "Content-Type": "application/json"},
        req["timeout"],
        ch.get("proxy", ""),
    )
    if data.get("error"):
        raise RuntimeError(json.dumps(data["error"])[:200])
    msg = ((data.get("choices") or [{}])[0]).get("message", {})
    for img in msg.get("images") or []:
        url = (img.get("image_url") or {}).get("url", "")
        if url:
            return _save_url(url, req["out"], ch.get("proxy", ""), req["timeout"])
    for part in msg.get("content") or []:
        if isinstance(part, dict) and part.get("type") == "image_url":
            url = (part.get("image_url") or {}).get("url", "")
            if url:
                return _save_url(url, req["out"], ch.get("proxy", ""), req["timeout"])
    return False


def gen_dashscope(ch: dict, req: dict) -> bool:
    params = {
        "size": req["size"].replace("x", "*"),
        "prompt_extend": False,
        "watermark": False,
        "n": req.get("n", 1),
    }
    if req.get("negative"):
        params["negative_prompt"] = req["negative"]
    payload = {
        "model": req["model"],
        "input": {"messages": [{"role": "user", "content": [{"text": req["prompt"]}]}]},
        "parameters": params,
    }
    data = _post(
        f"{ch['base_url']}/api/v1/services/aigc/multimodal-generation/generation",
        payload,
        {"Authorization": f"Bearer {ch['key']}", "Content-Type": "application/json"},
        req["timeout"],
        ch.get("proxy", ""),
    )
    if data.get("code"):
        raise RuntimeError(f"{data.get('code')}: {str(data.get('message'))[:160]}")
    content = data["output"]["choices"][0]["message"]["content"]
    url = next((c.get("image") for c in content if isinstance(c, dict) and c.get("image")), "")
    return bool(url) and _save_url(url, req["out"], ch.get("proxy", ""), req["timeout"])


def gen_generic(ch: dict, req: dict) -> bool:
    spec = ch.get("generic") or {}
    payload = json.loads(json.dumps(spec.get("request_template") or {}).replace("${prompt}", req["prompt"]).replace("${model}", req["model"]).replace("${size}", req["size"]))
    data = _post(
        spec.get("url") or ch["base_url"],
        payload,
        {"Authorization": f"Bearer {ch['key']}", "Content-Type": "application/json"},
        req["timeout"],
        ch.get("proxy", ""),
    )
    node = data
    for part in str(spec.get("response_jsonpath") or "").split("."):
        if not part:
            continue
        if isinstance(node, list):
            node = node[int(part)] if part.lstrip("-").isdigit() else node[0]
        else:
            node = (node or {}).get(part)
    if isinstance(node, str) and node:
        return _save_url(node, req["out"], ch.get("proxy", ""), req["timeout"])
    return False


def gen_builtin(ch: dict, req: dict) -> bool:
    raise BuiltinHandoff()


class BuiltinHandoff(Exception):
    """交由宿主自身出图。img.py 捕获后打印 handoff JSON 并以退出码 10 结束。"""


ADAPTERS = {
    "openai_images": gen_openai_images,
    "openai_chat": gen_openai_chat,
    "dashscope": gen_dashscope,
    "generic": gen_generic,
    "builtin": gen_builtin,
}


def run(ch: dict, req: dict) -> bool:
    fn = ADAPTERS.get(ch["adapter"])
    if not fn:
        raise RuntimeError(f"未知 adapter: {ch['adapter']}")
    return fn(ch, req)
