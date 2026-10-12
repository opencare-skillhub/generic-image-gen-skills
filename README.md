# Generic Image Gen Skills

通用出图技能。把「出图」做成一条可配置的流水线：**场景定限制条件 → 组装提示词 → 选渠道 → 出图 → 后处理**。

上游只管给提示词，本技能只管渲染。

> 当前版本以 `SKILL.md` 的版本头为准，变更历史见 [`CHANGELOG.md`](./CHANGELOG.md)。
> 本 README 不写死版本号，避免出现第三个会漂移的版本来源。

## 它解决什么问题

大多数出图脚本是「某个人在某台机器上跑通的一份脚本」：路径硬编码、渠道写死在代码里、
负面词全局生效、换场景就改代码。本技能把这些全部外置成配置：

| 原来的做法 | 本技能 |
|---|---|
| 渠道写死在脚本常量里 | 声明式 `config/channels.yaml`，加渠道只加一段 YAML |
| 全局「严禁出现任何文字」 | 按**场景**决定文字策略：配图禁文字，海报／社媒卡允许文字 |
| 换场景改代码 | 8 个内置场景各带自己的画幅、文字策略、负面词、渲染管线 |
| 换模型要懂后端差异 | 5 种 adapter 覆盖 OpenAI 系、DashScope、通用 HTTP、宿主内置 |
| 换风格靠手搓提示词 | 外挂风格包（279 个编号风格 + 36 个主题色 + 122 种版式） |
| 换机器跑不起来 | 凭据自动发现，脚本零第三方依赖 |

## 核心设计：四层解耦

```text
Scene   场景：画幅、文字策略、负面词、渲染管线
  ↓
Prompt  提示词：风格 / 主题色 / 版式 / 构图类型 / 文字
  ↓
Channel 渠道：声明式注册表，按能力过滤排序，自动回退
  ↓
Engine  引擎：唯一出图代码，5 种 adapter
```

前三层都是配置，只有第四层是代码。加场景、加风格、加渠道都不需要改代码。

## 快速开始

```bash
cd ~/.workbuddy/skills/image-gen

python3 scripts/img.py doctor    # 首次使用先跑，看缺什么

# 出图（场景 + 主题）
python3 scripts/img.py --scene 配图 --theme "一位父亲在病床边削苹果" --out /abs/o.png

# 用外挂手绘风格包
python3 scripts/img.py --scene 配图 --theme "…" --style 042 --color C-07 --out /abs/o.png

# 需要画面内文字（海报、封面、社媒卡）
python3 scripts/img.py --scene 海报 --theme "秋日市集" --text "秋日市集
本周末 · 南锣鼓巷" --out /abs/o.png

# 只出提示词，不生图
python3 scripts/img.py compose --theme "…" --style 042 --json
```

渠道全部不可用时，内置出图能力保底。

## 场景（决定画幅、文字、管线、负面词）

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

**要画面内出现文字，必须给 `--text`。** 允许文字的场景会自动附加场景版式要求，
并让模型一字不差地渲染 `--text` 的内容；不给 `--text` 时模型不会凭空排版文字。
细节与新增场景见 `references/scenes.md`。

## 渠道：带推荐，可覆盖

内置渠道按**类型**给出：SiliconFlow、阿里云百炼、OpenAI 兼容、OpenRouter、宿主内置。
加渠道只改 `config/channels.yaml`，见 `references/channels.md`。

选路策略（profile）：`default` / `cheap` / `fast` / `hq` / `zh-text` / `ref-image` / `local` / `builtin`。

三级覆盖，逐级收窄：

1. `--channel siliconflow --model Qwen/Qwen-Image` —— 钉死
2. `--profile hq` —— 换策略
3. `config/user.yaml` —— 永久生效

不确定为什么选了某个渠道时加 `--explain`，会打印候选、过滤原因与最终链。

## 与上游提示词项目对接

上游（手绘风格技能、写作技能、文章生成器、任意提示词项目）产出 prompt-spec JSON，
本技能负责渲染：

```bash
python3 scripts/img.py --prompt-spec spec.json --out /abs/o.png
```

契约全貌见 `references/prompt-contract.md`。要点：

- 风格编号、色号、版式编号**不会**写进提示词，防模型把 `#042` 画进画面。
- 风格激活按模型能力分三档：只出风格名 / 补正向特征 / 另需参考图。
- 主题是画面内容的唯一来源，风格与参考图不得改写主题。
- 上游可带 `channel` 字段自己指定渠道或策略。

## 与小胰宝开源项目的组合关系

小胰宝（PancrePal）是面向胰腺癌患者与家属的公益社区项目。这个仓库是
[`opencare-skillhub`](https://github.com/opencare-skillhub) 组织下的通用出图技能，
**本身不绑定小胰宝**，小胰宝只是它的第一个重度使用场景。

一条典型的小胰宝内容产线是这样接起来的：

```text
选题与素材
   ↓
写作技能：产出文章正文（HTML 一页 / 微信长图）
   ↓ 需要配图、封面、信息图
generic-image-gen-skills  ←  手绘风格包（279 风格 / 36 色 / 122 版式）
   ↓ 图文合稿
xyb-humanizer：去 AI 味、校准医学表述与恐吓倾向
   ↓
小胰宝社区发布（科普、白皮书、患者教育、社区内容）
```

同组织的另一个公开技能
[`xyb-humanizer`](https://github.com/opencare-skillhub/xyb-humanizer)
负责产线的最后一环：文字的自然度、作者感与医学可信度。两者是**上下游而非替代关系**——
一个管画面，一个管文字。

为什么公益内容场景特别需要这套东西：

- **画风要稳。** 科普与患者教育材料是系列内容，配图风格跳来跳去会削弱可信度。
  风格包＋场景配置让同一批内容保持一致的视觉语言。
- **文字不能错。** 海报和长图上的文字由模型照抄，写错就印错。
  本技能把「要渲染的文字」做成单独入参，与画面主题分离，便于人工校对。
- **不能靠恐吓抓注意力。** 这与 `xyb-humanizer` 的红线一致：出图环节同样不做灾难化、
  不渲染羞耻或虚假紧迫感的画面。
- **渠道要可迁移。** 志愿者各自的环境不同，凭据不能写死在脚本里。
  凭据解析链（CLI → `user.yaml` → 环境变量 → 本机模型配置自动发现）让同一份技能
  在不同志愿者的机器上都能直接跑。

如果你在做别的公益病种社区、科普项目或任何需要稳定出图的场景，这个技能可以单独使用，
不需要接入小胰宝。

## 致谢

感谢志愿者 **sam** 的贡献。

## 目录结构

```text
image-gen/
├── SKILL.md                     主文件：定位、场景表、常用参数、退出码、自检清单
├── README.md                    本文件：定位、组合关系、维护约定
├── CHANGELOG.md                 变更记录，每次改动顶端加一条
├── skill-dependencies.json      依赖清单与功能降级矩阵
├── .gitignore
├── config/
│   ├── default.yaml             场景、负面词、构图类型、profile、内置风格族、风格包探测
│   └── channels.yaml            渠道注册表（user.yaml 由 init 生成，不入库）
├── scripts/
│   ├── img.py                   唯一入口：generate / compose / list / doctor / init
│   ├── resolve.py               配置合并、凭据解析链、选路、--explain
│   ├── compose.py               提示词组装、风格包三档激活
│   ├── adapters.py              5 种 adapter 的请求与响应契约
│   ├── miniyaml.py              零依赖 YAML 子集解析器（有 PyYAML 时优先用）
│   ├── postprocess.py           trim / resize / contact-sheet
│   ├── gen.py                   旧入口兼容 wrapper
│   ├── html2png.sh              HTML 渲染管线（信息图、示意图）
│   └── check_environment.py     环境检查
├── references/
│   ├── scenes.md                场景、负面词、构图类型、画幅
│   ├── channels.md              加渠道、字段说明、凭据解析、选路解释
│   ├── adapters.md              5 种 adapter 契约
│   ├── prompt-contract.md       与上游技能的 JSON 契约
│   ├── setup-guide.md           各渠道密钥的官方入口、存储、轮换与吊销
│   └── html2png.md              HTML 渲染管线
├── examples/
│   ├── prompt-spec.json         prompt-spec 样例
│   ├── private-relay.yaml       私有中继／自建 endpoint 示例
│   └── character-lock.md        系列内容的人物一致性锁定方法
├── templates/.env.example       纯环境变量兜底模式
└── docs/spec-v1.0.md            v1.0 设计文档，供回溯设计决策
```

## 维护

### 版本规则

改动 `SKILL.md`、`config/` 或 `scripts/` 的实质内容时，**两件事必须同时做**：

1. 把 `SKILL.md` 版本头升一位；
2. 在 `CHANGELOG.md` **顶部**加一条，写清改了哪个文件、依据是哪一次实测。

只改版本号不记 CHANGELOG（或反过来）会造成版本记录脱节。
纯错别字或格式修正可以不升版本号，但仍建议在 CHANGELOG 记一行。

### 新增 CLI 参数必须同步三处

`scripts/img.py` 加参数时，同时更新：

1. `SKILL.md` 第 5 节参数表；
2. `references/prompt-contract.md` 字段表（如果上游 JSON 也要支持这个字段）；
3. `CHANGELOG.md`。

v1.0.0 时就漏过一次：`--text` 先加了代码，文档没跟上，技能自述与实际能力漂移。

### git 工作流

默认分支 `main`，远端在 `opencare-skillhub/generic-image-gen-skills`。

```sh
git log --oneline
git show <commit>
git diff HEAD -- config/
git restore <file>
git revert <commit>
```

### 提交前自查

```sh
python3 scripts/img.py doctor                    # 环境
python3 -m py_compile scripts/*.py && bash -n scripts/html2png.sh
git status                                       # 确认没有卷入半成品或凭据
```

`config/user.yaml` 与 `output/` 已在 `.gitignore` 中，不会误提交。

### 多会话并行修改的风险

- **git 不能阻止版本号撞车。** 有效的是约定：技能改动尽量只在一个会话里做，或每完成一处就提交。
- 若 A 会话改了文件还没提交，B 会话执行 `git add -A` 会把 A 的半成品一起卷进自己的提交。
  提交前先看一眼 `git status`。
- 推送前检查内容：本技能会被用在医学科普场景，`examples/` 与 `references/` 里若引用真实案例，
  需确认无手机号、证件号、密钥、医院名、医生姓名与病友昵称。

## 参考

- `references/scenes.md` —— 场景、负面词、构图类型、画幅
- `references/channels.md` —— 加渠道、字段说明、凭据解析、选路解释
- `references/adapters.md` —— 5 种 adapter 的请求与响应契约
- `references/prompt-contract.md` —— 与上游技能的 JSON 契约与组装规则
- `references/setup-guide.md` —— 各渠道密钥的官方入口、存储、轮换与吊销
- `references/html2png.md` —— HTML 渲染管线（信息图、示意图）
- `examples/` —— prompt-spec 样例、私有 endpoint 配置、人物一致性锁定
- `docs/spec-v1.0.md` —— v1.0 设计文档
