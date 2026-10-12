# 适配器契约

5 种 adapter 覆盖所有 HTTP 生图接口。请求与响应的解析规则如下。

## 1. openai_images

```
POST {base_url}/images/generations
Authorization: Bearer {key}
{
  "model": "...", "prompt": "...", "n": 1, "size": "1664x928",
  "response_format": "b64_json",
  "negative_prompt": "...",   // 仅当 caps.negative_prompt
  "seed": 123                 // 仅当 caps.seed
}
```

响应按 `data[].b64_json` → `data[].url` → `images[].url` 顺序取第一张。

适用：SiliconFlow、OpenAI、任何 OpenAI 兼容图接口、私有 endpoint。

## 2. openai_chat

```
POST {base_url}/chat/completions
{
  "model": "...",
  "messages": [{"role":"user","content":"…"}],
  "modalities": ["image","text"]
}
```

需要垫图时改为多段 content：`[{type:text},{type:image_url}]`。

响应取 `choices[0].message.images[].image_url.url`，其次 `choices[0].message.content[].image_url.url`。支持 `data:` 前缀与 http(s) 地址。

适用：OpenRouter、Gemini 类对话式出图。

## 3. dashscope

```
POST {base_url}/api/v1/services/aigc/multimodal-generation/generation
{
  "model": "...",
  "input": {"messages":[{"role":"user","content":[{"text":"…"}]}]},
  "parameters": {"size":"1664*928","prompt_extend":false,"watermark":false,"n":1,
                 "negative_prompt":"…"}
}
```

响应取 `output.choices[0].message.content[].image`（URL），下载保存。
`output.code` 非空即视为失败。

适用：阿里云百炼 Qwen-Image。

## 4. generic

兜底任意 HTTP 接口，在渠道里补一段 `generic`：

```yaml
    generic:
      url: https://example.com/api/draw
      request_template: {model: "${model}", prompt: "${prompt}", size: "${size}"}
      response_jsonpath: data.image_url
```

`request_template` 支持 `${prompt}` `${model}` `${size}` 占位；`response_jsonpath` 按 `.` 分段取值，数组用下标（`data.0.url`）。

## 5. builtin

不由脚本发请求。命中时 `img.py` 打印如下 JSON 并以退出码 10 结束：

```json
{"action":"builtin_image_gen","prompt":"…","size":"1664x928","negative":"…","out":"/abs/o.png","scene":"article-illustration"}
```

宿主编排层读到退出码 10 后调用自身出图能力，把图片写到 `out`。

## 6. 通用行为

- 代理：仅当渠道 `proxy` 非空时对该渠道生效，`region: needs_proxy` 的渠道必配。
- 尺寸：超过 `caps.max_side` 自动等比降档并对齐到 8 的倍数。
- 负面词：`caps.negative_prompt` 为 false 时丢弃，不报错。
- 超时：默认 300 秒，`--timeout` 覆盖。
- 失败：打印 `[渠道:模型] 原因`，自动尝试回退链下一个候选。
