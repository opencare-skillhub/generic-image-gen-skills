# 提示词契约（与上游技能对接）

上游负责产出提示词，本技能负责把它渲染成图。四条契约，按需选用。

## 契约 A · prompt-spec JSON（推荐）

上游写文件，`img.py --prompt-spec spec.json` 消费：

```json
{
  "v": 1,
  "scene": "article-illustration",
  "theme": "一位父亲在病床边削苹果，女儿在旁边看着",
  "style":  {"pack": "handraw", "number": "042",
             "name": "Beatrix Potter Watercolor", "traits": "细笔水彩、柔和田园色"},
  "color":  {"id": "C-07", "name_zh": "橄榄绿", "name_en": "Olive Green"},
  "layout": "SC-001",
  "mode":   "pure-image",
  "type":   "scene",
  "reference_image": "/abs/042.webp",
  "reference_required": false,
  "negative": null,
  "extra": "横构图，左侧留白",
  "channel": {"profile": "hq"}
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `scene` | 否 | 场景 id 或别名，缺省用 `defaults.scene` |
| `theme` | 是 | 画面主题，唯一内容来源 |
| `text` | 否 | 要渲染进画面的文字，仅 `allow_text` 场景生效；禁文字场景忽略并给 note |
| `style.number` / `style.name` / `style.traits` | 否 | 外挂风格包编号；`name`/`traits` 可绕过查表直接给 |
| `color.id` | 否 | 主题色编号 |
| `layout` | 否 | 版式编号 |
| `mode` | 否 | `pure-image`（默认）或 `graphic-text` |
| `type` | 否 | 构图类型 |
| `reference_image` | 否 | 垫图绝对路径 |
| `reference_required` | 否 | 上游声明需要参考图但路径缺失时，降级为纯文字并打印说明 |
| `negative` | 否 | 覆盖场景默认负面词；`null` 表示沿用场景 |
| `extra` | 否 | 追加到提示词的补充要求 |
| `channel` | 否 | `{"profile":"hq"}` 或 `{"id":"siliconflow","model":"…"}`，把选渠道权交回上游 |

## 契约 B · 纯文本

```bash
python3 scripts/img.py --prompt "完整的最终提示词" --scene article-illustration --out /abs/o.png
```

本技能只补场景负面词、画幅与后处理，不改写提示词内容。

## 契约 C · 只出提示词

```bash
python3 scripts/img.py compose --theme "…" --style 042 --color C-07 --json
```

输出拼装好的提示词与元信息，不调用任何生图接口。产物可直接贴进第三方图像 AI。

## 契约 D · 上游指定渠道

prompt-spec 里带 `channel` 字段，或用命令行 `--channel` / `--profile` 覆盖。

## 组装规则

1. 编号不进提示词。`#042`、`C-07`、`SC-001` 会被剥离，只保留自然语言名称，防模型把编号画进画面。
2. 风格激活三档，按 `model_capabilities.json` 与当前模型判定：
   - `name+style`：风格名本身强激活，只出「风格名 + 主题」，不输出特征。
   - `name+style+traits`：补正向特征。含「避免 / 不要 / 禁止 / 不准」的子句会被过滤掉。
   - `name+style+traits+reference-image`：另需参考图，并注入参考隔离指令。
3. 参考隔离指令（需要垫图时自动追加）：

   > 所附图片仅用于参考画风。只提取参考图的风格特征，例如线条、笔触、媒介、材质、色彩倾向和整体视觉语言；不要使用、复制或延续参考图中的任何主体、人物、动物、服装、道具、动作、姿态、场景、背景、构图、布局、文字或故事。最终画面内容完全以用户提供的主题为准。

4. `graphic-text` 模式在提示词末尾追加固定后缀，让文字参与构图。
5. 主题是画面内容的唯一来源，风格与参考图不得改写主题。

## 风格包

`config/default.yaml` 的 `style_packs.handraw.discover` 按顺序探测：

```
~/.workbuddy/skills/handraw-style/
~/.workbuddy/skills/renjian-guancha/vendor/handraw-style-data/
${IMAGE_GEN_HANDRAW_PATH}
```

未发现时回落内置 12 个风格族（`config/default.yaml` 的 `styles`），并打印说明。
风格包内没有 `images/` 目录时，需要参考图的风格降级为纯文字激活，同样打印说明。

## 已知上游

| 上游 | 对接方式 |
|---|---|
| `handraw-style` | 契约 A：`style.number` + `color.id` + `layout` |
| `renjian-guancha` | 契约 A，插图版 2–3 张 |
| 小胰宝公众号文章生成器 | 契约 A 或 B |
| 任意提示词项目 | 契约 B 或 C |
