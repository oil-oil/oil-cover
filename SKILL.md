---
name: oil-cover
description: 生成小红书和 B 站 AI 工具实操视频封面，支持脚本模式与 Agent 自主模式、真实视频证据、三画幅输出和可选创作者头像。仅在用户明确提到 oil-cover、$oil-cover、使用 oil-cover 或指定本 Skill 时触发；普通封面、首图、视频封面请求不要自动触发。
---

# oil-cover

为小红书 AI 工具实操内容生成稳定、清楚、干净、精致的视频封面。默认使用配置的脚本完成选帧、提示词生成和外置生图。

## 两种执行模式

- **模式一 · 脚本模式（默认）**：把活儿交给 `generate_oil_cover.py`，由脚本用 ZenMux 上的 Gemini 选帧分析、调 `gpt-image-2` 生成无人物底图；用户配置启用创作者头像时，再用确定性代码把透明头像合成到右下角。需要 Python + ffmpeg + Pillow + ZenMux key。下面「默认入口」到「输出说明」描述的都是这一模式。
- **模式二 · Agent 自主执行**：不调外部 Gemini、不需要 ZenMux key，由执行的 Agent 自己读 SOP 完成选帧、分析和生图；用户配置启用头像时，再调用项目脚本的头像合成函数。完整流程见 `references/agent-native-flow.md`。

## 安装位置与用户配置

不要假设用户名、Skill 安装目录、视频库、脚本、素材镜像或密钥位置。

- `SKILL_DIR`：当前这份 `SKILL.md` 所在目录。
- 用户配置：`${OIL_COVER_CONFIG:-$HOME/.oil-cover/config.json}`。它属于本机用户，不进入 Skill 仓库。
- Skill 内脚本：`$SKILL_DIR/scripts/generate_oil_cover.py`。若安装包没有脚本，读取配置里的 `script_path`；两者都不存在时说明安装不完整，不要猜个人目录。
- Skill 内资产：`$SKILL_DIR/assets/`。额外素材镜像仅从配置 `product_asset_mirror` 读取。
- API key：优先使用 `ZENMUX_API_KEY`；备用文件仅从 `api_key_file` 配置或 `--api-key-file` 读取。不要把 key 或个人绝对路径写进 Skill 仓库。

支持的用户配置：

```json
{
  "mode": "agent-native",
  "creator_name": "optional creator name",
  "script_path": "/optional/path/to/generate_oil_cover.py",
  "video_library_root": "/optional/path/to/video-library",
  "product_asset_mirror": "/optional/path/to/shared-product-assets",
  "api_key_file": "/optional/path/to/zenmux-key",
  "creator_portrait": {
    "enabled": false,
    "path": "/optional/path/to/portrait.png"
  }
}
```

路径允许使用 `~`，读取后必须展开。没有配置 `video_library_root` 时，所有持久产物默认跟随输入视频。配置后，同一视频的持久资源统一放进 `<video_library_root>/<视频标题>/`；从导出暂存目录开始处理时，先无覆盖地归位源视频，再生成字幕、封面和 sidecar。

### 选哪个模式（设一次，以后不问）

每次触发 oil-cover 时按这个顺序决定：

1. 先读用户配置的 `mode` 字段。
2. 已设为 `script` 或 `agent-native` → **直接按该模式执行，不再询问**。
3. 未设置（第一次）→ 问用户一次默认想用哪种模式，说明这是一次性设置；拿到答案后更新用户配置，再按选择执行。保留文件里的其他配置键，不要整份覆盖：

   ```bash
   mkdir -p "$(dirname "${OIL_COVER_CONFIG:-$HOME/.oil-cover/config.json}")"
   # 合并写入 {"mode":"agent-native"}，或设为 "script"
   ```

4. 用户随时可说「切换 / 改成 X 模式」覆盖默认（重写该文件），或在单次任务里临时指定某模式而**不**改默认偏好。

**前提与回退**：模式二要求执行 Agent 具备多模态视觉 + 支持参考图的生图工具（在 Codex 里就是 `.system/imagegen` 的内置 `image_gen` 工具）；Claude Code 当前没有内置生图工具。若 `mode=agent-native` 但当前环境跑不了生图这一步，说明情况并给两条路——去 Codex 跑，或本次临时回退脚本模式——不要静默失败，也不要擅自改掉用户的默认偏好。

走模式二时，先完整读 `references/agent-native-flow.md` 和 `references/cover-rules.md`，按 SOP 执行，**忽略下面所有针对脚本的参数与说明**。

## 封面标题提炼（执行者职责）

封面主标题由执行本 skill 的 Agent 在跑脚本**之前**自己提炼，不交给脚本里的分析模型做，避免它理解错内容：

- 视频标题只是主题输入，封面主标题不必和它一模一样。要突出这条视频最有分量的重点：结论、评价、对比、数字。
- 有字幕或文稿时（`.srt`/`.ass`/`.txt`，或视频旁的同名字幕文件）先通读一遍再提炼。`.ass`/`.srt` 先抽成纯文本（去掉时间轴和样式标记）。优先借用视频里的原话强词（例如口播里的「目前最强」「指哪打哪」这类明确判断），忠于内容，不夸大、不编造评价。
- 没有字幕、文稿或用户补充时，才退回视频标题本身做克制的精简。
- 提炼结果通过 `--title` 传给脚本；抽好的纯文本字幕通过 `--subtitle` 传入，供分析模型选帧、写副标题和点缀使用。分析模型会把 `--title` 当作已定稿的封面主标题，只做断行和排版，不再改写。

## 默认入口

默认运行：

```bash
python3 "$OIL_COVER_SCRIPT" \
  --video "<视频路径>" \
  --title "<提炼后的封面主标题>" \
  --subtitle "<纯文本字幕/文稿路径，有则必传>" \
  --topic "<补充背景>"
```

如果用户提供的是截图或已选关键帧：

```bash
python3 "$OIL_COVER_SCRIPT" \
  --image "<截图或关键帧路径>" \
  --logo "<可选 Logo 路径>" \
  --title "<标题或主题>" \
  --topic "<补充背景>"
```

默认不传 `--aspect`，脚本会并行生成小红书 `3:4` 竖屏版、通用/B 站首页主封面 `4:3` 横屏版和 B 站个人空间伴随版 `16:9` 横屏版。发布 B 站时默认上传 `_4x3.png`，平台再同步生成个人空间 `16:9` 版本。只重跑单个画幅时使用 `--aspect 3x4`、`--aspect 4x3` 或 `--aspect 16x9`。

## 进阶参数

- `--subtitle <脚本/字幕/转录文件>`：把上下文喂给 Gemini，帮助判断主题、标题措辞和证据选择。有完整文稿时优先加上。
- `--logo <Logo 路径>`：可多次传入多个产品 Logo 作为参考资产。
- 如果标题、字幕、视频画面或截图能明确判断主产品有 Logo，但 `references/product-assets.md` 暂时没有对应资产，先联网寻找官方或可信来源的透明 PNG，归档到 `$SKILL_DIR/assets/product-logos/`；配置了 `product_asset_mirror` 时再同步到镜像目录。通过 `--logo` 传给脚本，高频复用的产品同步补充到 `product-assets.md` 和脚本的自动匹配表。
- 取帧策略是「本地预筛」：脚本用 ffmpeg 低分辨率扫描整段视频，对每帧算清晰度(拉普拉斯方差)、亮度、内容度，硬过滤掉黑屏/纯白/纯色/loading/模糊帧，再按时间分桶取每段最清晰的一帧，产出若干**真实高清候选**交给分析模型按语义挑最佳帧。全程不调模型选帧、不上传整段视频。这是唯一的自动取帧路径，没有旧的「视频选帧」/均匀盲采兜底——预筛若失败会直接报错，不会静默降级。
- `--frame-count <N>`：本地预筛产出多少个候选帧供分析模型挑选，默认 8。候选越多模型选择越好，但分析请求越大。
- `--scan-fps <N>`：本地预筛扫描的采样帧率，默认 0=自动（≤5 分钟视频用 2fps，更长用 1fps）。想抓更细的瞬间可调高。
- `--candidate-seconds 1,8,24.5`：手动指定取帧时间点，跳过本地预筛。已经知道哪几秒是关键画面时用。
- `--aspect all|both|3x4|4x3|16x9`：默认 `all` 并行生成三版；`both` 为兼容旧调用，只生成 `3:4` 和 `4:3`；单独重跑时只生成指定画幅。
- `--bilibili-size <尺寸>`：B 站个人空间 `16:9` 伴随版的 API 尺寸，默认 `1280x720`；B 站默认上传源仍是 `4:3` 主封面。
- 副标题默认放开。如需禁用副标题、让外层只剩主标题，传 `--no-allow-subtitle`。
- 创作者头像由本地代码在生图后合成，不作为 Gemini 或 `gpt-image-2` 的参考图上传。是否启用及素材路径来自用户配置；公开 Skill 默认关闭。默认布局参数为：3:4 宽约 55%、顶部约 58%、向右越界约 6%；4:3 宽约 38%、顶部约 40%、向右越界约 3%；16:9 宽约 32%、顶部约 40%、右侧内收约 2%。
- 用户明确要求无人物封面时传 `--no-default-creator-portrait`。配置启用头像时默认保留；未配置时保持无人物。

排查与验证：

- `--dry-run`：不调任何 API，只准备本地文件和 prompt，用于核对路径、规则文件和素材是否就位。
- `--skip-generate`：只跑 Gemini 分析和写 prompt，不调用图片 API。用来看 Gemini 选了哪一帧、标题怎么断行、prompt 写成什么样。
- `--generation-only`：用 `/images/generations` 而非 `/images/edits`，屏幕帧和 Logo 参考图不上传给图片 API；头像启用时始终只在本地合成。

## 脚本职责

- 脚本路径：优先 `$SKILL_DIR/scripts/generate_oil_cover.py`，否则使用用户配置 `script_path`
- 默认分析模型：`google/gemini-3.5-flash`
- 默认生图模型：`openai/gpt-image-2`
- 默认规则文件：`references/cover-rules.md`
- 默认输出位置：视频（或图片）所在目录。最终封面命名 `<视频名>_3x4.png`、`<视频名>_4x3.png`、`<视频名>_16x9.png`，直接落在影片旁边方便查找；分析、prompt、原始响应等中间产物收进 `<视频名>.oil-cover/` 子目录。传 `--output-root` 可改到别处。

脚本负责用 ffmpeg 本地扫描+评分预筛出若干高清候选帧（默认策略，无需调模型），把候选交给 Gemini 多模态分析、由它按语义选出最佳封面帧并生成封面方案和提示词、保存 sidecar、并行调用 Zenmux 图片 API、生成无人物底图。用户配置启用头像时，再用 Pillow 把透明头像按画幅参数合成到右下角；头像不会进入 Gemini 或图片 API 的参考图列表。底图保存在 `<视频名>.oil-cover/<画幅>.generated-base.png`，合成记录保存在 `portrait_composite.json`，最终封面写到影片目录。本地预筛的打分明细写在 `<视频名>.oil-cover/frame_selection_local.json`。

## 何时读取参考文件

- 走模式二（Agent 自主执行）时，先完整读 `references/agent-native-flow.md`（流程 SOP）和 `references/cover-rules.md`（视觉规范）。
- 日常生成封面时（模式一），不需要手动读取完整视觉规范；脚本会把 `references/cover-rules.md` 传给 Gemini。
- 修改视觉规则、排查提示词遗漏、评审模型输出质量或调整脚本 guard 时，读取 `references/cover-rules.md`。
- 判断产品 Logo 或产品资产时，读取 `references/product-assets.md`。
- 新增产品 Logo、排查资产缺失或判断可信来源时，读取 `references/product-assets.md` 并按里面的补充规则执行。
- 如果用户要求复刻特定冲击型科技封面风格，读取 `references/impact-tech-cover-style.md`。

## 不可违反

- 只有用户明确提到 `oil-cover`、`$oil-cover`、`使用 oil-cover` 或指定这个 Skill 时，才使用本 Skill。
- 生图模型必须一次性生成完整无人物底图，包括真实屏幕证据、标题、产品标识、点缀和风格化效果；仅在配置启用头像时预留右下角安全区。
- 本地后处理只允许执行一项：配置启用头像时，把配置的透明头像按固定参数 alpha 合成到右下角。不要本地贴字、贴 Logo、拼其他图片、重排、裁切改版或视觉修补。
- 源截图、重建 UI 和生图底图不保留人物、人脸、头像、摄像头气泡和真人画中画；配置启用头像时，最终封面只允许出现这一张代码合成的头像，否则最终封面保持无人物。
- 绝对不要把历史案例或上一次任务里的产品名、模型名、关键词、品牌色和点缀带入当前封面。所有外层文字和点缀都必须来自当前视频、当前标题、当前字幕、当前截图或当前用户补充信息。
- 默认同时交付 `3:4`、`4:3` 和 `16:9` 三版；单独重跑时只生成指定画幅。
- 每次生图前必须保存 `.prompt.md` sidecar；生成后必须保留 `manifest.final.json`、`analysis.json`、`cover_plan.md`、API 原始响应和最终图片。
- 写 `analysis.json`、`cover_plan.md`、`.prompt.md`、生成记录以及本 skill 自身的参考文档时，只描述当前这一版的最终状态，不要塞编辑历史元数据（「更新于 X」「第 N 版」「原 X 现改为 Y」「本次修正了 Z」这类），不要把文档写成或改成 changelog；返工重跑时直接覆盖成新版本，而不是在文档里追加一段修改历史。
- 不要把 Zenmux API key 写进提示词、sidecar、日志或最终回复。

## 输出说明

完成后说明：

- 最终图片路径
- 对应 `.prompt.md` sidecar 路径
- `analysis.json` 和 `cover_plan.md` 路径
- 使用的参考帧、Logo 或素材
- 头像合成素材、参数和 `portrait_composite.json` 路径；说明头像未作为生图参考图上传
- 是否需要按 `--aspect 3x4`、`--aspect 4x3` 或 `--aspect 16x9` 重跑某一版
