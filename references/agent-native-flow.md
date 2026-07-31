# oil-cover · Agent 自主执行模式（SOP）

这是 oil-cover 的**第二种执行轨道**。和默认的脚本模式不同，本模式**不用 `generate_oil_cover.py` 做选帧、分析或生图，也不需要外部 Gemini 和 ZenMux key**：由执行的 Agent 用自身多模态视觉直接选帧和分析，用自身的图像生成工具生成无人物底图；用户配置启用头像时，再调用项目脚本的本地头像合成入口。

## 何时走这一轨

- 用户明确说「自主模式 / 你自己执行 / 别用脚本 / 让 Codex 跑 oil-cover」之类。
- 或当前环境没有脚本依赖（Python / ffmpeg / ZenMux key）但有可用的图像生成工具。

否则默认仍走脚本模式（见 `SKILL.md`）。

## 前提（不满足就别硬跑）

执行的 Agent 必须同时具备：

1. **多模态视觉**：能直接看视频抽出的帧 / 截图，做选帧和内容分析。
2. **支持传参考图的图像生成工具（图生图）**：能把选定的真实屏幕证据帧 + 产品 Logo 作为输入图喂进去，一次性整图生成。

**在 Codex 环境，这个工具就是系统 skill `.system/imagegen` 的内置 `image_gen` 工具**（无需 `OPENAI_API_KEY`，支持参考图）。本 SOP 第六步默认走它，CLI（`scripts/image_gen.py`）只是 fallback。

Claude Code 当前**没有**内置图像生成工具，第六步通常要在 Codex 等带 image gen 工具的环境里执行。如果执行环境只有纯文生图、不能传参考图，先告诉用户这会牺牲「真实屏幕证据 + 真实 Logo」的保真度，由用户决定是否继续。不要自行本地拼贴截图、Logo、文字或其他画面元素；配置启用头像时，第七步的头像合成是唯一允许的本地视觉后处理。

## 视觉规范的来源

本 SOP **只规定「Agent 自己怎么跑这套流程」，不重复视觉标准**。所有视觉判断——选帧标准、内容归因、构图、背景层、字体标题、点缀、质检、提示词骨架——一律以 `references/cover-rules.md` 为准。开跑前必须先完整读一遍 `cover-rules.md`。

## 与脚本模式的对照

| 环节 | 脚本模式（默认） | Agent 自主模式（本文件） |
| --- | --- | --- |
| 选帧 | Gemini 看 1fps 小 clip 选帧 | Agent 自己抽帧、看图、按 cover-rules 选 |
| 分析 | Gemini 多模态 + cover-rules | Agent 自己分析 + cover-rules |
| 生图 | ZenMux `gpt-image-2`（images/edits） | Agent 自带 image gen 工具（图生图） |
| 头像（可选） | 配置启用时由本地代码合成 | 调同一脚本的 `--composite-base` 入口 |
| 质检返工 | 脚本自动质检重跑 | Agent 自查底图与合成结果，按需只重跑失败环节 |
| 中间产物 | 视频旁 `<视频名>.oil-cover/` | 视频旁 `<视频名>.oil-cover/` |
| 依赖 | Python + ffmpeg + ZenMux key | 仅 Agent 自身能力 |

## 产物目录约定

- 不使用跨项目的全局 run 目录。
- 视频、截图和所有持久 sidecar 必须聚合在同一视频目录。
- 中间产物统一放在视频或截图旁的 `<视频名>.oil-cover/`：`frames/`、`analysis.md`、`cover_plan.md`、三份 prompt、三张无人物底图、头像合成记录和生成记录。
- 最终三张封面写在同一视频目录：`<视频名>_3x4.png`、`<视频名>_4x3.png`、`<视频名>_16x9.png`，不在其他位置保留重复副本。
- 配置了 `video_library_root` 时，先按 `SKILL.md` 的路径规则把源视频无覆盖地归入 `<video_library_root>/<视频标题>/`。

## 执行步骤

### 1. 建工作目录

```bash
VIDEO_DIR="<视频或截图所在目录>"
VIDEO_STEM="<视频或截图文件名，不含扩展名>"
RUN_DIR="$VIDEO_DIR/$VIDEO_STEM.oil-cover"
mkdir -p "$RUN_DIR/frames"
```

### 2. 取帧 / 选帧（对齐 cover-rules「证据选择」）

- **视频**：先看首帧判断它是实操界面还是片头/标题页（首帧规则见 cover-rules）。用 ffmpeg 在关键时间点抽若干候选帧到 `frames/`（有字幕/转录就结合内容定位关键时刻，没有就在时间线上铺开抽 4-8 帧）。Agent 逐帧看图，按 cover-rules 的选帧 + 可提炼性标准挑出最适合做封面的一帧，再从原视频抠出该时刻的全分辨率帧。
- **截图 / 已选关键帧**：直接用。
- 把**选了哪一帧、为什么**写进 `analysis.md`。
- 找不到合适实操画面时，说明缺口并请用户确认下一步，不要硬凑。

> 这一步是 Agent 用自身视觉判断，等价于脚本里 Gemini 看 clip 选帧。

### 3. 内容归因 + 视觉传达分析（对齐 cover-rules「视觉传达导演」「内容归因」）

在 `analysis.md` 里明确写出：主主题、主产品、承载界面、辅助品牌、一眼主语（0.5 秒内要读者看到的结果）、主证据、辅助证据、可牺牲信息。这些直接决定后面的 prompt。

### 4. 匹配 Logo（对齐 cover-rules「Logo 和参考素材」+ `product-assets.md`）

- 查 `references/product-assets.md` 和 `assets/product-logos/` 目录。
- 主产品能识别且有对应 PNG → 作为参考图（Image 2）。
- 能识别但清单里没有 → 按 `product-assets.md` 的补充规则联网找官方/可信透明 PNG，归档后再用。
- 实在没有独立 Logo → 用选定帧里的产品名/图标作品牌识别来源。
- 用户提供的真实截图优先级高于 Logo。

### 5. 写封面方案 + prompt（对齐 cover-rules「提示词骨架」）

- **先定封面主标题**：视频标题只是主题输入，封面主标题不必和它一模一样。有字幕或文稿时先通读（`.ass`/`.srt` 抽成纯文本再读），提炼突出重点、带结论/评价/对比/数字的短标题，优先借用口播原话里的强词；忠于内容，不夸大、不编造。没有字幕和文稿时才退回视频标题做克制精简。把选定标题和提炼依据写进 `analysis.md`。
- `cover_plan.md`：三版封面的方案要点（标题断行、强调词、构图、点缀、Logo 位置）。
- 用 cover-rules 的提示词骨架，给 `3:4`、`4:3` 和 `16:9` **各写一份完整 prompt**，分别存为 `cover_3x4.prompt.md`、`cover_4x3.prompt.md`、`cover_16x9.prompt.md`。
- 三份 prompt 都要让生图底图保持无人物。配置启用头像时，头像不作为参考图，并预留右下角安全区：3:4 为 `x=48%-100%, y=56%-100%`；4:3 为 `x=60%-100%, y=37%-100%`；16:9 为 `x=62%-100%, y=37%-100%`。标题、Logo、小标签和主证据不能进入安全区；安全区只延续背景和非关键屏幕细节，不生成头像、轮廓或占位卡。B 站默认上传独立生成的 4:3 首页主封面；16:9 仅作个人空间伴随版。
- **生图前必须先把 sidecar 写盘**，再调工具。

### 6. 生成无人物底图（调 Agent 自带 image gen 工具，图生图）

**这是 generate（带参考图），不是 edit** —— oil-cover 要把真实截图提炼重组成干净封面，不保留原图原样，所以截图和 Logo 都作为**参考图**喂入，而非编辑目标。

在 Codex 环境，默认用 `.system/imagegen` 的**内置 `image_gen` 工具**：

- **先把本地图加载进对话上下文**：内置 `image_gen` 只吃 prompt 文本，**没有文件路径 / `images[]` 参数**，所以本地的屏幕证据帧和 Logo 必须先用 `view_image` 工具加载进上下文，模型才看得到；再在 prompt 里按序号引用：Image 1 = 屏幕证据帧，Image 2 = 产品 Logo（如有）。
- **参考图是「参考」不是「复刻」**：参考图影响生成方向，Logo 的形状和品牌色会被参考，但细节会被模型重绘，做不到像素级复现——这点和脚本模式一致；prompt 里仍要写「保留产品识别、不要重新发明 Logo」尽量逼近。
- **一次性整图生成**完整底图（真实屏幕证据 + 标题 + 产品标识 + 点缀 + 风格化），底图不含任何人物；配置启用头像时，后续本地只允许合成该头像。
- 每个画幅一次独立调用（3:4、4:3、16:9 各一次）；环境支持并发调用时三版并行生成，不要用 `n` 出变体来凑三版。
- 画幅：在 prompt 里写死 `exact 3:4 portrait` / `exact 4:3 horizontal` / `exact 16:9 horizontal`。内置工具尺寸控制有限，先让它尽量贴近目标比例。若用户要求**严格精确**像素（脚本用的 `960x1280` / `1280x960` / `1280x720`，都是 16 的倍数、`gpt-image-2` 支持），而内置工具给不出，按 imagegen skill 的规则**先问用户**是否走 CLI fallback（`scripts/image_gen.py`，`gpt-image-2`，需 `OPENAI_API_KEY`）——不要为了普通的尺寸控制擅自切 CLI，更不要本地裁切凑比例。
- **底图落地**：把内置工具产物保存到 `$RUN_DIR`，命名为 `3x4.generated-base.png`、`4x3.generated-base.png`、`16x9.generated-base.png`。配置启用头像时，先不要把底图当成最终交付；未启用时可直接把底图作为最终封面。把工具、尺寸、屏幕帧和 Logo 参考图记进生成记录；启用头像时明确它没有上传给生图工具。
- 非 Codex 环境若没有等价工具，见上文「前提」，不要硬跑。

### 7. 按配置选择是否合成头像

配置未启用头像或用户明确要求无人物时，跳过本步骤，把无人物底图作为最终封面。配置启用时，分别调用项目脚本的本地入口；这一步不读取 API key，也不调用 Gemini、ZenMux 或图片模型：

```bash
python3 "$OIL_COVER_SCRIPT" \
  --composite-base "$RUN_DIR/3x4.generated-base.png" \
  --composite-aspect 3x4 \
  --composite-output "$VIDEO_DIR/${VIDEO_STEM}_3x4.png" \
  > "$RUN_DIR/3x4.portrait-composite.json"

python3 "$OIL_COVER_SCRIPT" \
  --composite-base "$RUN_DIR/4x3.generated-base.png" \
  --composite-aspect 4x3 \
  --composite-output "$VIDEO_DIR/${VIDEO_STEM}_4x3.png" \
  > "$RUN_DIR/4x3.portrait-composite.json"

python3 "$OIL_COVER_SCRIPT" \
  --composite-base "$RUN_DIR/16x9.generated-base.png" \
  --composite-aspect 16x9 \
  --composite-output "$VIDEO_DIR/${VIDEO_STEM}_16x9.png" \
  > "$RUN_DIR/16x9.portrait-composite.json"
```

头像是否启用及素材路径来自用户配置。启用时的固定布局参数为：3:4 头像宽 55%、顶部 58%、向右越界 6%；4:3 头像宽 38%、顶部 40%、向右越界 3%；16:9 头像宽 32%、顶部 40%、右侧内收 2%。不要为单次任务临时手调；用户明确要求修改默认时更新用户配置。

### 8. 自查质检（对齐 cover-rules「自动质检和返工」）

生成后逐项核对：标题可读、标题有内容相关装饰、产品 Logo 像参考图、屏幕物件有裁切感、主证据足够大、底图无人物/摄像头、无完整截图噪音、整体完整。配置启用头像时，再检查最终图只出现一张配置头像且不挡标题、Logo 或主证据。底图失败就写只修失败项的 prompt 并重跑底图；头像位置失败先检查画幅和输入尺寸，不要用临时贴图参数修一张特例。

### 9. 收尾

确认产物齐全：视频旁三张图，以及同目录 `<视频名>.oil-cover/` 里的 `analysis.md` / `cover_plan.md` / 三份 `.prompt.md` / 生成记录 / 无人物底图。

## 不可违反（继承 SKILL.md，本模式同样适用）

- 生图工具必须一次性生成完整无人物底图；配置启用头像时，本地后处理只允许调用第 7 步合成该头像。不要本地贴字、贴 Logo、拼其他图片、重排、裁切改版或视觉修补。
- 源截图、重建 UI 和底图不保留人物、人脸、头像、摄像头气泡和真人画中画；配置启用头像时，最终图只允许出现代码合成的这一张头像，否则最终图保持无人物。
- 绝对不要把历史案例或上一次任务里的产品名、模型名、关键词、品牌色和点缀带入当前封面；所有外层文字和点缀只能来自当前视频、当前标题、当前字幕、当前截图或当前用户补充信息。
- 默认同时交付 `3:4`、`4:3` 和 `16:9` 三版；单独重跑时只生成指定画幅。
- 生图前必存 `.prompt.md` sidecar；生成后保留 `analysis.md`、`cover_plan.md`、三份 prompt、生成记录和最终图片。
- `analysis.md`、`cover_plan.md`、三份 `.prompt.md`、生成记录只写当前最终状态；返工重跑（第 7 步）把它们整份覆盖成新版本，不要追加「第一版 / 第二版 / 本次修正了 X」这类编辑历史，也不要把文档写成 changelog。
- 本模式不用 ZenMux key；若执行环境用到任何 key，不得写进 prompt、sidecar、日志或最终回复。

## 输出说明

完成后说明：

- 三张最终封面路径（视频旁）。
- `<视频名>.oil-cover/` 路径（含 `analysis.md` / `cover_plan.md` / 三份 `.prompt.md`）。
- 使用的参考帧、Logo；配置启用头像时再说明头像素材，并明确头像未作为生图参考图上传。
- 配置启用头像时说明头像合成记录路径。
- 是否需要单独重跑 `3:4`、`4:3` 或 `16:9` 某一版。
