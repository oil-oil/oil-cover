# AI 产品参考资产

本 Skill 内置常用 AI 产品 Logo，位置是 `assets/product-logos/`。默认使用透明背景 PNG；旧 SVG 保留为备用素材。需要同步到外部素材库时，只使用用户配置里的 `product_asset_mirror`，不要在 Skill 中写个人绝对路径。

## 资产列表

| 产品 | 文件 | 用法 |
| --- | --- | --- |
| OpenAI | `openai.png` | OpenAI、ChatGPT、Codex 生态主题的辅助识别 |
| Codex | `codex-openai.png` | Codex、Coding Agent、代码工作流主题的主视觉锚点 |
| Claude | `claude.png` | Claude、Claude 模型、Anthropic 生态主题 |
| Claude Code | `claude-code.png` | Claude Code 实操、CLI、Agent 编程主题 |
| Anthropic | `anthropic.png` | Anthropic 公司或模型生态主题 |
| Cursor | `cursor.png` | Cursor、IDE 对比、AI 编程工具主题 |
| Gemini | `gemini.png` | Gemini、Google AI、模型对比主题 |
| Kimi | `kimi.png` | Kimi、Kimi K3、Kimi Code、Moonshot AI 主题 |
| LongCat | `longcat.png` | LongCat、LongCat 2.0、美团模型和模型对比主题 |
| GitHub Copilot | `github-copilot.png` | Copilot、GitHub 工作流、IDE 辅助主题 |
| GitHub | `github.png` | GitHub、仓库、Issue、PR、Actions 和协作开发主题 |
| Ego Lite | `ego-lite.png` | ego-browser、Ego Lite 浏览器、浏览器自动化主题 |
| Selector | `selector.png` | Selector、Visual Element Picker、元素选择器和网页元素定位主题 |

## 使用规则

- 优先把 Logo 当作参考图或画面锚点，不要让生图模型重新发明产品标识。
- Logo 可以出现在封面的视觉系统里，但不要做成官方宣传物。
- 如果用户提供了真实产品截图，截图优先级高于 Logo。
- 生成前说明用了哪些参考图，生成后把使用的 Logo 文件名记录在提示词说明里。
- 如果主产品明确有 Logo，但本清单没有对应 PNG，先寻找官方品牌页、产品官网、GitHub 仓库、可信图标库或已安装 App 包内图标；优先使用透明背景 PNG。只有找到的来源可信、图形清晰、没有水印，才补进资产目录。
- 如果来源只提供 SVG、ICNS 或 favicon，可以转换成 640x640 RGBA PNG，并保留来源说明；不要把低清截图、搜索结果缩略图或非官方改版图标当成长期资产。
- 新增高频产品后，同步更新本文件、配置的 `generate_oil_cover.py` 自动匹配表；设置了 `product_asset_mirror` 时再更新镜像目录里的说明文件。

## 来源

- OpenAI 品牌页：`https://openai.com/brand/`
- Claude Code 文档：`https://code.claude.com/docs/en/overview`
- Lobe Icons PNG package：`@lobehub/icons-static-png@1.91.0`
- Lobe Icons：`https://lobehub.com/icons`
- Lobe Icons GitHub：`https://github.com/lobehub/lobe-icons`
- Ego Lite app icon：`/Applications/ego lite.app/Contents/Resources/app.icns`
- Selector favicon：`https://oil-oil.github.io/selector/assets/favicon.svg`
- LongCat 2.0 官方 Hugging Face 仓库：`https://huggingface.co/meituan-longcat/LongCat-2.0/blob/main/figures/longcat_logo.svg`
- Kimi 官网 favicon：`https://www.kimi.com/favicon.ico`；长期资产使用同图形的 Lobe Icons 640×640 透明 PNG / SVG
- Simple Icons CDN：`https://cdn.simpleicons.org/`
