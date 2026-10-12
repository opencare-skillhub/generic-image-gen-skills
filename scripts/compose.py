#!/usr/bin/env python3
"""提示词组装：prompt-spec / 场景参数 → 最终生图提示词。

上游（handraw-style、renjian-guancha、文章生成器、任意提示词项目）产出 prompt-spec，
本模块负责把它编译成可直接送进生图接口的提示词。

用法：
  compose.py --spec spec.json [--model X] [--scene article-illustration] [--json]
  compose.py --theme "主题" --style 042 --color C-07 [--style-pack handraw]
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
import sys

sys.path.insert(0, str(HERE))
import resolve as R  # noqa: E402

ID_RE = re.compile(r"#\d{2,4}\b|\bC-\d{2}\b|\b(?:SC|IG|SB)-\d{2,4}\b")
NEGATIVE_MARKERS = ("避免", "不要", "禁止", "不准")


# ---------------------------------------------------------------- 风格包
def discover_pack(cfg: dict, name: str = "handraw"):
    pack = (cfg.get("style_packs") or {}).get(name) or {}
    for raw in pack.get("discover") or []:
        p = Path(os.path.expanduser(R.expand(raw, {})))
        if raw and not str(R.expand(raw, {})).strip():
            continue
        if p.exists():
            return p
    return None


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


class Pack:
    def __init__(self, root: Path, cfg: dict, name: str = "handraw"):
        self.root = root
        files = ((cfg.get("style_packs") or {}).get(name) or {}).get("files") or {}
        self.styles = _load_json(root / files.get("styles", "styles.json")) or []
        self.colors = _load_json(root / files.get("colors", "colors.json")) or []
        self.layouts = _load_json(root / files.get("layouts", "layouts.json")) or []
        self.caps = _load_json(root / files.get("caps", "model_capabilities.json")) or {}
        self.has_images = (root / "images").exists()

    def style(self, number: str):
        num = str(number).lstrip("#").zfill(3)
        for s in self.styles:
            if str(s.get("number", "")).zfill(3) == num:
                return s
        return None

    def color(self, cid: str):
        up = str(cid).upper()
        for c in self.colors:
            if str(c.get("id", "")).upper() == up:
                return c
        return None

    def layout(self, lid: str):
        up = str(lid).upper()
        for l in self.layouts:
            if str(l.get("id", "")).upper() == up:
                return l
        return None

    def reference_path(self, number: str):
        num = str(number).lstrip("#").zfill(3)
        n = int(num)
        bucket = f"{(n - 1) // 200 * 200 + 1:03d}-{((n - 1) // 200 + 1) * 200:03d}"
        for cand in (f"{num}_grid.webp", f"{num}.webp"):
            p = self.root / "images" / "individual" / bucket / cand
            if p.exists():
                return p
        return None

    def activation(self, model: str, number: str):
        """返回 (activation_source, need_reference, name_strong)。"""
        models = self.caps.get("models") or {}
        entry = models.get(model) or {}
        if not entry:
            entry = self.caps.get("default") or {}
            fallback = True
        else:
            fallback = False
        num = str(number).lstrip("#").zfill(3)
        style_entry = (entry.get("styles") or {}).get(num) or {}
        name_strong = style_entry.get("name_activation") == "strong"
        traits_strong = entry.get("traits_activation") == "strong" or name_strong
        if name_strong:
            return ("name+style", False, True)
        if traits_strong:
            return ("name+style+traits", False, False)
        if fallback and (self.caps.get("default") or {}).get("use_reference_image"):
            return ("name+style+traits+reference-image", True, False)
        return ("name+style+traits", False, False)


# ---------------------------------------------------------------- 工具
def clean_traits(text: str) -> str:
    if not text:
        return ""
    parts = re.split(r"[、；;。]", text)
    kept = [p.strip() for p in parts if p.strip() and not any(m in p for m in NEGATIVE_MARKERS)]
    return "、".join(kept)


def strip_ids(text: str) -> str:
    return ID_RE.sub("", text)


# ---------------------------------------------------------------- 主组装
def compose(req: dict, cfg: dict) -> dict:
    """req 键：scene / theme / text / style / color / layout / mode / negative / type / extra / model / pack"""
    scene_id = req.get("scene") or (cfg.get("defaults") or {}).get("scene")
    scene = (cfg.get("scenes") or {}).get(scene_id) or {}
    negatives = cfg.get("negatives") or {}
    neg_name = req.get("negative") if req.get("negative") is not None else scene.get("negative", "none")
    negative = negatives.get(neg_name, "") if isinstance(neg_name, str) else str(neg_name or "")

    theme = (req.get("theme") or "").strip()
    extra = (req.get("extra") or "").strip()
    model = req.get("model") or ""
    # 要渲染进画面的文字（仅 allow_text 场景生效；article-illustration 等禁文字场景会被忽略并提示）
    text_in_image = (req.get("text") or "").strip()

    style_raw = req.get("style")
    color_raw = req.get("color")
    layout_raw = req.get("layout")
    pack_name = req.get("pack")
    forced_name = forced_traits = ""
    if isinstance(style_raw, dict):
        pack_name = pack_name or style_raw.get("pack")
        style_key = style_raw.get("number") or style_raw.get("name") or ""
        forced_name = style_raw.get("name") or ""
        forced_traits = style_raw.get("traits") or ""
    else:
        style_key = style_raw or ""
    if isinstance(color_raw, dict):
        cid = color_raw.get("id") or ""
        forced_color_zh = color_raw.get("name_zh") or ""
        forced_color_en = color_raw.get("name_en") or ""
    else:
        cid = color_raw or ""
        forced_color_zh = forced_color_en = ""
    if isinstance(layout_raw, dict):
        lid = layout_raw.get("id") or ""
    else:
        lid = layout_raw or ""

    pack = None
    pack_root = None
    if pack_name or style_key or cid or lid:
        pack_root = discover_pack(cfg, pack_name or "handraw")
        if pack_root:
            pack = Pack(pack_root, cfg, pack_name or "handraw")

    style_name_zh = style_name_en = ""
    traits_zh = ""
    ref_image = req.get("reference_image") or ""
    activation = "none"
    need_ref = False
    notes = []

    style_key = style_key
    if style_key and pack:
        st = pack.style(style_key)
        if not st and forced_name:
            st = {"generation_name": forced_name, "traits": forced_traits}
        if st:
            style_name_zh = st.get("generation_name", "")
            style_name_en = st.get("generation_name", "")
            traits_zh = clean_traits(st.get("traits", ""))
            activation, need_ref, strong = pack.activation(model or "gpt-image-2", style_key)
            if need_ref and not ref_image:
                found = pack.reference_path(style_key)
                if found:
                    ref_image = str(found)
                else:
                    notes.append("该风格需要参考图，但风格包内没有 images/ 目录，已降级为纯文字激活")
                    need_ref = False
            elif req.get("reference_required") and not ref_image:
                notes.append("上游声明需要参考图但未提供路径，已按纯文字激活")
        else:
            notes.append(f"风格包内没有编号 {style_key}，已忽略风格")
    elif style_key:
        builtin = (cfg.get("styles") or {}).get(str(style_key))
        if builtin:
            style_name_zh = builtin.get("name_zh", "")
            style_name_en = builtin.get("name_en", "")
            traits_zh = clean_traits(builtin.get("traits", ""))
            activation = "builtin-style"
        elif pack_root is None:
            notes.append("未发现外挂风格包，风格编号已忽略；可用内置风格族见 config/default.yaml 的 styles")

    color_zh = color_en = ""
    if cid and pack:
        c = pack.color(cid)
        if c:
            color_zh = c.get("name_zh", "")
            color_en = c.get("name_en", "")
    if not color_zh and forced_color_zh:
        color_zh, color_en = forced_color_zh, forced_color_en

    layout_hint = ""
    lid = req.get("layout")
    if lid and pack:
        lo = pack.layout(lid)
        if lo:
            prompt_file = pack.root / str(lo.get("prompt_file") or "")
            if prompt_file.exists():
                layout_hint = prompt_file.read_text(encoding="utf-8").strip()
            else:
                layout_hint = "、".join(lo.get("keywords") or []) or lo.get("name", "")
                notes.append(f"版式 {lid} 的提示词模板文件不在包内，已用关键词代替")

    type_hint = (cfg.get("types") or {}).get(req.get("type") or "", "")

    zh, en = [], []
    if style_name_zh:
        zh.append(f"风格名称：{style_name_zh}。")
        en.append(f"Style name: {style_name_en}.")
    if color_zh:
        zh.append(f"主题色：{color_zh}（{color_en}）。")
        en.append(f"Theme color: {color_en}.")
    if theme:
        zh.append(f"主题：{theme}")
        en.append(f"Theme: {theme}")
    text_directive = (scene.get("text_directive") or "").strip()
    if text_directive:
        zh.append(text_directive)
    if text_in_image:
        if scene.get("allow_text", False):
            zh.append(
                f"画面中必须清晰、准确地渲染以下文字，一字不差、不得改写或遗漏：\n{text_in_image}"
            )
            en.append(
                f'Render the following text in the image exactly as written, character for character:\n"{text_in_image}"'
            )
        else:
            notes.append(
                f"场景 {scene_id} 禁止画面文字，已忽略 text={text_in_image!r}；需要文字请用 poster/cover/social-card 等场景"
            )
    if type_hint:
        zh.append(type_hint)
    if extra:
        zh.append(extra)
    if traits_zh and activation != "name+style":
        zh.append(f"核心风格特征：{traits_zh}")
        en.append(f"Core style traits: {traits_zh}")
    if layout_hint:
        zh.append(layout_hint)
        if not scene.get("allow_text", False) and ("文字" in layout_hint or "文案" in layout_hint):
            notes.append(f"版式 {lid} 含文字结构，但场景 {scene_id} 禁止画面文字；需要文字时改用 cover/poster/social-card 场景")
    if style_name_zh:
        zh.append(f"参考作者/风格名称：{style_name_zh}")
        en.append(f"Reference author/style name: {style_name_en}")

    mode = req.get("mode") or (cfg.get("defaults") or {}).get("mode") or "pure-image"
    suffix = (cfg.get("modes") or {}).get(mode, "")
    if suffix:
        zh.append(suffix)

    prompt_zh = strip_ids("\n".join(p for p in zh if p))
    prompt_en = " ".join(p for p in en if p)

    if need_ref and ref_image:
        isolation = (
            "所附图片仅用于参考画风。只提取参考图的风格特征，例如线条、笔触、媒介、材质、"
            "色彩倾向和整体视觉语言；不要使用、复制或延续参考图中的任何主体、人物、动物、服装、"
            "道具、动作、姿态、场景、背景、构图、布局、文字或故事。最终画面内容完全以用户提供的主题为准。"
        )
        prompt_zh += isolation
        prompt_en += (
            " Use the attached image only as a style reference. Extract only its stylistic qualities. "
            "The user's written theme is the sole source for the image content."
        )

    ratio = req.get("ratio") or scene.get("ratio") or (cfg.get("defaults") or {}).get("ratio")
    return {
        "scene": scene_id,
        "mode": mode,
        "ratio": ratio,
        "prompt_zh": prompt_zh,
        "prompt_en": prompt_en,
        "prompt": prompt_zh,
        "negative": negative,
        "allow_text": scene.get("allow_text", False),
        "text_in_image": text_in_image if scene.get("allow_text", False) else "",
        "pipeline": scene.get("pipeline", "gen"),
        "reference_image": ref_image if ref_image else "",
        "activation_source": activation,
        "need_reference": bool(need_ref and ref_image),
        "style_pack": str(pack_root) if pack_root else "",
        "notes": notes,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="image-gen 提示词组装")
    ap.add_argument("--spec", help="prompt-spec JSON 文件")
    ap.add_argument("--theme")
    ap.add_argument("--style")
    ap.add_argument("--color")
    ap.add_argument("--layout")
    ap.add_argument("--type")
    ap.add_argument("--scene")
    ap.add_argument("--text", help="要渲染进画面的文字（仅 allow_text 场景）")
    ap.add_argument("--mode")
    ap.add_argument("--model")
    ap.add_argument("--pack", default="handraw")
    ap.add_argument("--negative")
    ap.add_argument("--extra")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    req = {k: v for k, v in vars(args).items() if v not in (None, "")}
    if args.spec:
        req.update(json.loads(Path(args.spec).read_text(encoding="utf-8")))
    cfg = R.load_config()
    out = compose(req, cfg)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(out["prompt_zh"])
        if out["notes"]:
            print("\n".join(f"[note] {n}" for n in out["notes"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
