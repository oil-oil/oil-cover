# oil-cover · Agent 自主执行模式（SOP）

这是 oil-cover 的**第二种执行轨道**。和默认的脚本模式不同，本模式**不调用 `generate_oil_cover.py`、不需要外部 Gemini、不需要 ZenMux key**：由执行的 Agent 自己读完这份 SOP，端到端跑完整个流程——用自身多模态视觉直接看视频帧/截图来选帧和分析，用自身的图像生成工具（图生图）出图。

## 何时走这一轨

- 用户明确说「自主模式 / 你自己执行 / 别用脚本 / 让 Codex 跑 oil-cover」之类。
- 或当前环境没有脚本依赖（Python / ffmpeg / ZenMux key）但有可用的图像生成工具。

否则默认仍走脚本模式（见 `SKILL.md`）。

## 前提（不满足就别硬跑）

执行的 Agent 必须同时具备：

1. **多模态视觉**：能直接看视频抽出的帧 / 截图，做选帧和内容分析。
2. **支持传参考图的图像生成工具（图生图）**：能把选定的真实屏幕证据帧 + 产品 Logo 作为输入图喂进去，一次性整图生成。

**在 Codex 环境，这个工具就是系统 skill `.system/imagegen` 的内置 `image_gen` 工具**（无需 `OPENAI_API_KEY`，支持参考图）。本 SOP 第六步默认走它，CLI（`scripts/image_gen.py`）只是 fallback。

Claude Code 当前**没有**内置图像生成工具，第六步通常要在 Codex 等带 image gen 工具的环境里执行。如果执行环境只有纯文生图、不能传参考图，先告诉用户这会牺牲「真实屏幕证据 + 真实 Logo」的保真度，由用户决定是否继续，**不要**自己本地拼贴凑数。

## 视觉规范的来源

本 SOP **只规定「Agent 自己怎么跑这套流程」，不重复视觉标准**。所有视觉判断——选帧标准、内容归因、构图、背景层、字体标题、点缀、质检、提示词骨架——一律以 `references/cover-rules.md`（186 行）为准。开跑前必须先完整读一遍 `cover-rules.md`。

## 与脚本模式的对照

| 环节 | 脚本模式（默认） | Agent 自主模式（本文件） |
| --- | --- | --- |
| 选帧 | Gemini 看 1fps 小 clip 选帧 | Agent 自己抽帧、看图、按 cover-rules 选 |
| 分析 | Gemini 多模态 + cover-rules | Agent 自己分析 + cover-rules |
| 生图 | ZenMux `gpt-image-2`（images/edits） | Agent 自带 image gen 工具（图生图） |
| 质检返工 | 脚本自动质检重跑 | Agent 自查，按需带修正 prompt 重跑 |
| 中间产物 | 视频旁 `<视频名>.oil-cover/` | 系统统一目录 `~/.oil-cover/runs/<run-id>/` |
| 依赖 | Python + ffmpeg + ZenMux key | 仅 Agent 自身能力 |

## 产物目录约定

- **统一根目录**：`~/.oil-cover/runs/`，跨项目、不跟视频走。
- **每次任务一个 run 目录**：`~/.oil-cover/runs/<run-id>/`，其中 `<run-id>` = `<时间戳>-<视频名slug>`，时间戳用 `date +%Y%m%d-%H%M%S`，slug 取文件名去扩展名、空格和特殊字符转 `-`。
- run 目录内放：`frames/`（抽出的候选帧）、`analysis.md`、`cover_plan.md`、`cover_3x4.prompt.md`、`cover_4x3.prompt.md`、生成记录（用了哪些工具/参数/参考图）、以及最终两张图的副本。
- **最终交付的两张封面仍写到视频/截图旁边**：`<视频名>_3x4.png`、`<视频名>_4x3.png`，方便查找；run 目录里只是留一份副本备查。这是和脚本模式唯一刻意保持一致的地方——只把中间产物挪进了统一目录。

## 执行步骤

### 1. 建 run 目录

```bash
RUN_ID="$(date +%Y%m%d-%H%M%S)-<视频名slug>"
mkdir -p "$HOME/.oil-cover/runs/$RUN_ID/frames"
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

- `cover_plan.md`：两版封面的方案要点（标题断行、强调词、构图、点缀、Logo 位置）。
- 用 cover-rules 的提示词骨架，给 `3:4` 和 `4:3` **各写一份完整 prompt**，分别存为 `cover_3x4.prompt.md`、`cover_4x3.prompt.md`。
- **生图前必须先把 sidecar 写盘**，再调工具。

### 6. 生图（调 Agent 自带 image gen 工具，图生图）

**这是 generate（带参考图），不是 edit** —— oil-cover 要把真实截图提炼重组成干净封面，不保留原图原样，所以截图和 Logo 都作为**参考图**喂入，而非编辑目标。

在 Codex 环境，默认用 `.system/imagegen` 的**内置 `image_gen` 工具**：

- **先把本地图加载进对话上下文**：内置 `image_gen` 只吃 prompt 文本，**没有文件路径 / `images[]` 参数**，所以本地的屏幕证据帧和 Logo 必须先用 `view_image` 工具加载进上下文，模型才看得到；再在 prompt 里按序号引用：Image 1 = 屏幕证据帧，Image 2 = 产品 Logo（如有）。
- **参考图是「参考」不是「复刻」**：参考图影响生成方向，Logo 的形状和品牌色会被参考，但细节会被模型重绘，做不到像素级复现——这点和脚本模式一致；prompt 里仍要写「保留产品识别、不要重新发明 Logo」尽量逼近。
- **一次性整图生成**完整画面（真实屏幕证据 + 标题 + 产品标识 + 点缀 + 风格化），不分层、不本地后处理。
- 每个画幅一次独立调用（3:4 一次、4:3 一次），不要用 `n` 出变体来凑两版。
- 画幅：在 prompt 里写死 `exact 3:4 portrait` / `exact 4:3 horizontal`。内置工具尺寸控制有限，先让它尽量贴近目标比例。若用户要求**严格精确**像素（脚本用的 `960x1280` / `1280x960`，都是 16 的倍数、`gpt-image-2` 支持），而内置工具给不出，按 imagegen skill 的规则**先问用户**是否走 CLI fallback（`scripts/image_gen.py`，`gpt-image-2`，需 `OPENAI_API_KEY`）——不要为了普通的尺寸控制擅自切 CLI，更不要本地裁切凑比例。
- **落地与搬运**：内置工具默认把图存到 `$CODEX_HOME/generated_images/...`。封面是项目产物，**必须 copy 到视频/截图旁** `<视频名>_3x4.png`、`<视频名>_4x3.png`，并在 run 目录留副本；不能只留在 `generated_images`。**兜底**：若本次没有源素材路径（纯主题 / 冒烟测试，没有视频或截图文件可定位「旁边」），最终图只写入 run 目录即可。把用到的工具（内置 / CLI）、尺寸、参考图记进生成记录。
- 非 Codex 环境若没有等价工具，见上文「前提」，不要硬跑。

### 7. 自查质检（对齐 cover-rules「自动质检和返工」）

生成后逐项核对：标题可读、标题有内容相关装饰、产品 Logo 像参考图、屏幕物件有裁切感、主证据足够大、无人物/摄像头、无完整截图噪音、整体像一张完整生成图。任一核心项不达标 → 写一份只修失败项的修正 prompt，带**原参考图**重跑一次，保留已经成功的标题、构图、产品归因、主视觉和整体风格。

### 8. 收尾

确认产物齐全：视频旁两张图、run 目录里的 `analysis.md` / `cover_plan.md` / 两份 `.prompt.md` / 生成记录 / 图副本。

## 不可违反（继承 SKILL.md，本模式同样适用）

- 最终封面必须一次性生成完整画面；不要在生成后用本地工具贴字、贴 Logo、拼图、重排、裁切改版或视觉修补。
- 封面不保留人物、人脸、头像、摄像头气泡和真人画中画（所有层级，包括重建的 UI 卡片、画廊样本、嵌套截图）。
- 绝对不要把历史案例或上一次任务里的产品名、模型名、关键词、品牌色和点缀带入当前封面；所有外层文字和点缀只能来自当前视频、当前标题、当前字幕、当前截图或当前用户补充信息。
- 默认同时交付 `3:4` 和 `4:3` 两版；单独重跑时只生成指定画幅。
- 生图前必存 `.prompt.md` sidecar；生成后保留 `analysis.md`、`cover_plan.md`、两份 prompt、生成记录和最终图片。
- 本模式不用 ZenMux key；若执行环境用到任何 key，不得写进 prompt、sidecar、日志或最终回复。

## 输出说明

完成后说明：

- 两张最终封面路径（视频旁）。
- run 目录路径（含 `analysis.md` / `cover_plan.md` / 两份 `.prompt.md`）。
- 使用的参考帧、Logo 或素材。
- 是否需要单独重跑 `3:4` 或 `4:3` 某一版。
