# CHANGELOG

每次改动在**顶部**加一条。版本号以 `SKILL.md` 版本头为准。

## v1.0.0 — 2026-10-12

从「renjian-guancha 插图版快照」重构为通用出图技能。目录结构、配置格式、CLI 均破坏性变更。

**新增**

- `config/default.yaml` —— 8 个场景（各带画幅／文字策略／负面词／管线）、负面词库、
  构图类型、8 个选路 profile、12 个内置风格族、风格包探测路径。
- `config/channels.yaml` —— 声明式渠道注册表，按渠道类型各给一条公开示例
  （SiliconFlow、阿里云百炼、OpenAI 兼容、OpenRouter、宿主内置）。
- `scripts/img.py` —— 唯一入口：`generate` / `compose` / `list` / `doctor` / `init`。
- `scripts/resolve.py` —— 配置合并、凭据解析链（CLI → user.yaml → env → 本机模型配置自动发现）、
  按 caps 过滤排序选路、`--explain` 打印选择理由。
- `scripts/compose.py` —— prompt-spec → 终稿提示词；风格包三档激活；
  风格编号／色号／版式编号不进提示词。
- `scripts/adapters.py` —— 5 种 adapter：`openai_images` / `openai_chat` / `dashscope` /
  `generic` / `builtin`。
- `scripts/miniyaml.py` —— 零依赖 YAML 子集解析器（装了 PyYAML 时优先用），主链路保持零第三方依赖。
- `scripts/postprocess.py` —— trim / resize / contact-sheet。
- `references/` —— scenes、channels、adapters、prompt-contract、setup-guide、html2png 六份。
- `examples/` —— prompt-spec 样例、私有中继 endpoint 示例、人物一致性锁定方法。
- `skill-dependencies.json` —— 依赖清单与功能降级矩阵。
- `README.md`、`docs/spec-v1.0.md`。

**修改**

- `SKILL.md` 重写为薄入口：定位、场景表、三条命令、退出码、自检清单，细节指向 `config/` 与 `references/`。
- `scripts/gen.py` 降为兼容 wrapper，旧参数映射到 `img.py`（`--backend` → `--channel`，
  `--hq` → `--profile hq`），打印 deprecation。旧调用不断。
- `scripts/html2png.sh` 保留并收为 `pipeline: html` 的实现，修掉硬编码绝对路径。
- `templates/.env.example` 更新为纯环境变量兜底模式。

**删除**

- `scripts/ensure_deps.sh`（由 `img.py doctor` 取代）。
- `references/providers.md`（由 `config/channels.yaml` + `references/channels.md` 取代）。
- 私有中继 CPA 移出内置渠道，降级到 `examples/private-relay.yaml`。

**修复的行为缺陷**

- 全局「严禁出现任何文字」不再对所有场景生效：配图／头像禁文字，海报／社媒卡／封面允许文字，
  写实图不加负面词。原实现对海报、信息图、社媒卡是反向约束。
- `--text` 支持：允许文字的场景会把待渲染文字原样交给模型，并附加场景版式要求；
  不给 `--text` 时模型不会凭空排版文字（实测：海报第一版出成了无字照片）。
  禁文字场景收到 `--text` 时忽略并提示。
- 凭据不再依赖单一 env 文件，改为多级解析链，本机已配的 provider 免填 key。
- 内置出图（builtin）改为条件性优先：无凭据时置顶保底，已有凭据时排末尾兜底，
  命中 `skip_when`（垫图／seed／多张／非标画幅／负面词）时跳过。

**实测**

- `img.py list --scenes` / `--styles` / `--channels`：场景别名命中、风格包发现
  （279 风格 + 36 色 + 122 版式）、SiliconFlow 凭据自动发现。
- `compose --style 042 --color C-07`：编号未进提示词，激活档正确。
- `--explain`：海报场景把文字能力强的渠道排前，配图场景把低价渠道排前。
- 真实出图 2 张：配图走 SiliconFlow（1664×928 手绘水彩）、海报走百炼（3:4，文字一字不差渲染）。
- `gen.py` 转发与 builtin handoff（退出码 10）均正常。

**未实测**

- HTML 渲染管线（本机无 Gotenberg/Chromium）。
- Pillow 后处理（本机 managed Python 无 PIL，会自动跳过）。
