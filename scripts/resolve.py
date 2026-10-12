#!/usr/bin/env python3
"""配置解析、凭据解析链、渠道选取与 --explain。

用法（主要被 img.py 调用，也可单独诊断）：
  resolve.py --list-channels [--explain]
  resolve.py --profile hq [--explain]
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

LATENCY_RANK = {"low": 0, "mid": 1, "high": 2}
QUALITY_RANK = {"low": 0, "mid": 1, "high": 2}
PLAIN_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


# ---------------------------------------------------------------- 配置加载
def _load_yaml(path: Path):
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        import miniyaml

        return miniyaml.safe_load(text)


def deep_merge(base, override):
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for k, v in override.items():
            out[k] = deep_merge(base.get(k), v) if k in base else v
        return out
    return override if override is not None else base


def merge_channels(base: list, override: list) -> list:
    """按 id 合并渠道列表；override 中没有的 id 原样保留。"""
    out = [dict(c) for c in base]
    index = {c.get("id"): i for i, c in enumerate(out)}
    for c in override or []:
        cid = c.get("id")
        if cid in index:
            out[index[cid]] = deep_merge(out[index[cid]], c)
        else:
            out.append(dict(c))
    return out


def load_config(root: Path = ROOT) -> dict:
    cfg = _load_yaml(root / "config" / "default.yaml")
    channels = _load_yaml(root / "config" / "channels.yaml")
    cfg["_channels"] = channels.get("channels", [])
    user_path = root / "config" / "user.yaml"
    cfg["_user_path"] = user_path
    if user_path.exists():
        user = _load_yaml(user_path) or {}
        if user.get("channels"):
            cfg["_channels"] = merge_channels(cfg["_channels"], user["channels"])
        for key, value in user.items():
            if key == "channels":
                continue
            cfg[key] = deep_merge(cfg.get(key), value)
    cfg["_user_credentials"] = cfg.get("credentials") or {}
    return cfg


# ---------------------------------------------------------------- 变量展开
def expand(value, ctx: dict):
    if isinstance(value, str):
        m = PLAIN_RE.fullmatch(value.strip())
        if m:
            name, default = m.group(1), m.group(2)
            return ctx.get(name) or os.environ.get(name) or (default or "")
        return PLAIN_RE.sub(
            lambda mo: str(ctx.get(mo.group(1)) or os.environ.get(mo.group(1)) or mo.group(2) or ""),
            value,
        )
    if isinstance(value, list):
        return [expand(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: expand(v, ctx) for k, v in value.items()}
    return value


# ---------------------------------------------------------------- 凭据发现
def _json_file(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def discover_key(channel: dict) -> tuple[str, str]:
    """从本机已配置的模型管理里发现可用 key。返回 (key, source)。"""
    base = str(channel.get("base_url") or "")
    host = ""
    if "://" in base:
        host = base.split("://", 1)[1].split("/", 1)[0]
    cid = str(channel.get("id", "")).lower()

    models = _json_file(Path.home() / ".workbuddy" / "models.json")
    if isinstance(models, list):
        for item in models:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            vendor = str(item.get("vendor") or "").lower()
            key = str(item.get("apiKey") or "")
            if not key:
                continue
            if (host and host in url) or (cid and (cid in vendor or cid in url.lower())):
                return key, "~/.workbuddy/models.json"

    claw = _json_file(Path.home() / ".openclaw" / "openclaw.json")
    if isinstance(claw, dict):
        providers = ((claw.get("models") or {}).get("providers") or {})
        for name, prov in providers.items():
            if not isinstance(prov, dict):
                continue
            key = str(prov.get("apiKey") or "")
            if not key:
                continue
            if cid and (cid in str(name).lower() or cid in str(prov.get("baseUrl") or "").lower()):
                return key, "~/.openclaw/openclaw.json"
    return "", ""


def channel_key(channel: dict, cfg: dict, overrides: dict) -> tuple[str, str]:
    cid = str(channel.get("id", ""))
    if cid in overrides:
        return str(overrides[cid]), "--set"
    user_cred = cfg.get("_user_credentials") or {}
    if cid in user_cred and user_cred[cid]:
        return str(user_cred[cid]), "config/user.yaml"
    raw = ((channel.get("auth") or {}).get("key")) or ""
    ctx = dict(overrides)
    value = expand(raw, ctx)
    if isinstance(value, str) and value.strip() and not PLAIN_RE.search(value):
        return value.strip(), "环境变量"
    found, source = discover_key(channel)
    if found:
        return found, source
    return "", ""


# ---------------------------------------------------------------- 渠道求值
def normalize_channel(ch: dict, cfg: dict, overrides: dict) -> dict:
    cid = str(ch.get("id", ""))
    key, source = channel_key(ch, cfg, overrides)
    base = expand(ch.get("base_url") or "", dict(overrides)) or ch.get("base_url_default") or ""
    models = ch.get("model") or {}
    return {
        "id": cid,
        "adapter": ch.get("adapter"),
        "enabled": ch.get("enabled", "auto"),
        "base_url": str(base).rstrip("/"),
        "model_default": expand(models.get("default"), dict(overrides)) or ch.get("model_default") or "",
        "model_hq": expand(models.get("hq"), dict(overrides)) or ch.get("model_default") or "",
        "proxy": expand(ch.get("proxy") or "", dict(overrides)) or "",
        "caps": ch.get("caps") or {},
        "cost": ch.get("cost", 1.0),
        "latency": ch.get("latency", "mid"),
        "quality": ch.get("quality", "mid"),
        "region": ch.get("region", "global"),
        "tags": ch.get("tags") or [],
        "key": key,
        "key_source": source,
        "note": ch.get("note", ""),
    }


def usable(ch: dict) -> tuple[bool, str]:
    if ch.get("enabled") is False:
        return False, "已停用"
    if ch["adapter"] == "builtin":
        return True, "无需凭据"
    if not ch.get("base_url"):
        return False, "缺 base_url"
    if not ch.get("key"):
        return False, "缺凭据"
    if not ch.get("model_default"):
        return False, "缺模型"
    return True, "可用"


def evaluate(cfg: dict, overrides: dict) -> list[dict]:
    out = []
    for raw in cfg["_channels"]:
        ch = normalize_channel(raw, cfg, overrides)
        ok, reason = usable(ch)
        ch["usable"] = ok
        ch["reason"] = reason
        out.append(ch)
    return out


# ---------------------------------------------------------------- 选路
def profile_of(cfg: dict, name: str) -> dict:
    return (cfg.get("profiles") or {}).get(name) or (cfg.get("profiles") or {}).get("default") or {}


def _match_filter(ch: dict, flt: dict) -> tuple[bool, str]:
    if not flt:
        return True, ""
    tags = flt.get("tags") or []
    if tags and not any(t in ch["tags"] for t in tags):
        return False, f"标签 {ch['tags']} 不含任一 {tags}"
    for key, want in (flt.get("caps") or {}).items():
        if ch["caps"].get(key) != want:
            return False, f"{key}={ch['caps'].get(key)}，需要 {want}"
    if flt.get("region") and ch["region"] != flt["region"]:
        return False, f"region={ch['region']}，需要 {flt['region']}"
    return True, ""


def _sort_key(ch: dict, sort: list, need_text: bool = False):
    keys = []
    if need_text:
        keys.append(0 if ch["caps"].get("text_rendering") == "strong" else 1)
    for item in sort or ["cost asc"]:
        parts = item.split()
        field = parts[0]
        desc = len(parts) > 1 and parts[1] == "desc"
        if field == "cost":
            val = float(ch.get("cost", 1.0))
        elif field == "latency":
            val = LATENCY_RANK.get(ch.get("latency", "mid"), 1)
        elif field == "quality":
            val = QUALITY_RANK.get(ch.get("quality", "mid"), 1)
        else:
            val = 0
        keys.append(-val if desc else val)
    return tuple(keys)


def builtin_skips(cfg: dict, opts: dict) -> list[str]:
    rules = cfg.get("builtin") or {}
    skip_when = rules.get("skip_when") or []
    hits = []
    if "reference_image" in skip_when and opts.get("ref"):
        hits.append("reference_image（需要垫参考图）")
    if "seed" in skip_when and opts.get("seed") is not None:
        hits.append("seed（需要复现）")
    if "n_gt_1" in skip_when and int(opts.get("n") or 1) > 1:
        hits.append("n_gt_1（需要多张）")
    if "negative_prompt" in skip_when and (opts.get("negative") or "").strip():
        hits.append("negative_prompt（需要负面词）")
    if "nonstandard_size" in skip_when and opts.get("nonstandard_size"):
        hits.append("nonstandard_size（比例超出内置能力）")
    return hits


def select_chain(cfg: dict, channels: list[dict], profile: str, opts: dict) -> tuple[list[dict], list[str]]:
    """返回 (回退链, 解释行)。"""
    spec = profile_of(cfg, profile)
    flt = spec.get("filter") or {}
    sort = spec.get("sort") or ["cost asc"]
    max_attempts = int(spec.get("max_attempts") or 4)
    log = [f"profile={profile}  filter={flt or '{}'}  sort={sort}"]

    picked, skipped = [], []
    bch = None
    for ch in channels:
        if ch["adapter"] == "builtin":
            bch = ch
            continue
        ok_use, reason = usable(ch)
        if not ok_use:
            log.append(f"  - {ch['id']}: 跳过（{reason}）")
            continue
        matched, why = _match_filter(ch, flt)
        if not matched:
            log.append(f"  - {ch['id']}: 不匹配 profile（{why}）")
            skipped.append(ch)
            continue
        picked.append(ch)
        log.append(f"  - {ch['id']}: 入选（cost={ch['cost']} latency={ch['latency']} quality={ch['quality']}）")
    picked.sort(key=lambda c: _sort_key(c, sort, bool(opts.get("need_text"))))
    chain = picked[:max_attempts]

    builtin_cfg = cfg.get("builtin") or {}
    mode = str(builtin_cfg.get("mode") or "auto").lower()
    if bch:
        hits = [] if opts.get("force_builtin") else builtin_skips(cfg, opts)
        if hits:
            chain = [c for c in chain if c is not bch]
            log.append(f"  - builtin: 跳过（命中 skip_when: {'; '.join(hits)}）")
        elif mode == "off" and not opts.get("force_builtin"):
            chain = [c for c in chain if c is not bch]
            log.append("  - builtin: 关闭（builtin.mode=off）")
        elif opts.get("force_builtin"):
            chain = [bch] + [c for c in chain if c is not bch]
            hits = builtin_skips(cfg, opts)
            warn = f"；已显式指定，仍将跳过的能力：{'; '.join(hits)}" if hits else ""
            log.append(f"  - builtin: 置顶（--channel builtin 显式指定）{warn}")
        elif mode == "last" or (mode == "auto" and any(c["adapter"] != "builtin" for c in chain)):
            chain = [c for c in chain if c is not bch] + [bch]
            log.append("  - builtin: 排到末尾（已有可用凭据，内置兜底）")
        else:
            chain = [bch] + [c for c in chain if c is not bch]
            log.append("  - builtin: 置顶（本机无可用凭据，内置保底）")
    elif mode in ("auto", "first"):
        any_key = any(c["usable"] and c["adapter"] != "builtin" for c in channels)
        if not any_key:
            pool = [c for c in channels if c["adapter"] == "builtin"]
            if pool:
                chain = pool + chain
                log.append("  - builtin: 置顶（本机无可用凭据，内置保底）")

    log.append(f"最终链: {' -> '.join(c['id'] for c in chain) or '（空）'}")
    return chain, log


# ---------------------------------------------------------------- CLI
def main() -> int:
    ap = argparse.ArgumentParser(description="image-gen 配置与渠道诊断")
    ap.add_argument("--profile", default="default")
    ap.add_argument("--list-channels", action="store_true")
    ap.add_argument("--explain", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    channels = evaluate(cfg, {})
    chain, log = select_chain(cfg, channels, args.profile, {})
    if args.json:
        print(json.dumps({"channels": channels, "chain": [c["id"] for c in chain], "log": log}, ensure_ascii=False, indent=2))
        return 0
    for ch in channels:
        flag = "可用" if ch["usable"] else "不可用"
        src = ch["key_source"] or "—"
        print(f"{ch['id']:<12} {ch['adapter']:<14} {flag:<6} 凭据来源={src:<28} {ch['reason']}")
    print()
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
