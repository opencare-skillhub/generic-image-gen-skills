# 凭据配置指南

## 0. 依赖与官方入口

| 依赖 id | 必需 | 官方主页 | 官方文档 |
|---|---|---|---|
| `python-runtime` | 是 | https://www.python.org | https://docs.python.org/zh-cn/3/ |
| `image-provider-api` | 是 | https://www.siliconflow.cn | https://docs.siliconflow.cn |
| `handraw-style-pack` | 否 | https://www.workbuddy.cn | https://www.workbuddy.cn/docs/workbuddy/Overview |
| `html-renderer` | 否 | https://gotenberg.dev | https://gotenberg.dev/docs/getting-started |

`python-runtime` 要求 Python 3.10 及以上，安装包从 https://www.python.org/downloads/ 获取。
`handraw-style-pack` 是本地只读风格数据，缺失时回落内置 12 个风格族。
`html-renderer` 只影响信息图与示意图场景，缺失时改用生图管线。

凭据只保存在本机。三种存放方式，按推荐顺序：

1. **WorkBuddy 模型管理**（`~/.workbuddy/models.json`）——已配置的 provider 会被自动发现，不必再填一次。
2. **环境变量**——适合临时或 CI 场景。
3. **`config/user.yaml` 的 `credentials`**——适合长期固定，该文件已被 `.gitignore` 排除。

优先级：`--set` > `config/user.yaml` > 环境变量 > 模型管理 > `~/.openclaw/openclaw.json`。

不得把密钥写进提示词、日志、交付文件或版本库。

## 1. SiliconFlow（Qwen-Image，国内直连）

- 主页：https://www.siliconflow.cn
- 文档：https://docs.siliconflow.cn
- 控制台：https://cloud.siliconflow.cn → 账户管理 → API 密钥 → 新建密钥
- 密钥页：https://cloud.siliconflow.cn/account/ak
- 环境变量：`SILICONFLOW_API_KEY`
- 权限：图像生成接口调用
- 轮换 / 吊销：同一页面删除旧密钥后新建，同步更新环境变量
- 验证：`img.py list --channels` 显示 siliconflow 可用

## 2. 阿里云百炼（Qwen-Image，画面内文字能力强）

- 主页：https://bailian.console.aliyun.com
- 文档：https://help.aliyun.com/zh/model-studio/
- 控制台：百炼控制台 → 密钥管理 → 创建 API Key
- 环境变量：`DASHSCOPE_API_KEY`
- 权限：多模态生成接口调用
- 轮换 / 吊销：密钥管理页删除并新建
- 验证：`img.py list --channels` 显示 dashscope 可用

## 3. OpenAI（或任意 OpenAI 兼容 endpoint）

- 主页：https://platform.openai.com
- 文档：https://platform.openai.com/docs/guides/images
- 控制台：https://platform.openai.com/api-keys → Create new secret key
- 环境变量：`OPENAI_API_KEY`，可选 `OPENAI_BASE_URL`、`OPENAI_MODEL`
- 权限：图像生成
- 轮换 / 吊销：密钥页 Revoke 后新建
- 验证：`img.py list --channels` 显示 openai 可用

## 4. OpenRouter（国内直连常被地域拦截，需要代理）

- 主页：https://openrouter.ai
- 文档：https://openrouter.ai/docs
- 控制台：https://openrouter.ai/keys → Create Key
- 环境变量：`OPENROUTER_API_KEY`，代理 `OPENROUTER_PROXY`（或在 `config/user.yaml` 给该渠道配 `proxy`）
- 权限：图像模态调用
- 轮换 / 吊销：Keys 页删除后新建
- 验证：`img.py --theme "…" --channel openrouter --explain`

## 5. 私有 / 自建 endpoint

在 `config/channels.yaml` 追加一段，或用 `config/user.yaml` 覆盖：

```yaml
channels:
  - id: my-endpoint
    adapter: openai_images
    base_url: https://my-endpoint.example.com/v1
    model: {default: "my-image-model"}
    auth: {type: bearer, key: "${MY_ENDPOINT_API_KEY}"}
```

示例见 `examples/`。

## 6. 零凭据也能出图

不配任何密钥时，`builtin` 渠道保底：由宿主自身出图，`img.py` 打印 handoff JSON 并以退出码 10 结束。
限制：不支持 seed、多张并列、参考图垫图、负面词，结果不可复现。需要这些能力时配置一个真实渠道。

## 7. 自检

```bash
python3 scripts/img.py doctor
python3 scripts/check_environment.py --format text
```
