# 场景与构图类型

场景决定**限制条件**：画幅、能否出现文字、走哪条管线、默认负面词、后处理。

## 1. 内置场景

| id | 别名 | 画幅 | 文字 | 管线 | 默认负面词 | 后处理 |
|---|---|---|---|---|---|---|
| `article-illustration` | 配图、文章配图、插画、手绘、插图 | 16:9 | 禁止 | 生图 | no-text | — |
| `cover` | 封面、头图、题图、主图 | 16:9 | 允许 | 生图 | no-garbage | trim |
| `infographic` | 信息图、长图、数据图、排版图 | 3:4 | 允许 | HTML | none | trim |
| `poster` | 海报、宣传图 | 3:4 | 允许 | 生图 + 版式 | no-garbage | — |
| `social-card` | 社媒卡、图文卡、卡片图 | 1:1 | 允许 | 生图 + 图文后缀 | no-garbage | — |
| `diagram` | 示意图、流程图、架构图、关系图 | 16:9 | 允许 | HTML + SVG | none | trim |
| `avatar` | 头像、图标、icon、logo、标志 | 1:1 | 禁止 | 生图 | no-text | trim |
| `photo-realistic` | 写实、照片、产品图、实拍感 | 3:2 | 禁止 | 生图 | none | — |

`no-text` 禁一切可读字符；`no-garbage` 禁水印、logo、畸形手指、过曝等，但允许构图文字；`none` 不加负面词。

## 2. 负面词下沉规则

负面词不再全局生效。写进提示词的路径是：

```
--negative "…"（显式覆盖）
  > prompt-spec 的 negative 字段
  > 场景的 negative（具名引用 config/default.yaml 的 negatives 库）
```

写实类场景刻意用 `none`，避免把质感洗掉。

## 3. 构图类型（`--type`）

| 值 | 含义 |
|---|---|
| `portrait` | 人物半身，主体居中，肩部以上入画 |
| `full-body` | 全身入画，留出环境关系 |
| `scene` | 广角场景，人物小于画面三分之一 |
| `closeup` | 局部特写，只保留一个主体细节 |
| `top-down` | 俯视构图，桌面或床面视角 |
| `metaphor` | 抽象隐喻，用物件代替概念 |

类型只做构图约束，不改写主题。

## 4. 画幅与尺寸

`--ratio` 取 `config/default.yaml` 的 `output.ratio_presets`；`--size WxH` 显式指定时优先。

| 比例 | 像素 |
|---|---|
| 1:1 | 1328x1328 |
| 16:9 | 1664x928 |
| 4:3 | 1472x1104 |
| 3:4 | 1104x1472 |
| 3:2 | 1536x1024 |
| 2:3 | 1024x1536 |
| 9:16 | 928x1664 |

请求尺寸超过渠道 `caps.max_side` 时自动等比降档，不报错。

## 5. 新增场景

在 `config/user.yaml` 追加即可（按 key 合并）：

```yaml
scenes:
  course-slide:
    aliases: [课件配图, 教学插图]
    pipeline: gen
    ratio: "16:9"
    allow_text: true
    negative: no-garbage
    prefer_profile: zh-text
    postprocess: [trim]
```

## 6. 两种管线

- `gen`：调用生图接口。
- `html`：调用 `scripts/html2png.sh` 渲染本地 HTML，零生图 token，文字精确。`infographic` 与 `diagram` 默认走它，需要 `--html` 指定输入文件。
