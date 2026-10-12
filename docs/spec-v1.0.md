# image-gen v1.0 — 评估与设计 Spec

> 目标：把一个「某台机器上给某个项目用的生图脚本包」，重构成**场景驱动、声明式配置、可被上游提示词技能复用**的通用出图技能。
> 日期：2026-10-12 · 作者：jack · 版本：v1.0（草稿，待拍板）

---

## Part 1 · 现状评估（v0.1.0）

### 1.1 结论先行

当前技能**不具备通用性**。它是「renjian-guancha 插图版」这条单一流水线在某台机器上的产物快照：个人账号、个人代理、个人 NAS 路径、单项目的提示词约束全部写死。换机、换人、换场景都要改代码。

### 1.2 问题清单

| # | 维度 | 现状证据 | 影响 | 严重度 |
|---|---|---|---|---|
| 1 | 可移植性 | `SKILL.md` 硬编码 另一台机器上的绝对路径；默认 env 路径 `~/.openclaw/.env`；OpenRouter 代理写死 `127.0.0.1:7890` | 换机即废；本机（macOS / WorkBuddy）根本跑不通 | **P0** |
| 2 | 渠道代表性 | 7 个后端里 `cpa.hybridsam.dev`（私有中继）、`OPENROUTER_PROXY`、`OPENAI_API_KEY` 全是**个人账号快照**，不是「渠道类型」 | 渠道清单对任何其他人都不成立 | **P0** |
| 3 | 扩展性 | 后端链写死在 `gen.py` 的 Python 常量（`CPA_CHEAP/OR_HQ/LOCAL_*`） | 加一个渠道 = 改源码，不是配置 | **P0** |
| 4 | 场景覆盖 | 只有「艺术图 / 信息图」两分法 | 海报、社媒卡、头像、图表、写实图、封面无法表达 | **P0** |
| 5 | 限制条件不具代表性 | `DEFAULT_NEG` 是**全局常量**，核心是「严禁出现任何文字」；§6 还残留「女儿三十多岁 / 父亲六七十岁」这类**单个医患插画项目的人物设定** | 对海报/信息图/图文模式是**反向约束**（它们恰恰需要文字）；人物设定污染通用提示词 | **P0** |
| 6 | 风格/类型 | 无风格库、无类型库、无提示词模板 | 风格一致性只能靠手搓 prompt，多次出图会漂移 | **P0** |
| 7 | 可配置性 | 仅 env 变量；无配置文件、无 `init`、无 `--list`、无 `--model` | 用户无法自助查看/切换渠道，只能改 env | **P1** |
| 8 | 本机能力未用 | 未读 `~/.workbuddy/models.json`（WorkBuddy 模型管理，本机已配多家 provider） | 用户已配的 provider 用不上，还要再填一遍 key | **P1** |
| 9 | 与上游重复 | `renjian-guancha/scripts/illustrate.py` 是同一套多后端逻辑的**另一个进化分支**（零依赖 + local 自动发现 + `--model`），两份并行维护 | 双份维护，改一处漏一处 | **P1** |
| 10 | 代码缺陷 | `DASH_MODEL_HQ = os.environ.get("DASHSCOPE_MODEL", "qwen-image-3.0")` → 用户一旦设 `DASHSCOPE_MODEL`，HQ 链被吃掉；`SKILL.md` 有两个 `## 5.`；`--quality` 未在文档出现 | 行为与文档不符 | **P2** |

### 1.3 根因

**职责没分开**。现在的 `image-gen` 同时承担了四件事：选渠道、拼提示词、定尺寸限制、定负面词。而这四件事的变化频率完全不同——渠道按月变、场景按任务变、风格按项目变、尺寸按模型变。混在一个 Python 文件里，任何一层变化都要动代码。

---

## Part 2 · 设计目标与原则

| 原则 | 含义 |
|---|---|
| **场景驱动，不是提示词驱动** | 用户说「配图」就按配图的默认（比例/文字/负面词/管线）走，不需要每次手填负面词 |
| **配置声明化** | 渠道、场景、风格、模板都是 YAML；Python 只做执行。加能力 = 加配置 |
| **内置推荐，外置覆盖** | 推荐是一份「默认 profile」，任何一层（渠道/模型/风格/提示词）都能被用户或上游技能覆盖 |
| **单一职责：只管出图** | 上游（handraw / renjian-guancha / 小胰宝文章生成器 / 任意提示词项目）只管产出提示词或 prompt-spec；本技能只管把它渲染成图 |
| **零依赖优先** | 主链路纯标准库（`urllib`），httpx/Pillow 仅在需要后处理时按需启用 |
| **可解释** | 任何一次出图都能打印「为什么选这个渠道/这个提示词」，方便人和 AI 快速调整 |

---

## Part 3 · 架构：四层解耦

```
L1 Scene     场景预设    → 比例 / 是否允许文字 / 管线(生图|HTML) / 默认负面词 / 后处理
L2 Prompt    提示词组装  → Style(风格) + Type(类型/构图) + Template(模板) + Theme(主题)
L3 Channel   渠道注册表  → adapter 类型 + caps 能力 + cost + region（声明式 YAML）
L4 Engine    执行引擎    → 凭据解析 → 按 profile 排序回退 → 调 adapter → 后处理 → 落盘
```

**关键**：L1/L2/L3 都是数据，L4 是唯一代码。上游技能只对接 L2，本技能拥有 L3/L4 并托管 L1。

---

## Part 4 · 目录结构（v1.0）

```
image-gen/
  SKILL.md                     # 薄：定位 + 场景表 + 三条命令 + 指向 config/
  config/
    default.yaml               # 内置：scenes / styles / types / profiles（只读）
    channels.yaml              # 内置：渠道注册表（只读）
    user.yaml                  # 用户覆盖（init 生成，.gitignore）
  references/
    spec-v1.0.md               # 本文
    adapters.md                # 4 种 adapter 的请求/响应契约
    channels.md                # 渠道字段说明 + 加渠道教程
    prompt-contract.md         # 与上游技能的 JSON 契约
  scripts/
    img.py                     # 唯一入口（gen.py 降为兼容 wrapper）
    resolve.py                 # 配置合并 + --explain 打印生效链
    compose.py                 # prompt-spec / scene+style → 最终提示词
    init.py                    # 交互式初始化 → 写 user.yaml
    doctor.py                  # 自检（替代 ensure_deps.sh）
    postprocess.py             # trim / resize / contact-sheet / 格式转换
    html2png.sh                # HTML 渲染管线（保留）
  vendor/                      # 外挂风格包软链（handraw 等，不入库）
  templates/
    .env.example               # 保留，作为纯 env 模式的兜底
```

---

## Part 5 · L1 场景（Scene）

场景是**限制条件的载体**。原先全局生效的「禁止文字」下沉为 `article-illustration.negative`，不再污染其他场景。

```yaml
scenes:
  article-illustration:
    aliases: [配图, 文章配图, 插画, 手绘, illustration, 氛围图]
    pipeline: gen
    ratio: "16:9"
    size_presets: ["1664x928", "1328x1328", "928x1664"]
    allow_text: false
    negative: default-no-text          # 具名引用 negative 库
    prefer_profile: default
    postprocess: []
    notes: 默认走手绘风格包；人物设定由 Style/Theme 决定，不由场景决定
```

内置 8 个场景：

| id | 别名 | 比例 | 允许文字 | 管线 | 默认负面词 | 后处理 |
|---|---|---|---|---|---|---|
| `article-illustration` | 配图/插画/手绘 | 16:9 | ❌ | 生图 | `no-text` | — |
| `cover` | 封面/头图/题图 | 16:9 | 可选 | 生图 | `no-garbage` | trim |
| `infographic` | 信息图/长图/数据图 | 自定义 | ✅ | **HTML** | — | trim |
| `poster` | 海报 | 3:4 | ✅ | 生图 + layout | `no-garbage` | — |
| `social-card` | 社媒卡/图文卡 | 1:1 | ✅ | 生图 + `graphic-text` 后缀 | `no-garbage` | — |
| `diagram` | 示意图/流程图/架构图 | 16:9 | ✅ | **HTML(SVG)** | — | trim |
| `avatar` | 头像/图标/LOGO | 1:1 | ❌ | 生图 | `no-text` | trim + 居中 |
| `photo-realistic` | 写实/照片/产品图 | 3:2 | ❌ | 生图 | **无**（写实图不加负面词） | — |

负面词库（`negatives:`）：`no-text`（禁文字/字母/数字/签名/印章/水印/logo）、`no-garbage`（禁水印/logo/畸形手指/过曝，但**允许构图文字**）、`none`。

---

## Part 6 · L2 风格 / 类型 / 模板

### 6.1 三层数据结构

| 层 | 内容 | 谁提供 |
|---|---|---|
| **Style 风格** | 画风：`name_zh / name_en / traits / 兼容模型 / 参考图` | 内置精简库 + 外挂 pack |
| **Type 类型** | 构图与主体类型：`半身 / 全身 / 场景 / 特写 / 俯视 / 抽象隐喻` | 内置 |
| **Layout 排版** | 图文结构：`SC-001 上文下图`、`IG-xxx 信息图`、`SB-xxx 分镜` | 外挂 pack（handraw layouts.json，122 种） |

### 6.2 内置精简风格库（12 族，跨场景通用）

`line-doodle` / `ink-wash` / `watercolor` / `pencil-sketch` / `woodcut` / `risograph` / `flat-vector` / `minimal-geo` / `collage` / `pixel` / `clay-3d` / `editorial-cartoon`

每族含：`name_zh`、`name_en`、`traits`（正向可见特征）、`zh_prompt_hint`、`compatible_adapters`。

### 6.3 外挂风格包（对接 handraw）

```yaml
style_packs:
  handraw:
    discover:                        # 按顺序探测，命中即用
      - ~/.workbuddy/skills/handraw-style/
      - ~/.workbuddy/skills/renjian-guancha/vendor/handraw-style-data/
      - ${IMAGE_GEN_HANDRAW_PATH}
    files: {styles: styles.json, colors: colors.json, layouts: layouts.json,
            caps: model_capabilities.json}
    ranges: {style: "001-279", color: "C-01-C-36", layout: ["SC","IG","SB"]}
    rules:                           # 沿用 handdraw-style-prompter 的既有规则
      - 编号不得写进提示词（防模型把 #042 画进画面）
      - name_activation=strong 时只出「作者/风格名 + 主题」，不出 traits
      - 否则补 traits；仍不激活则要求参考图 + 注入参考隔离指令
      - traits 只取正向，过滤含 避免/不要/禁止/不准 的子句
```

**探测不到完整包时**，回落 `renjian-guancha/vendor/handraw-style-data/`（本目录已存在，含 279 风格 + 36 色 + 122 版式，缺的只是参考图 37MB）→ 即：**只装本技能也能跑 handraw 风格**。

---

## Part 7 · L2 提示词契约（与上游技能的衔接）

上游 = handraw-style、renjian-guancha、小胰宝公众号文章生成器、或任何「能产出提示词的项目」。

### 契约 A · prompt-spec JSON（推荐）

上游产出，本技能消费：

```json
{
  "v": 1,
  "scene": "article-illustration",
  "theme": "一位父亲在病床边削苹果，女儿在旁边看着",
  "style":  { "pack": "handraw", "number": "042",
              "name": "Beatrix Potter Watercolor", "traits": "细笔水彩、柔和田园色…" },
  "color":  { "id": "C-07", "name_zh": "橄榄绿", "name_en": "Olive Green" },
  "layout": "SC-001",
  "mode":   "pure-image",
  "reference_image": "/abs/042.webp",
  "reference_required": true,
  "negative": null,
  "extra": "横构图，左侧留白"
}
```

本技能负责：选渠道 → 查 `model_capabilities.json` 决定 **name / name+traits / name+traits+ref-image** 三档激活 → 拼终稿 → 出图 → 后处理。

### 契约 B · 纯文本（最低要求）

`--prompt "…"` 或 `--prompt-file spec.md`。本技能只补：场景默认负面词、比例、后处理。**不改动主题内容**。

### 契约 C · 反向（只出提示词，不生图）

`--emit-prompt-only` → 输出拼装好的中/英双语提示词，供用户复制到任意图像 AI（Midjourney / 即梦 / GPT Image）。本技能此时是「提示词编译器」。

### 契约 D · 上游可覆盖渠道策略

prompt-spec 里可带 `"channel": {"profile":"hq"}` 或 `"channel": {"id":"siliconflow","model":"Qwen/Qwen-Image"}`，把选渠道的权力交回上游。

---

## Part 8 · L3 渠道注册表（声明式）

### 8.1 4+1 种 adapter，覆盖一切

| adapter | 请求 | 适用 |
|---|---|---|
| `openai_images` | `POST {base}/images/generations` | SiliconFlow / OpenAI / 任何 OpenAI 兼容图接口 / 私有 endpoint |
| `openai_chat` | `POST {base}/chat/completions`，`modalities:["image","text"]`，读 `message.images[].image_url.url` | OpenRouter / Gemini 类对话式出图 |
| `dashscope` | `POST {base}/api/v1/services/aigc/multimodal-generation/generation` | 阿里云百炼 Qwen-Image |
| `generic` | 可配 `request_template` + `response_jsonpath` | 兜底任意 HTTP 接口 |
| `builtin` | 调宿主内置 ImageGen 工具 | 环境提供时优先可选 |

> 加渠道 = `channels.yaml` 加一段，**不改一行代码**。

### 8.2 channel 字段

```yaml
channels:
  - id: siliconflow
    adapter: openai_images
    enabled: auto                       # auto = 解析到 key 才启用
    base_url: https://api.siliconflow.cn/v1
    model: {default: "Qwen/Qwen-Image", hq: "Qwen/Qwen-Image"}
    auth:  {type: bearer, key: "${SILICONFLOW_API_KEY}"}
    caps:
      max_side: 2048                    # 宽度硬上限 → 自动降档
      ratios: ["1:1","16:9","4:3","3:4","9:16","3:2","2:3"]
      negative_prompt: true
      reference_image: false
      zh_prompt: strong                 # strong | medium | weak
      text_rendering: weak              # 弱 → 场景要求文字时自动降权
      seed: true
      n: true
    cost: 0.3                           # 相对单价，1.0 = 基准
    latency: low                        # low | mid | high
    quality: mid
    region: cn                          # cn | global | needs_proxy
    tags: [cheap, fast, zh]
    proxy: null                         # needs_proxy 时填 ${OPENROUTER_PROXY}
```

### 8.3 凭据解析链（不再只靠 env 文件）

```
CLI --set > config/user.yaml > 环境变量 > ~/.workbuddy/models.json（按 base_url/vendor 自动发现）
        > ~/.openclaw/openclaw.json > 跳过并提示
```

`~/.workbuddy/models.json` 是本机 WorkBuddy「模型管理」的既有配置，自动发现后**用户无需再填 key**（`illustrate.py` 已验证此路径可行）。

---

## Part 9 · Profiles（带推荐，但不锁死）

**推荐不是硬编码的回退链，而是「按 caps 过滤 + 排序」的策略**：

```yaml
profiles:
  default:   {filter: {},                        sort: [cost asc, latency asc], max_attempts: 4}
  cheap:     {filter: {tags: [cheap]},           sort: [cost asc]}
  fast:      {filter: {tags: [fast]},            sort: [latency asc]}
  hq:        {filter: {tags: [hq]},              sort: [quality desc]}
  zh-text:   {filter: {caps.zh_prompt: strong}}
  ref-image: {filter: {caps.reference_image: true}}
  local:     {filter: {region: cn}}
```

三条覆盖路径，逐级收窄：

1. `--profile hq` —— 换个推荐策略
2. `--channel siliconflow --model Qwen/Qwen-Image` —— 钉死
3. `config/user.yaml` 里改 profile 或加 channel —— 永久生效

**AI 可调**：`img.py --explain` 打印「候选渠道 → 过滤原因 → 最终顺序 → 选中理由」，AI 读一眼就能给出调整建议（缺 key / 尺寸超限 / 不支持参考图 / 需要代理）。

---

## Part 10 · CLI

```bash
img.py --scene article-illustration \
       --theme "一位父亲在病床边削苹果" \
       [--prompt-spec spec.json | --prompt "…" | --prompt-file f.md] \
       [--style-pack handraw] [--style 042] [--color C-07] [--layout SC-001] \
       [--mode pure-image|graphic-text] \
       [--ratio 16:9 | --size 1664x928] [--n 2] [--seed N] \
       [--profile default|cheap|fast|hq|zh-text|ref-image|local] \
       [--channel X] [--model Y] [--negative "…"] [--ref /abs/img.webp] \
       [--out /abs/o.png] [--post trim,resize] \
       [--emit-prompt-only] [--dry-run] [--explain]

img.py init      # 交互式：探测本机 provider → 生成 config/user.yaml
img.py list      # 列出 场景 / 风格 / 渠道（含是否可用）
img.py doctor    # 自检：依赖、key、可达性、尺寸限制
img.py compose   # 只出提示词（等价 --emit-prompt-only）
```

---

## Part 11 · 后处理与输出

- `trim` 按边缘中位色裁白边；`resize` 统一输出宽度；`contact-sheet` 多张（`--n>1`）拼对比图
- 格式按后缀自动：`.png` / `.jpg`(q=90) / `.webp`
- 可选上传：命中本机 COS 配置时 `--upload cos://workbuddy-1328692865/xyb/`（沿用既有默认路径）
- 输出目录约定：未给 `--out` 时落 `./output/<scene>-<timestamp>.png`

---

## Part 12 · 迁移路径（v0.1 → v1.0）

| 步 | 动作 | 风险 |
|---|---|---|
| 1 | `gen.py` 降为 thin wrapper，旧参数映射到 `img.py`，打印 deprecation | 无，旧调用不断 |
| 2 | `scripts/migrate_v1.py`：读现有 env → 生成 `config/user.yaml` | 无 |
| 3 | 把 SKILL.md §6 的「禁文字负面词」下沉为 `article-illustration.negative`；「女儿/父亲人物设定」移入 `examples/` 作为**示例**而非常规 | 需同步 renjian-guancha 调用 |
| 4 | `renjian-guancha/scripts/illustrate.py` 改为调用 `img.py --prompt-spec`，删掉重复后端逻辑 | 需回归插图版出图 |
| 5 | 硬编码路径全部移除：另一台机器的绝对路径 → `$(dirname $0)/..`；`~/.openclaw/.env` → 凭据解析链 | — |

---

## Part 13 · 验收标准（DoD）

1. 全新环境、只跑 `img.py init` + 填 1 个 key，能出图
2. 加一个新渠道**只改 YAML**，不改 Python
3. `poster` / `social-card` 场景出图**允许文字**；`article-illustration` 出图**无文字**
4. 传入 handraw prompt-spec（含 `#042` + `C-07` + `SC-001`）能正确出图，且画面里**不出现编号**
5. `--explain` 输出能解释「为什么是这个渠道」
6. 自动发现 `~/.workbuddy/models.json` 里已配的 provider，无需重复填 key
7. `--emit-prompt-only` 产出的提示词可直接贴进任意第三方图像 AI
8. `renjian-guancha` 插图版改用本技能后，出图结果不劣化
9. 无任何 key 时 `doctor` 明确列出「缺什么、去哪配」
10. 主链路零第三方依赖（`python3 img.py` 直接跑）

---

## Part 14 · 落地排期（建议 3 个 PR）

| PR | 内容 | 产出 |
|---|---|---|
| PR1 | L3+L4：channels.yaml + 4 种 adapter + `img.py` + `init/list/doctor` + 凭据解析链 | 通用出图引擎可用，gen.py 兼容保留 |
| PR2 | L1+L2：scenes / styles / types / negatives + `compose.py` + prompt-spec 契约 | 场景与风格可用，负面词不再全局 |
| PR3 | 外挂 pack + 上游衔接：handraw 探测与激活策略 + renjian-guancha 切换 + 文档 | 生态打通 |

---

## Part 15 · 待拍板（需要你定）

1. **内置渠道清单**：默认带哪些「有代表性的公开渠道」？（建议：SiliconFlow / 阿里云百炼 / OpenAI 兼容 / OpenRouter 四类**类型**各一条示例，CPA 这类私有中继降级为 `examples/`）
2. **配置文件格式**：YAML（表达力强，需 pyyaml）vs JSON（零依赖）。→ 建议 YAML + 内置极简解析回退 JSON
3. **是否保留 `html2png` 在技能内**：它是独立能力（零 token 排版图），建议保留但拆为 `pipeline: html` 的一个实现，不单独成节
4. **内置风格库规模**：12 族精简版够不够，还是要接 handraw 279 种才算完整？
5. **`builtin` adapter 优先级**：宿主的 ImageGen 工具可用时，是否默认优先（省配置）还是默认关闭（可控）？
