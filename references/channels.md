# 渠道配置

## 1. 加一个渠道（只改 YAML）

编辑 `config/channels.yaml`，追加一段：

```yaml
  - id: my-endpoint
    adapter: openai_images
    enabled: auto
    base_url: https://my-endpoint.example.com/v1
    model: {default: "my-image-model", hq: "my-image-model-pro"}
    auth: {type: bearer, key: "${MY_ENDPOINT_API_KEY}"}
    caps:
      max_side: 2048
      ratios: ["1:1", "16:9"]
      negative_prompt: true
      reference_image: false
      zh_prompt: strong
      text_rendering: weak
      seed: true
      n: true
    cost: 0.5
    latency: mid
    quality: mid
    region: cn
    tags: [cheap, zh]
```

不需要改任何 Python。

## 2. 字段说明

| 字段 | 含义 |
|---|---|
| `id` | 渠道标识，`--channel` 用这个值 |
| `adapter` | `openai_images` / `openai_chat` / `dashscope` / `generic` / `builtin` |
| `enabled` | `auto` 解析到凭据才启用；`true` 始终候选；`false` 停用 |
| `base_url` | 接口根地址。支持 `${ENV}` 占位，缺失时回退 `base_url_default` |
| `model` | `{default, hq}`。`--profile hq` 走 hq，其余走 default |
| `auth.key` | 支持 `${ENV}` 占位 |
| `proxy` | 仅该渠道走代理。`region: needs_proxy` 的渠道务必配 |
| `caps.max_side` | 单边像素上限，超限时自动等比降档 |
| `caps.ratios` | 支持的画幅，请求比例不在其中会被标记为非标 |
| `caps.negative_prompt` | 不支持时负面词自动丢弃，不报错 |
| `caps.reference_image` | 是否支持垫参考图 |
| `caps.zh_prompt` | `strong` / `medium` / `weak`，供 `zh-text` profile 过滤 |
| `caps.text_rendering` | 画面内渲染文字的能力，海报与社媒卡场景依赖它 |
| `caps.seed` / `caps.n` | 是否支持固定种子 / 一次多张 |
| `cost` | 相对单价，`1.0` 为基准，仅用于排序 |
| `latency` / `quality` | `low/mid/high`，仅用于排序 |
| `region` | `cn` / `global` / `needs_proxy` / `local` |
| `tags` | 供 profile 过滤：`cheap` `fast` `hq` `zh` `text` `router` `free` `zero-config` |

## 3. 凭据解析顺序

```
--set <id>=<key>  >  config/user.yaml 的 credentials  >  环境变量
  >  ~/.workbuddy/models.json（按 host 或 vendor 匹配自动发现）
  >  ~/.openclaw/openclaw.json
```

`img.py list --channels` 会打印每条渠道的凭据来源；来源为空即不可用。

安全约定：凭据留在环境变量或本机模型管理里。`config/user.yaml` 只在确实需要时写入，且已被 `.gitignore` 排除。

## 4. 覆盖方式（三级）

| 级别 | 用法 | 生效范围 |
|---|---|---|
| 单次 | `--channel siliconflow --model Qwen/Qwen-Image` | 本次调用 |
| 策略 | `--profile hq` | 本次调用，换一套过滤排序规则 |
| 永久 | 在 `config/user.yaml` 改 `defaults.profile` 或追加 `channels` | 所有调用 |

`config/user.yaml` 里按 `id` 合并同 id 渠道，只写要改的字段即可。

## 5. 选路解释

```bash
python3 scripts/img.py --theme "…" --explain
```

输出示例：

```
profile=default  filter={}  sort=['cost asc', 'latency asc']
  - builtin: 排到末尾（已有可用凭据，内置兜底）
  - siliconflow: 入选（cost=0.3 latency=low quality=mid）
最终链: siliconflow -> dashscope -> openai -> builtin
```

## 6. 内置出图（builtin）的位置规则

`config/default.yaml` 的 `builtin.mode`：

| mode | 行为 |
|---|---|
| `auto`（默认） | 本机无任何可用凭据 → 置顶保底；已有凭据 → 排到末尾 |
| `first` | 始终置顶（仍受 skip_when 约束） |
| `last` | 始终排末尾 |
| `off` | 关闭 |

`builtin.skip_when` 命中任一条件即跳过：`reference_image`（垫图）、`seed`、`n_gt_1`、`nonstandard_size`、`negative_prompt`。

命中 builtin 时 `img.py` 打印 handoff JSON 并以退出码 10 结束，由宿主调用自身出图能力。
