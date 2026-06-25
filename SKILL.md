---
name: oil-cover
description: 小红书 AI 工具实操内容的封面生成 Skill（作者 oil 欧呦）。仅当用户明确提到 oil-cover、$oil-cover、使用 oil-cover 或指定这个 Skill 时触发；普通封面、首图、视频封面请求不要自动触发。
---

# oil-cover

为小红书 AI 工具实操内容生成稳定、清楚、干净、精致的视频封面。默认使用项目脚本完成选帧、提示词生成和外置生图。

## 两种执行模式

- **模式一 · 脚本模式（默认）**：把活儿交给 `generate_oil_cover.py`，由脚本用 ZenMux 上的 Gemini 选帧分析、调 `gpt-image-2` 生图。需要 Python + ffmpeg + ZenMux key。下面「默认入口」到「输出说明」描述的都是这一模式。
- **模式二 · Agent 自主执行**：不调脚本、不需要外部 Gemini、不需要 ZenMux key，由执行的 Agent 自己读 SOP 端到端完成——用自身多模态视觉选帧分析，用自身的图像生成工具（图生图）出图。完整流程见 `references/agent-native-flow.md`。

### 选哪个模式（设一次，以后不问）

模式选择记在 `~/.oil-cover/config.json`，跨 Claude / Codex 共享。每次触发 oil-cover 时按这个顺序决定：

1. 先读 `~/.oil-cover/config.json` 的 `mode` 字段。
2. 已设为 `script` 或 `agent-native` → **直接按该模式执行，不再询问**。
3. 未设置（第一次）→ 问用户一次默认想用哪种模式，说明这是一次性设置；拿到答案后写入配置，再按选择执行：

   ```bash
   mkdir -p ~/.oil-cover
   printf '{\n  "mode": "agent-native"\n}\n' > ~/.oil-cover/config.json   # 或 "script"
   ```

4. 用户随时可说「切换 / 改成 X 模式」覆盖默认（重写该文件），或在单次任务里临时指定某模式而**不**改默认偏好。

**前提与回退**：模式二要求执行 Agent 具备多模态视觉 + 支持参考图的生图工具（在 Codex 里就是 `.system/imagegen` 的内置 `image_gen` 工具）；Claude Code 当前没有内置生图工具。若 `mode=agent-native` 但当前环境跑不了生图这一步，说明情况并给两条路——去 Codex 跑，或本次临时回退脚本模式——不要静默失败，也不要擅自改掉用户的默认偏好。

走模式二时，先完整读 `references/agent-native-flow.md` 和 `references/cover-rules.md`，按 SOP 执行，**忽略下面所有针对脚本的参数与说明**。

## 默认入口

默认运行：

```bash
python3 ~/.claude/skills/oil-cover/scripts/generate_oil_cover.py \
  --video "<视频路径>" \
  --title "<标题或主题>" \
  --topic "<补充背景>"
```

如果用户提供的是截图或已选关键帧：

```bash
python3 ~/.claude/skills/oil-cover/scripts/generate_oil_cover.py \
  --image "<截图或关键帧路径>" \
  --logo "<可选 Logo 路径>" \
  --title "<标题或主题>" \
  --topic "<补充背景>"
```

默认不传 `--aspect`，脚本会并行生成 `3:4` 竖屏版和 `4:3` 横屏版。只重跑单个画幅时使用 `--aspect 3x4` 或 `--aspect 4x3`。

## 进阶参数

- `--subtitle <脚本/字幕/转录文件>`：把上下文喂给 Gemini，帮助判断主题、标题措辞和证据选择。有完整文稿时优先加上。
- `--logo <Logo 路径>`：可多次传入多个产品 Logo 作为参考资产。
- 如果标题、字幕、视频画面或截图能明确判断主产品有 Logo，但 `references/product-assets.md` 暂时没有对应资产，先联网寻找官方或可信来源的透明 PNG，归档到 `assets/product-logos/`，再通过 `--logo` 传给脚本。高频复用的产品要同步补充到 `product-assets.md` 和脚本的自动匹配表。
- 默认取帧策略是「视频选帧」：脚本把整段视频压成 1fps 小 clip 发给分析模型，让它看完全片、按内容挑出最适合做封面的那一刻（带理由），再抠那一帧走后续流程，比盲采等距帧准得多。
- `--frame-select video|sample`：取帧策略，默认 `video`（让模型看视频选帧）；`sample` 回退到旧的均匀盲采。
- `--select-count <N>`：video 模式下让模型返回几个候选时刻，默认 1（信任它从全片选的单帧）。
- `--select-fps` / `--select-width`：压缩 clip 的帧率与宽度，默认 1fps / 512px。
- `--candidate-seconds 1,8,24.5`：手动指定取帧时间点，跳过自动选帧。已经知道哪几秒是关键画面时用。
- `--frame-count <N>`：仅在 `--frame-select sample` 回退模式下生效，控制盲采候选数，默认 12。
- `--aspect both|3x4|4x3`：默认 `both` 并行生成两版；单独重跑时只生成指定画幅。
- 副标题默认放开。如需禁用副标题、让外层只剩主标题，传 `--no-allow-subtitle`。

排查与验证：

- `--dry-run`：不调任何 API，只准备本地文件和 prompt，用于核对路径、规则文件和素材是否就位。
- `--skip-generate`：只跑 Gemini 分析和写 prompt，不调用图片 API。用来看 Gemini 选了哪一帧、标题怎么断行、prompt 写成什么样。
- `--generation-only`：用 `/images/generations` 而非 `/images/edits`，参考图不上传给图片 API。

## 脚本职责

- 脚本路径：`scripts/generate_oil_cover.py`（相对本 skill 安装目录，例如 `~/.claude/skills/oil-cover/scripts/generate_oil_cover.py`；Codex 环境为 `~/.codex/skills/oil-cover/scripts/`）
- 默认分析模型：`google/gemini-3.5-flash`
- 默认生图模型：`openai/gpt-image-2`
- 默认规则文件：`references/cover-rules.md`
- 默认输出位置：视频（或图片）所在目录。最终封面命名 `<视频名>_3x4.png`、`<视频名>_4x3.png`，直接落在影片旁边方便查找；分析、prompt、原始响应等中间产物收进 `<视频名>.oil-cover/` 子目录。传 `--output-root` 可改到别处。

脚本负责把整段视频压成小 clip 让分析模型看完、按内容选出最佳封面帧并抠出全分辨率帧，调用 Gemini 多模态分析生成封面方案和提示词、保存 sidecar、并行调用 Zenmux 图片 API、把最终封面写到影片目录并保存响应日志。

## 何时读取参考文件

- 走模式二（Agent 自主执行）时，先完整读 `references/agent-native-flow.md`（流程 SOP）和 `references/cover-rules.md`（视觉规范）。
- 日常生成封面时（模式一），不需要手动读取完整视觉规范；脚本会把 `references/cover-rules.md` 传给 Gemini。
- 修改视觉规则、排查提示词遗漏、评审模型输出质量或调整脚本 guard 时，读取 `references/cover-rules.md`。
- 判断产品 Logo 或产品资产时，读取 `references/product-assets.md`。
- 新增产品 Logo、排查资产缺失或判断可信来源时，读取 `references/product-assets.md` 并按里面的补充规则执行。
- 如果用户要求复刻特定冲击型科技封面风格，读取 `references/impact-tech-cover-style.md`。

## 不可违反

- 只有用户明确提到 `oil-cover`、`$oil-cover`、`使用 oil-cover` 或指定这个 Skill 时，才使用本 Skill。
- 最终封面必须一次性生成完整画面，包括真实屏幕证据、标题、产品标识、点缀和风格化效果。
- 不要在生成后用本地工具贴字、贴 Logo、拼图、重排、裁切改版或视觉修补。
- 封面不保留人物、人脸、头像、摄像头气泡和真人画中画。
- 绝对不要把历史案例或上一次任务里的产品名、模型名、关键词、品牌色和点缀带入当前封面。所有外层文字和点缀都必须来自当前视频、当前标题、当前字幕、当前截图或当前用户补充信息。
- 默认同时交付 `3:4` 和 `4:3` 两版；单独重跑时只生成指定画幅。
- 每次生图前必须保存 `.prompt.md` sidecar；生成后必须保留 `manifest.final.json`、`analysis.json`、`cover_plan.md`、API 原始响应和最终图片。
- 不要把 Zenmux API key 写进提示词、sidecar、日志或最终回复。

## 输出说明

完成后说明：

- 最终图片路径
- 对应 `.prompt.md` sidecar 路径
- `analysis.json` 和 `cover_plan.md` 路径
- 使用的参考帧、Logo 或素材
- 是否需要按 `--aspect 3x4` 或 `--aspect 4x3` 重跑某一版
