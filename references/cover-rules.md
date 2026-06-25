# oil-cover 视觉规范

这份文件是 `generate_oil_cover.py` 默认传给 Gemini 的完整封面设计规范。日常使用 Skill 时不需要手动读取；只有要修改视觉标准、排查提示词遗漏或评审脚本输出时，才打开本文件。

## 核心目标

- 为小红书 AI 工具实操视频生成稳定、清楚、干净、精致的视频封面。
- 默认方向是“真实视频证据 + Apple-like 产品视觉 + 清晰标题 + 无人物干净构图”。
- 封面必须突出真实屏幕内容、可读标题、主产品 Logo、内容相关点缀和轻微空间层次。
- 参考截图默认用于提炼证据，不用于整张复刻。最终画面要像“重新设计过的实操证据卡片”，只保留能解释主题的界面信号。
- 最终封面必须由 `openai/gpt-image-2` 一次性生成完整画面，本地工具不能贴字、贴 Logo、拼图、裁切改版或视觉修补。

## 视觉传达导演

- 生成封面前，必须先回答：这张封面 0.5 秒内要让读者看到什么结果。这个答案就是“一眼主语”。
- 一眼主语通常来自截图里最能证明结果的区域，例如生成结果、对比结果、关键卡片、选中状态、运行成功状态或视觉成品，而不是完整工作区。
- 一眼主语必须成为屏幕区域里的最大视觉证据。辅助 UI 只能解释它，不能和它平分画面。
- 如果主证据是多张封面、卡片、结果图、列表或对比项，必须把这些结果图放大成主视觉画廊；保留数量要服务手机端可读性，可以减少样本数量或用边缘裁切暗示还有更多。
- 如果主证据被文件列表、输入框、工作流区块、正文段落或完整窗口挤小，优先删除、裁切或弱化这些辅助信息。
- 不要为了“证据完整”牺牲手机端可见性。封面不是界面说明书，信息保真要服务点击理解。
- Gemini 的分析必须输出主视觉、辅助视觉和可牺牲信息；提示词必须写清主视觉占比和辅助信息上限。

## 硬规则

- 最终画面不保留人物。移除真人画中画、摄像头气泡、人脸、头像和人物形象。
- 人物限制适用于所有层级，包括重建的 UI 卡片、对比图、画廊样本、嵌套截图和小预览条里的真人照片或头像。除非用户明确要求人物，否则统一替换成抽象 UI、图表、产品卡、代码块或中性占位。
- 每张封面都要有可见的衬线字体层次，优先用于英文产品名、模型名、数字、小标签或关键词。
- 主标题必须是第一视觉锚点。除非用户要求低调标题，标题视觉面积要明显大于普通封面。
- 标题和屏幕必须落在清晰网格里，优先左对齐、居中对齐或轴线对齐，避免随机漂浮和边距混乱。
- 标题里的每个词使用什么字体、颜色、强调方式，必须在提示词里写成确定方案。
- 默认标题使用深石墨色或柔和黑。强调色必须说明强调哪个词、颜色来源和理由。
- 标题区域不能只有裸文字。默认必须给标题加 1-2 个内容相关装饰，例如关键词柔和高亮、细下划线、轻量括号、光标标记、窗口状态小标、工作流小标签或结果状态小字。
- 装饰文字必须来自当前标题、截图、字幕、主题或产品归因，长度要短，优先 2-5 个词，作用是帮读者更快理解当前工作流。
- 标题、英文产品名、Logo 和产品标识必须在提示词里写成确定值，避免随机品牌、无关 Logo、水印、hashtag 和感叹号。
- 背景配色必须来自选定关键帧、截图、Logo 或参考图，再做克制延展。
- 生图提示词必须包含这句背景层开头：`Mandatory visible background: full-canvas clean base, visible fine grid, restrained low-opacity local gradient glow sampled from the selected image, very light grain.`
- 参考截图不能原样铺进封面。必须先提炼 2-3 个关键证据，再重组为干净界面；删除侧栏历史列表、长段正文、无关路径、通知、状态栏、旧字幕和边缘杂讯。
- 不能生成额外展示框、白色底卡、手机框、设备壳、第二层容器或后期拼贴感。
- 禁止把历史案例、测试样例或上一次任务里的产品名、模型名、颜色名、关键词和点缀带入新任务。任何外层文字、品牌、点缀标签和强调词都必须来自当前视频、当前标题、当前字幕、当前截图或当前用户补充信息。

## 证据选择

- 有视频时先提取并判断首帧，但不要机械使用首帧。
- 首帧如果是实操界面、结果页或工具页面，可以作为屏幕证据。
- 首帧如果是标题页、片头页、纯文字页或已有封面页，只用于提炼主题、配色、字体气质和系列感，不作为最终屏幕主视觉。
- 首帧不可用时，结合字幕、口播和时间线选择 2-6 个候选关键帧，再选出最适合视觉传达的一帧。
- 优先选择界面清楚、动作明确、结果可见、构图能支撑标题的真实画面，例如产品界面、操作结果、对比页、工作流画面、关键弹窗、代码或终端输出。
- 选帧时要同时判断“可提炼性”：这一帧是否能抽出少量关键控件、关键词、结果状态或流程节点，是否能在去掉侧栏和正文噪音后仍然说明主题。
- 找不到合适实操画面时，说明缺口并请用户确认下一步。

## 内容归因

- 生成前必须判断主主题、主产品、承载界面和辅助品牌。
- 外层标题、Logo 和产品小标记只服务主主题和主产品。
- 截图里的承载工具、浏览器、编辑器、聊天框或发布环境默认只作为屏幕证据，不自动升级成联合品牌。
- 辅助品牌只有在内容明确讲它的工作流、集成、对比或教程时，才进入外层视觉。
- Claude Code、Codex、Cursor、OpenAI 等产品相关内容可以说明“实操 / 体验 / 工作流”，不要暗示官方合作。

## 构图规则

### 3:4 竖屏

- 必须是 exact 3:4 portrait cover，接近 1080x1440 的竖向构图；脚本 API 尺寸默认使用 `960x1280`。
- 标题更集中、更大，手机信息流里先看见标题再看见屏幕。
- 标题块建议放在上方 10%-38% 区域，屏幕块建议放在下方 38%-96% 区域。
- 屏幕默认放大到画面下半部，约占画面高度 55%-70%，可只露出 80%-95%。
- 标题和屏幕要通过轻微重叠、轴线、界面状态、选框或光标形成同一套画面秩序。
- 竖版可以加入克制点缀，点缀由当前内容决定，用来强调关键动作、界面状态或可见的工作流步骤。

### 4:3 横屏

- 必须是 exact 4:3 horizontal cover；脚本 API 尺寸默认使用 `1280x960`。
- 标题必须作为第一视觉锚点，不能变成左侧小标签。
- 标题和屏幕都要足够大，横版建议标题区约占画面宽度 40%-50%，屏幕证据约占画面宽度 45%-55%。
- 屏幕可以更完整，保留清楚的浏览器或工具界面证据。
- 横版可以加入克制点缀，点缀类型由当前内容决定，用来强化标题阅读、界面状态或屏幕关键区域。
- 点缀要来自主题逻辑，并且能让读者更快理解当前工作流。

## 屏幕物件

- 默认使用一个可见屏幕或浏览器物件，裁切边界来自画布边缘、安全区或隐形遮罩。
- 默认给屏幕一个轻微 3D 透视倾斜：subtle perspective tilt about 5-12 degrees，像从侧面略微看过去、一边离视线更近，制造视差立体感与景深；保留左上角浏览器/窗口边缘，保持 UI 文字清晰可读。
- 默认不要把完整屏幕物件居中完整放进画面。封面里的屏幕必须至少有一侧被画布边缘、安全区或隐形遮罩裁切，只露出 80%-95%，让画面有取景感和空间层次。
- 保留左上角浏览器或窗口边缘，右侧、底部或角落必须优先被画布裁掉；只有用户明确要求完整截图时，才完整显示屏幕物件。
- 透视幅度保持克制：只用轻微倾斜，避免极端斜切、鱼眼、扭曲和大角度旋转；正放 0 度和夸张透视都不是默认。
- 截图物件可以比安全区大 110%-160%，通过越界和裁切制造层次。
- 不要生成折角、卷页、厚设备边、黑色厚阴影、额外底卡或随机漂浮窗口。

## 截图提炼与去噪

- 生图阶段默认要整理截图，让封面更清楚。不要把参考截图当成完整背景、完整网页或完整 App 截图复刻。
- 每张封面只保留 2-3 个核心证据，例如产品名、当前 Agent 名称、运行状态、关键按钮、结果卡片、终端命令、选区、光标或一小段能说明流程的代码。
- 2-3 个核心证据必须有主次。第一个核心证据默认是主证据，必须占屏幕内容区 55%-75%；其他证据合计最多占 15%-30%。
- 当主证据是结果卡片、封面缩略图、图片画廊或对比样本时，不要把它们缩成完整工作区里的小图。必须放大为可读的主画廊，可以裁掉周边 UI。
- 在 3:4 竖版里，如果主证据是横向多卡片画廊，不要为了完整显示所有样本而把它们塞成小缩略图。必须根据手机端可读性选择保留数量；必要时裁切画廊边缘，或删除文件列表、工作流区块等辅助 UI。
- 允许重写界面布局，把真实截图里的核心证据提炼成干净的浏览器窗口、局部面板、流程卡片或结果摘要，但不能改掉主题和产品归因。
- 允许放大核心标题、终端、按钮、选区、光标、代码片段或关键卡片，让它们成为屏幕区域里最容易读到的信息。
- 必须删除或大幅淡化侧栏历史列表、完整聊天长文、无关文件路径、时间戳、系统状态栏、地址栏细节、底部字幕、人像气泡、通知、杂乱边缘和所有不能帮助理解主题的小字。
- 重建结果卡片、对比卡片或图库样本时，不要生成真人照片墙、头像列表或人物预览图；使用抽象界面、图表、封面卡、代码块或产品状态替代。
- 如果原截图信息很多，优先使用“局部放大 + 少量关键卡片 + 空白留白”的方式重组，不要追求完整还原。
- 必须保留真实实操感、产品识别和关键操作逻辑。
- 不要生成假 UI，不要乱改关键文字，不要把真实流程改成无关页面。

## 背景和阴影

- 背景顺序：纯净底色、细网格、局部低透明取色光感、极轻 grain。
- 网格要细、浅、均匀，在空白区域肉眼可见，不能被渐变冲掉。
- 当局部渐变或屏幕光感经过网格时，网格线可以出现极轻的取样色光泽，像柔和光线掠过纸面或磨砂玻璃。光泽只能增强层次，不能变成霓虹网格或复杂科技线条。
- 渐变必须从选定关键帧、截图、Logo 或参考图取色。
- 渐变默认放在边缘、角落或屏幕后方，覆盖约 15%-30% 画面。
- 不要大面积彩色雾、脏灰底色、复杂科技线条、坐标纹或过度发光。
- 屏幕阴影默认使用清爽浅阴影：主阴影接近 `0 18px 44px rgba(30,35,40,0.10)`，接触阴影接近 `0 4px 12px rgba(30,35,40,0.06)`。
- 避免厚重黑影、强烈投影、大面积脏灰阴影、霓虹发光和悬浮过高的夸张阴影。

## 字体和标题

- 中文主标题使用 Apple-like 现代黑体风格，接近苹方 / SF Pro CJK。
- 不使用宋体主标题、综艺花字、手写体、卡通字、书法字、廉价发光描边和立体金属字。
- 字体最多 2-3 种层次：主标题、衬线强调、小标签或英文注释。
- 衬线优先给语义关键词：产品名、工具名、模型名、关键概念、数字编号。
- 中英文混排要统一字重、基线、深色和行距。
- 主标题默认 4-10 个字，优先表达结果、动作或痛点。
- 可以加一句短副标题，明显小于主标题，只补一个动作、判断或边界，不写解释段落。当用户要求”只要标题””不需要副标题”时，外层只保留主标题。
- 标题装饰和副标题不是一回事。副标题可以解释内容，标题装饰负责让标题区域更有视觉层次，例如轻高亮、细标记、小标签、光标点或局部界面状态。
- 不使用夸张词，不使用感叹号，不加 hashtag，不堆 3 个以上小标签。
- 如果用户说”不需要描述文字””只要标题””不要小标签”，外层只允许出现主标题。

## 关键词和点缀

- 一张封面最多 1-2 个强调区域，优先给产品名、工具名、模型名或关键动作词。
- 强调方式优先选择柔和背景高亮、浅色贴片、雾面高亮、透明玻璃、细描边、局部反白或小面积低透明渐变。也可以使用取样色或产品色，但要降饱和并作为材质层使用。
- 关键词强调必须写清具体词、材质、颜色来源和强度。
- 大标题主体默认保持深色或柔和黑；不要把整行大字直接染成高饱和彩色。
- 柔和背景高亮应像一层低透明、轻圆角、贴在字后方的材质，不像按钮、胶囊标签、广告 CTA 或独立贴纸。
- 不要把关键词做成亮色按钮、大胶囊、独立贴纸、广告 CTA 或整词炫彩渐变。
- 装饰必须来自内容逻辑，优先使用当前截图或当前主题自然出现的界面状态、关键词、按钮、路径、URL 或光标状态。
- 点缀里的文字、品牌名、模型名和小标签只能来自当前内容归因。不要使用历史测试案例里的固定词。
- 坐标点、玻璃标签和悬浮说明框容易显乱，只有能直接解释画面时才加入。

## Logo 和参考素材

- 有产品 Logo 文件时，把 Logo 作为参考资产说明，并要求保留产品识别。
- 如果主产品能从标题、主题、字幕或截图里明确识别，并且 `product-assets.md` 有对应 Logo，默认必须把这个 Logo 作为参考图传给生图模型。
- 生图提示词必须要求使用参考 Logo 的真实形状和比例，不要让模型重新发明、简化、替换或用相似符号代替产品图标。
- 没有独立 Logo 文件时，使用选定关键帧里的产品名称、图标或界面标识作为品牌识别来源。
- Logo 可以做成小角标、微型贴纸、标题旁图标或屏幕附近标记，不要做成大型品牌广告。
- 用户提供的图片素材要归档后使用，并在 sidecar 记录原始来源和归档路径。
- 产品资产清单见 `product-assets.md`。

## 提示词要求

- 提示词要完整、明确、少重复。可以发挥，但必须覆盖画幅、标题、参考图、背景层、单一屏幕物件裁切、截图提炼与去噪、阴影、文字方案、点缀方案和少量禁止项。
- 背景层、屏幕裁切、截图提炼与去噪、阴影、文字方案、点缀方案都要单独写清。
- 提示词必须单独写清标题装饰：装饰放在哪里、强调哪个词、使用什么材质或小字、为什么和当前内容有关。
- 提示词必须明确写出“从参考截图提炼哪些信息”和“删除哪些干扰信息”。如果只写 preserve / crop / clean，力度不够。
- 最后放一行 `Avoid`，控制最容易出错的内容。
- 不限制固定行数。优先保留能影响成图稳定性的具体构图信息、标题字号关系、点缀关系和质检约束，避免堆叠空泛形容词。

## 自动质检和返工

- 脚本默认在生图后进行一次视觉质检，不需要人工介入。
- 质检重点包括：标题可读、标题有内容相关装饰、产品 Logo 像参考图、屏幕物件有裁切感、主证据足够大、无人物摄像头、无完整截图噪音、整体像一张完整生成图。
- 如果核心检查失败，脚本必须把失败项转成修正提示，并自动重跑一次。
- 自动返工只修失败项，必须保留已经成功的标题、构图、产品归因、主视觉和整体风格。

## 提示词骨架

```text
Use case: ads-marketing.
Asset type: Xiaohongshu <exact 3:4 portrait cover / exact 4:3 horizontal cover>.
Input images: Image 1 is the selected real screen evidence frame. Image 2 is the product logo if provided.
Primary request: Create one complete Apple-like AI tool tutorial cover. Preserve real product identity and tutorial evidence. Remove person, webcam bubble, old subtitles, and unrelated clutter.
Content attribution: main topic is "<主主题>"; main product is "<主产品>"; host interface is "<承载界面或无>"; supporting brands are "<辅助品牌或无>".
Title text: "<主标题>" with exact line breaks "<换行方案>"; optional short subtitle "<可选副标题>" clearly smaller than the main title; small product mark "<主产品名或 Logo>".
Composition: <标题位置、屏幕位置、互动状态、Logo 位置、点缀类型> with strict editorial alignment and readable phone-feed hierarchy.
Mandatory visible background: full-canvas clean <浅色或深色> base, visible fine grid, restrained low-opacity local gradient glow sampled from <具体颜色来源>, and very light grain; place the gradient at <位置>, covering about <15%-30%> of the canvas.
Screen crop plan: one visible screen/browser object only; show about <比例>; offset <方向>; clip <边/角> by canvas edge, safe area, or invisible mask; keep only the screen object's own edge or browser chrome.
Screenshot distillation plan: treat the selected screenshot as evidence source, not a full screenshot to copy; extract only <2-3 个关键证据>; remove <侧栏/长文/字幕/头像/无关小字/路径/通知/状态栏>; rebuild the screen area as a simplified real-feeling UI with generous whitespace and a clear focal hierarchy.
Visual communication plan: one-glance subject is <0.5 秒内要读者看到的结果>; primary evidence is <最能证明结果的区域>; make it occupy <55%-75%> of the screen content area; supporting evidence is <辅助 UI> and must stay below <15%-30%>; sacrifice <可以删掉/裁掉/弱化的信息> if it makes the primary evidence smaller.
Screen refinement plan: refine and recompose the screen content by <强化重点>; clean <字幕/人像/杂边/冗余文字>; preserve <产品名/命令/关键 UI 状态>.
Shadow plan: screen object only, clean light graphite shadow close to `0 18px 44px rgba(30,35,40,0.10)` plus soft contact shadow close to `0 4px 12px rgba(30,35,40,0.06)`.
Text style: Chinese main title uses fixed Apple-like PingFang SC / SF Pro CJK; visible restrained serif accent on "<具体词>"; colors: <每段文字颜色>; no random colored words.
Title decoration: add <1-2 个内容相关标题装饰>, such as a subtle highlight behind "<关键词>", a tiny "<当前内容小标签>", a cursor mark, bracket, or UI state chip; it must be aligned to the title grid and help readers understand this exact workflow.
Decoration: <1-2 个内容相关点缀>, subtle, aligned, useful for reading the current topic.
Avoid: full screenshot copy, unfiltered raw screenshot, sidebar history list, long chat transcript, dense tiny text, extra showcase frame, white backing card, phone frame, device shell, second container, fake UI, person/avatar/face, watermark, hashtags, unrelated logo, low-resolution artifacts, large misty gradient, neon cyberpunk, heavy black shadow.
```
