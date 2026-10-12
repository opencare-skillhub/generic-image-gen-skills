# HTML → PNG 渲染管线

`infographic` 与 `diagram` 场景走这条管线：**不调用生图接口，零 token，文字精确**。

## 1. 调用

```bash
python3 scripts/img.py --scene infographic --html /abs/page.html --out /abs/output.png
```

等价直接调用：

```bash
bash scripts/html2png.sh /abs/page.html /abs/output.png 1100 1240
```

参数：`<输入 html|url> <输出 png|jpg> [视口宽=1100] [输出宽=1240]`

## 2. 渲染器优先级

| 优先级 | 渲染器 | 探测方式 |
|---|---|---|
| 1 | Gotenberg | `$GOTENBERG_URL`，否则探测 `http://gotenberg:3000`、`http://127.0.0.1:3980` 的 `/health` |
| 2 | 本地 Chromium | `chromium` / `chromium-browser` / `google-chrome` / `google-chrome-stable` |

两者都不可用时退出码 127 并提示启动渲染器；此时改用生图场景，或交付 HTML 由用户自行导出。

## 3. 自动能力

- 同目录的 CSS、图片、字体、JS 自动打包上传（Gotenberg 路径）
- 按左右 margin 中位色检测背景并裁掉上下白边
- `.jpg` / `.jpeg` 后缀输出 JPEG（quality=90），其余输出 PNG
- 需要 Pillow 与 numpy；缺失时退出码 127 并提示解释器

## 4. 编写建议

- 布局用 CSS Grid / Flexbox，图表用内联 SVG
- 配色写成 CSS 变量，便于整套换色
- 字体用系统字体栈，避免外部字体依赖
- 先用 `--viewport 800` 确认布局，再放大到最终宽度

## 5. 与生图管线的分工

同一份产物里可以混用：

- 插画、氛围图、人物图 → 生图管线
- 信息图、数据图、流程图 → HTML 管线

两者输出宽度保持一致即可。
