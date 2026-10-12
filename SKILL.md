---
name: image-gen
description: 通用出图技能。按场景（配图、封面、海报、社媒卡、头像、信息图、示意图、写实图）自动定画幅、文字策略与负面词，从声明式渠道注册表里选模型并自动回退，产出 PNG/JPG/WebP；支持外挂手绘风格包（279 个编号风格、36 个主题色、122 种版式），也接受上游提示词项目投喂 prompt-spec JSON 或纯文本提示词。触发词：生图、画一张、做图、配图、插画、手绘插图、封面图、海报、头像、信息图、长图、示意图、generate image、illustration、infographic、poster。不用于纯文字写作、代码生成与非图像任务。
version: 1.0.0
agent_created: true
---

# Image Gen

把「出图」做成一条可配置的流水线：**场景定限制条件 → 组装提示词 → 选渠道 → 出图 → 后处理**。
上游技能只管给提示词，本技能只管渲染。

## 1. 快速开始

```bash
cd ~/.workbuddy/skills/image-gen

# 出图（场景 + 主题）
python3 scripts/img.py --scene 配图 --theme "一位父亲在病床边削苹果" --out /abs/o.png

# 用外挂手绘风格包
python3 scripts/img.py --scene 配图 --theme "…" --style 042 --color C-07 --out /abs/o.png

# 需要画面内文字（海报、封面、社媒卡）
python3 scripts/img.py --scene 海报 --theme "秋日市集" --text "秋日市集
本周末 · 南锣鼓巷" --out /abs/o.png

# 只出提示词，不生图
python3 scripts/img.py compose --theme "…" --style 042 --json

# 看环境缺什么
python3 scripts/img.py doctor
```

首次使用先跑 `doctor`。渠道全部不可用时，内置出图保底。

## 2. 场景（决定画幅、文字、管线、负面词）

| 场景 | 别名 | 画幅 | 文字 | 管线 |
|---|---|---|---|---|
| `article-illustration` | 配图、插画、手绘、插图 | 16:9 | 禁止 | 生图 |
| `cover` | 封面、头图、题图 | 16:9 | 允许 | 生图 |
| `infographic` | 信息图、长图、数据图 | 3:4 | 允许 | HTML |
| `poster` | 海报、宣传图 | 3:4 | 允许 | 生图 + 版式 |
| `social-card` | 社媒卡、图文卡 | 1:1 | 允许 | 生图 + 图文后缀 |
| `diagram` | 示意图、流程图、架构图 | 16:9 | 允许 | HTML + SVG |
| `avatar` | 头像、图标、icon、logo | 1:1 | 禁止 | 生图 |
| `photo-realistic` | 写实、照片、产品图 | 3:2 | 禁止 | 生图 |

**负面词不再全局生效**：配图与头像禁文字，海报与社媒卡允许文字，写实图不加负面词。
细节与新增场景见 `references/scenes.md`。

**要画面内出现文字，必须给 `--text`**。允许文字的场景会自动附加场景版式要求
（如海报的「主视觉 + 标题区 + 信息区」），并把 `--text` 的内容原样交给模型渲染；
不给 `--text` 时模型不会凭空排版文字，海报会变成照片。禁文字场景给了 `--text` 会被忽略并提示。

需要文字精确的排版图（信息图、示意图）走 HTML 管线，需加 `--html /abs/page.html`，零生图 token。见 `references/html2png.md`。

## 3. 选渠道（带推荐，可覆盖）

内置渠道按**类型**给出：SiliconFlow、阿里云百炼、OpenAI 兼容、OpenRouter、宿主内置。
加渠道只改 `config/channels.yaml`，不改代码。见 `references/channels.md`。

选路策略（profile）：

| profile | 选什么 |
|---|---|
| `default` | 按单价与延迟排序（默认） |
| `cheap` | 只走低价渠道 |
| `fast` | 只走低延迟渠道 |
| `hq` | 高质量优先，走各渠道的 hq 模型 |
| `zh-text` | 中文提示词强 + 画面文字强（海报、社媒卡） |
| `ref-image` | 只走支持垫参考图的渠道 |
| `local` | 只走国内直连渠道 |
| `builtin` | 只走宿主内置出图 |

三级覆盖，逐级收窄：

1. `--channel siliconflow --model Qwen/Qwen-Image` —— 钉死
2. `--profile hq` —— 换策略
3. `config/user.yaml` —— 永久生效（先跑 `img.py init --apply` 生成）

不确定为什么选了某个渠道时加 `--explain`，会打印候选、过滤原因与最终链。

**内置出图（builtin）**：本机无任何凭据时置顶保底；已有凭据时排到末尾兜底。
需要垫图、seed、多张、非标画幅或负面词时自动跳过。见 `references/channels.md`。

## 4. 与上游提示词项目对接

上游（handraw-style、renjian-guancha、文章生成器、任意提示词项目）产出 prompt-spec JSON，
本技能负责渲染：

```bash
python3 scripts/img.py --prompt-spec spec.json --out /abs/o.png
```

契约全貌、字段说明与组装规则见 `references/prompt-contract.md`。要点：

- 风格编号、色号、版式编号**不会**写进提示词，防模型把 `#042` 画进画面。
- 风格激活按 `model_capabilities.json` 分三档：只出风格名 / 补正向特征 / 另需参考图。
- 主题是画面内容的唯一来源，风格与参考图不得改写主题。
- 上游可带 `channel` 字段自己指定渠道或策略。

外挂风格包按顺序探测：`~/.workbuddy/skills/handraw-style/` →
`~/.workbuddy/skills/renjian-guancha/vendor/handraw-style-data/` → `$IMAGE_GEN_HANDRAW_PATH`。
都没命中时回落内置 12 个风格族并打印说明。

## 5. 常用参数

| 参数 | 说明 |
|---|---|
| `--scene` / `--theme` | 场景（支持别名）与画面主题 |
| `--text` | 要渲染进画面的文字，仅 `allow_text` 场景生效（海报/封面/社媒卡/信息图/示意图） |
| `--prompt` / `--prompt-file` / `--prompt-spec` | 三种投喂方式，后者优先 |
| `--style` / `--color` / `--layout` / `--type` | 风格编号、色号、版式编号、构图类型 |
| `--mode` | `pure-image`（默认）/ `graphic-text` |
| `--ratio` / `--size` | 画幅或显式尺寸 |
| `--out` / `--n` / `--seed` | 输出路径、张数、随机种子 |
| `--profile` / `--channel` / `--model` | 选路三级覆盖 |
| `--negative` / `--ref` | 覆盖负面词、垫参考图 |
| `--post` | 后处理：`trim`、`resize`、`sheet` |
| `--emit-prompt-only` / `--dry-run` / `--explain` / `--json` | 只出提示词 / 只打印计划 / 打印选路解释 / 机器可读输出 |

## 6. 退出码

| 码 | 含义 | 处理 |
|---|---|---|
| 0 | 成功 | 输出 `OUT <路径>` |
| 1 | 所有渠道失败 | 跑 `img.py doctor`，或用 `--explain` 看原因 |
| 2 | 参数或配置错误 | 按提示修正 |
| 10 | 交宿主出图 | stdout 是 handoff JSON，用宿主出图能力生成图片并写到 JSON 里的 `out` 路径 |

读到退出码 10 时，用 JSON 中的 `prompt`、`size`、`negative` 调用宿主自身的出图能力，
把结果写到 `out` 指定路径，再继续后续流程。

## 7. 自检清单

- [ ] 跑过 `img.py doctor`，至少一条渠道可用或确认内置出图能兜底
- [ ] 场景选对：需要画面内文字时不能选 `article-illustration`
- [ ] 需要画面内文字时给了 `--text`，且文字内容本身已校对（模型会照抄，写错就画错）
- [ ] 输出路径是绝对路径或明确相对路径
- [ ] 需要多张时用 `--n`，需要复现时用 `--seed`（内置出图两者都不支持）
- [ ] 上游给了 prompt-spec 时确认 `theme` 非空

停止条件：所有渠道失败且宿主也不提供出图能力时停止，不猜测结果、不用上一次结果顶替。

## 8. 参考

- `references/scenes.md` —— 场景、负面词、构图类型、画幅
- `references/channels.md` —— 加渠道、字段说明、凭据解析、选路解释
- `references/adapters.md` —— 5 种 adapter 的请求与响应契约
- `references/prompt-contract.md` —— 与上游技能的 JSON 契约与组装规则
- `references/setup-guide.md` —— 各渠道密钥的官方入口、存储、轮换与吊销
- `references/html2png.md` —— HTML 渲染管线（信息图、示意图）
- `examples/` —— 私有 endpoint 配置、人物一致性锁定、prompt-spec 样例
