#!/usr/bin/env python3
"""image-gen 唯一入口：场景 → 提示词 → 选渠道 → 出图 → 后处理。

命令：
  img.py --theme "主题" [--scene 配图] [--style 042] [--color C-07] [--out /abs/o.png]
  img.py --prompt-spec spec.json --out /abs/o.png
  img.py --scene infographic --html /abs/page.html --out /abs/o.png
  img.py compose --theme "主题" --style 042          # 只出提示词
  img.py list [--scenes|--styles|--channels]        # 列出可用项
  img.py doctor                                     # 环境自检
  img.py init [--apply]                             # 生成 config/user.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import adapters  # noqa: E402
import compose as C  # noqa: E402
import postprocess as PP  # noqa: E402
import resolve as R  # noqa: E402

EXIT_OK, EXIT_FAIL, EXIT_ARG, EXIT_BUILTIN = 0, 1, 2, 10


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="img.py", description="image-gen 出图入口")
    sub = ap.add_subparsers(dest="cmd")

    def common(p: argparse.ArgumentParser):
        p.add_argument("--scene", help="场景 id 或别名，见 img.py list --scenes")
        p.add_argument("--theme", help="画面主题")
        p.add_argument("--text", help="要渲染进画面的文字（仅 allow_text 场景：海报/封面/社媒卡等）")
        p.add_argument("--prompt", help="直接给最终提示词，跳过组装")
        p.add_argument("--prompt-file", help="从文件读最终提示词")
        p.add_argument("--prompt-spec", help="prompt-spec JSON，见 references/prompt-contract.md")
        p.add_argument("--style", help="风格编号（外挂包）或内置风格族名")
        p.add_argument("--color", help="主题色编号，如 C-07")
        p.add_argument("--layout", help="版式编号，如 SC-001")
        p.add_argument("--type", help="构图类型：portrait/full-body/scene/closeup/top-down/metaphor")
        p.add_argument("--mode", help="pure-image 或 graphic-text")
        p.add_argument("--pack", default="handraw", help="外挂风格包名")
        p.add_argument("--negative", help="覆盖场景默认负面词")
        p.add_argument("--extra", help="追加到提示词的补充要求")
        p.add_argument("--ref", help="参考图绝对路径（垫图）")
        p.add_argument("--ratio", help="比例，如 16:9")
        p.add_argument("--size", help="显式尺寸 WxH，优先于 --ratio")
        p.add_argument("--out", help="输出路径（.png/.jpg/.webp）")
        p.add_argument("--n", type=int, default=1, help="出图张数")
        p.add_argument("--seed", type=int, help="随机种子")
        p.add_argument("--profile", help="选路策略：default/cheap/fast/hq/zh-text/ref-image/local/builtin")
        p.add_argument("--channel", help="钉死渠道 id")
        p.add_argument("--model", help="钉死模型 id")
        p.add_argument("--set", action="append", default=[], help="覆盖凭据：--set siliconflow=sk-xxx")
        p.add_argument("--timeout", type=float, help="单请求超时秒数")
        p.add_argument("--post", help="后处理，逗号分隔：trim,resize")
        p.add_argument("--emit-prompt-only", action="store_true", help="只出提示词，不生图")
        p.add_argument("--dry-run", action="store_true", help="只打印计划")
        p.add_argument("--explain", action="store_true", help="打印选路解释")
        p.add_argument("--json", action="store_true", help="机器可读输出")

    common(ap)
    ap.add_argument("--scenes", action="store_true")
    ap.add_argument("--styles", action="store_true")
    ap.add_argument("--channels", action="store_true")
    ap.add_argument("--html", help="HTML 管线输入（infographic/diagram 场景）")
    ap.add_argument("--viewport", type=int, default=1100, help="HTML 渲染视口宽度")
    ap.add_argument("--out-width", type=int, default=1240, help="HTML 输出宽度")
    ap.add_argument("--apply", action="store_true", help="init 时真正写文件")

    p_compose = sub.add_parser("compose", help="只出提示词")
    common(p_compose)
    p_list = sub.add_parser("list", help="列出场景 / 风格 / 渠道")
    p_list.add_argument("--scenes", action="store_true")
    p_list.add_argument("--styles", action="store_true")
    p_list.add_argument("--channels", action="store_true")
    sub.add_parser("doctor", help="环境自检").add_argument("--net", action="store_true", help="带凭据做一次真实探测（会发起网络请求）")
    p_init = sub.add_parser("init", help="生成 config/user.yaml")
    p_init.add_argument("--apply", action="store_true")
    return ap


def overrides_from(args) -> dict:
    out = {}
    for item in getattr(args, "set", []) or []:
        if "=" in item:
            k, v = item.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def scene_id(cfg: dict, raw: str | None) -> str:
    scenes = cfg.get("scenes") or {}
    if not raw:
        return (cfg.get("defaults") or {}).get("scene", "article-illustration")
    if raw in scenes:
        return raw
    for sid, s in scenes.items():
        if raw in (s.get("aliases") or []):
            return sid
    return raw


def resolve_size(cfg: dict, ratio: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    presets = (cfg.get("output") or {}).get("ratio_presets") or {}
    wh = presets.get(ratio)
    return f"{wh[0]}x{wh[1]}" if wh else "1664x928"


def do_list(args, cfg: dict) -> int:
    if args.scenes:
        for sid, s in (cfg.get("scenes") or {}).items():
            print(f"{sid:<22} {s.get('ratio',''):<6} 文字={'允许' if s.get('allow_text') else '禁止':<4} 管线={s.get('pipeline')}  别名={','.join(s.get('aliases') or [])}")
        return EXIT_OK
    if args.styles:
        for k, v in (cfg.get("styles") or {}).items():
            print(f"{k:<18} {v.get('name_zh','')} / {v.get('name_en','')}")
        pack = C.discover_pack(cfg, "handraw")
        print(f"\n外挂风格包 handraw: {pack or '未发现'}")
        return EXIT_OK
    chans = R.evaluate(cfg, {})
    for ch in chans:
        state = "可用" if ch["usable"] else "不可用"
        print(f"{ch['id']:<12} {ch['adapter']:<14} {state:<6} 模型={ch['model_default'] or '—':<28} 凭据={ch['key_source'] or '—'}")
    return EXIT_OK


def _probe(ch: dict, timeout: float) -> str:
    """真实认证探测：带凭据 GET 一次模型列表。只有 --net 才会发起网络请求。"""
    import urllib.error
    import urllib.request

    opener = adapters._opener(ch.get("proxy", ""))
    for path in ("/models", "/v1/models"):
        try:
            req = urllib.request.Request(ch["base_url"] + path, headers={"Authorization": f"Bearer {ch['key']}"})
            with opener.open(req, timeout=timeout) as resp:
                return f"HTTP {resp.status}"
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403):
                return f"HTTP {exc.code}（凭据被拒或权限不足）"
            if exc.code == 404:
                continue
            return f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            return f"网络失败：{str(exc)[:80]}"
    return "未找到模型列表端点"


def do_doctor(cfg: dict, net: bool = False, timeout: float = 15.0) -> int:
    print(f"python: {sys.version.split()[0]}")
    print(f"skill root: {ROOT}")
    print(f"user.yaml: {'存在' if (ROOT / 'config' / 'user.yaml').exists() else '未生成（img.py init --apply）'}")
    print("\n== 渠道 ==")
    for ch in R.evaluate(cfg, {}):
        line = f"{ch['id']:<12} {'可用' if ch['usable'] else '不可用':<6} {ch['reason']}"
        if net and ch["usable"] and ch["adapter"] != "builtin":
            line += f"  探测：{_probe(ch, timeout)}"
        print(line)
    if not net:
        print("（加 --net 会带凭据做一次真实探测，会发起网络请求）")
    print(f"\nPillow（后处理需要）: {'已装' if PP.has_pillow() else '未装，trim/resize/sheet 会跳过'}")
    print("依赖清单检查: python3 scripts/check_environment.py（auth_probe 需宿主提供 --probe-results）")
    return EXIT_OK


def do_init(cfg: dict, apply: bool) -> int:
    defaults = cfg.get("defaults") or {}
    target = ROOT / "config" / "user.yaml"
    content = (
        "# image-gen 用户配置（只写要改的字段；本文件含凭据时不要提交到 git）\n"
        "defaults:\n"
        f"  scene: {defaults.get('scene','article-illustration')}\n"
        f"  profile: {defaults.get('profile','default')}\n"
        f"  ratio: \"{defaults.get('ratio','16:9')}\"\n"
        "\n"
        "# 凭据优先留在环境变量或 ~/.workbuddy/models.json；确实要写在这里时用：\n"
        "# credentials:\n"
        "#   siliconflow: sk-xxx\n"
    )
    print("== 已发现 ==")
    for ch in R.evaluate(cfg, {}):
        print(f"{ch['id']:<12} {'可用' if ch['usable'] else '不可用':<6} {ch['key_source'] or ch['reason']}")
    if apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"\n已写入 {target}")
    else:
        print(f"\n将写入 {target}：\n{content}（加 --apply 执行）")
    return EXIT_OK


def do_html(args, cfg: dict) -> int:
    if not args.html:
        print("HTML 场景需要 --html 指定输入文件", file=sys.stderr)
        return EXIT_ARG
    script = HERE / "html2png.sh"
    out = Path(args.out).expanduser() if args.out else Path((cfg.get("defaults") or {}).get("out_dir", "./output")) / f"{Path(args.html).stem}.png"
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    import subprocess

    proc = subprocess.run(
        ["bash", str(script), str(Path(args.html).resolve()), str(out), str(args.viewport), str(args.out_width)],
        capture_output=True,
        text=True,
    )
    print(proc.stdout.strip() or proc.stderr.strip())
    return EXIT_OK if proc.returncode == 0 and out.exists() else EXIT_FAIL


def do_generate(args, cfg: dict) -> int:
    overrides = overrides_from(args)
    sid = scene_id(cfg, args.scene or (cfg.get("defaults") or {}).get("scene"))
    scene = (cfg.get("scenes") or {}).get(sid) or {}

    req: dict = {"scene": sid}
    if args.prompt_spec:
        spec = json.loads(Path(args.prompt_spec).read_text(encoding="utf-8"))
        chan = spec.pop("channel", None) or {}
        if isinstance(chan, dict):
            args.profile = args.profile or chan.get("profile")
            args.channel = args.channel or chan.get("id")
            args.model = args.model or chan.get("model")
        req.update(spec)
    for key in ("theme", "text", "style", "color", "layout", "type", "mode", "extra", "negative", "ratio"):
        val = getattr(args, key, None)
        if val:
            req[key] = val
    if args.ref:
        req["reference_image"] = args.ref
    if args.model:
        req["model"] = args.model

    if args.prompt or args.prompt_file:
        final_prompt = args.prompt or Path(args.prompt_file).read_text(encoding="utf-8")
        composed = {
            "prompt": final_prompt,
            "prompt_zh": final_prompt,
            "negative": req.get("negative") or (cfg.get("negatives") or {}).get(scene.get("negative", "none"), ""),
            "ratio": req.get("ratio") or scene.get("ratio") or "16:9",
            "pipeline": scene.get("pipeline", "gen"),
            "reference_image": args.ref or "",
            "activation_source": "raw",
            "notes": [],
            "mode": req.get("mode", "pure-image"),
        }
    else:
        composed = C.compose(req, cfg)

    for note in composed.get("notes") or []:
        print(f"[note] {note}", file=sys.stderr)

    if getattr(args, "cmd", None) == "compose" or args.emit_prompt_only:
        if args.json:
            print(json.dumps(composed, ensure_ascii=False, indent=2))
        else:
            print(composed["prompt_zh"])
        return EXIT_OK

    if composed.get("pipeline") == "html":
        return do_html(args, cfg)

    ratio = composed.get("ratio") or "16:9"
    size = resolve_size(cfg, ratio, args.size)
    n = max(1, int(args.n or 1))
    timeout = float(args.timeout or (cfg.get("defaults") or {}).get("timeout") or 300)
    negative = composed.get("negative") or ""
    profile = args.profile or scene.get("prefer_profile") or (cfg.get("defaults") or {}).get("profile") or "default"

    channels = R.evaluate(cfg, overrides)
    if args.channel:
        channels = [c for c in channels if c["id"] == args.channel] or channels
        profile = "default"
    builtin_caps = (next((c for c in channels if c["id"] == "builtin"), {}) or {}).get("caps") or {}
    nonstandard = ratio not in (builtin_caps.get("ratios") or [ratio])
    opts = {
        "ref": args.ref,
        "seed": args.seed,
        "n": n,
        "negative": negative,
        "nonstandard_size": nonstandard,
        "need_text": bool(scene.get("allow_text")),
        "force_builtin": args.channel == "builtin",
    }
    chain, log = R.select_chain(cfg, channels, profile, opts)
    if args.explain:
        print("\n".join(log))

    if not chain:
        print("ERR: 没有可用渠道。先跑 img.py doctor 看缺什么，或用 --channel/--set 指定。", file=sys.stderr)
        return EXIT_FAIL

    out_base = Path(args.out).expanduser().resolve() if args.out else (
        Path((cfg.get("defaults") or {}).get("out_dir", "./output")).resolve() / f"{sid}-{int(time.time())}.png"
    )
    out_base.parent.mkdir(parents=True, exist_ok=True)

    plan = {
        "scene": sid,
        "size": size,
        "n": n,
        "profile": profile,
        "chain": [c["id"] for c in chain],
        "out": str(out_base),
        "prompt": composed["prompt_zh"],
        "negative": negative,
    }
    if args.dry_run or args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        if args.dry_run:
            return EXIT_OK

    paths = []
    for i in range(n):
        target = out_base if n == 1 else out_base.with_name(f"{out_base.stem}-{i + 1}{out_base.suffix}")
        last_err = ""
        for ch in chain:
            model = args.model or (ch["model_hq"] if profile == "hq" and ch["model_hq"] else ch["model_default"])
            try:
                ok = adapters.run(
                    ch,
                    {
                        "model": model,
                        "prompt": composed["prompt_zh"],
                        "negative": negative if ch["caps"].get("negative_prompt") else "",
                        "size": adapters.clamp_size(size, int(ch["caps"].get("max_side") or 2048)),
                        "n": 1,
                        "seed": args.seed,
                        "out": target,
                        "timeout": timeout,
                        "reference_image": composed.get("reference_image") or "",
                    },
                )
                if ok and target.exists():
                    print(f"OK {target} via {ch['id']}:{model}")
                    paths.append(target)
                    break
            except adapters.BuiltinHandoff:
                print(
                    json.dumps(
                        {
                            "action": "builtin_image_gen",
                            "prompt": composed["prompt_zh"],
                            "size": size,
                            "negative": negative,
                            "out": str(target),
                            "scene": sid,
                        },
                        ensure_ascii=False,
                    )
                )
                return EXIT_BUILTIN
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)[:200]
                print(f"  [{ch['id']}:{model}] {last_err}", file=sys.stderr)
        if not paths or len(paths) <= i:
            print(f"ERR: 出图失败 {target}（{last_err or '所有渠道均失败'}）", file=sys.stderr)

    if not paths:
        return EXIT_FAIL

    steps = args.post.split(",") if args.post else (scene.get("postprocess") or [])
    width = int(size.split("x")[0])
    for p in paths:
        for line in PP.apply(p, steps, width):
            print(line)
    if len(paths) > 1 and "sheet" in (steps or []):
        print(PP.sheet(paths, out_base.with_name(f"{out_base.stem}-sheet{out_base.suffix}")))
    if not args.json:
        for p in paths:
            print(f"OUT {p}")
    return EXIT_OK


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()
    cfg = R.load_config()

    if args.cmd == "list":
        return do_list(args, cfg)
    if args.cmd == "doctor":
        return do_doctor(cfg, getattr(args, "net", False))
    if args.cmd == "init":
        return do_init(cfg, args.apply)
    if args.cmd == "compose":
        return do_generate(args, cfg)
    return do_generate(args, cfg)


if __name__ == "__main__":
    raise SystemExit(main())
