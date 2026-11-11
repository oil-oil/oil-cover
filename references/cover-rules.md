# oil-cover 视觉规范

这份文件是 `generate_oil_cover.py` 默认传给 Gemini 的完整封面设计规范。日常使用 Skill 时不需要手动读取；只有要修改视觉标准、排查提示词遗漏或评审脚本输出时，才打开本文件。

## 核心目标

- 为配置的创作者生成稳定、清楚、干净、精致的小红书和 B 站 AI 工具实操视频封面。
- 默认方向是“真实视频证据 + Apple-like 产品视觉 + 清晰标题”。生图底图保持无人物；用户配置启用头像时，最终头像由代码确定性合成。
- 封面必须突出真实屏幕内容、可读标题、主产品 Logo、内容相关点缀和轻微空间层次。
- 参考截图默认用于提炼证据，不用于整张复刻。最终画面要像“重新设计过的实操证据卡片”，只保留能解释主题的界面信号。
- 生图模型必须一次性生成完整无人物底图。配置启用头像时，本地工具只允许执行该头像的 alpha 合成；不能本地贴字、贴 Logo、拼其他图片、裁切改版或视觉修补。

## 视觉传达导演

- 生成封面前，必须先回答：这张封面 0.5 秒内要让读者看到什么结果。这个答案就是“一眼主语”。
- 一眼主语通常来自截图里最能证明结果的区域，例如生成结果、对比结果、关键卡片、选中状态、运行成功状态或视觉成品，而不是完整工作区。
- 一眼主语必须成为屏幕区域里的最大视觉证据。辅助 UI 只能解释它，不能和它平分画面。
- 如果主证据是多张封面、卡片、结果图、列表或对比项，必须把这些结果图放大成主视觉画廊；保留数量要服务手机端可读性，可以减少样本数量或用边缘裁切暗示还有更多。
- 如果主证据被文件列表、输入框、工作流区块、正文段落或完整窗口挤小，优先删除、裁切或弱化这些辅助信息。
- 不要为了“证据完整”牺牲手机端可见性。封面不是界面说明书，信息保真要服务点击理解。
- Gemini 的分析必须输出主视觉、辅助视觉和可牺牲信息；提示词必须写清主视觉占比和辅助信息上限。

## 硬规则

- 源截图、重建 UI 和生图底图不保留人物。移除真人画中画、摄像头气泡、人脸、头像和人物形象；限制适用于 UI 卡片、对比图、画廊样本、嵌套截图和小预览条。
- 配置启用头像时，最终封面只允许出现配置的一张透明头像，由代码在生图后合成；未启用时最终封面保持无人物。
- 创作者头像是否启用及素材路径来自用户配置；公开 Skill 默认关闭。启用时的默认布局为：3:4 宽 55%、顶部 58%、向右越界 6%；4:3 宽 38%、顶部 40%、向右越界 3%；16:9 宽 32%、顶部 40%、右侧内收 2%。
- 每张封面都要有可见的衬线字体层次，优先用于英文产品名、模型名、数字、小标签或关键词。
- 主标题必须是第一视觉锚点。除非用户要求低调标题，标题视觉面积要明显大于普通封面。
- 长标题通过两至三行断行保持大字，不挤成横贯画面的一行小字。品牌标识、副标题和装饰先让位，不能靠缩小主标题容纳附加信息。验收时检查完整头像合成图及缩略图，确认主标题仍能一眼读出。
- 标题和屏幕必须落在清晰网格里，优先左对齐、居中对齐或轴线对齐，避免随机漂浮和边距混乱。
- 标题里的每个词使用什么字体、颜色、强调方式，必须在提示词里写成确定方案。
- 默认标题使用深石墨色或柔和黑。强调色必须说明强调哪个词、颜色来源和理由。
- 标题区域不能只有裸文字。默认必须给标题加 1-2 个内容相关装饰，例如关键词柔和高亮、细下划线、轻量括号、光标标记、窗口状态小标、工作流小标签或结果状态小字。
- 装饰文字必须来自当前标题、截图、字幕、主题或产品归因，长度要短，优先 2-5 个词，作用是帮读者更快理解当前工作流。
- 标题、英文产品名、Logo 和产品标识必须在提示词里写成确定值，避免随机品牌、无关 Logo、水印和自行添加的 hashtag、感叹号；用户指定的标题保持原文。
- 背景配色从选定关键帧、截图、Logo 或参考图取色相，再统一调成粉调/灰调/奶油调的柔和氛围；禁止把 UI 里的荧光、酸性高饱和功能色原样放大。完整档位见「封面色彩体系」。
- 背景要有可感知的柔和色彩氛围，不能素成接近纯灰白；氛围允许 1-3 个邻近色相柔和融合，禁止全光谱彩虹和高饱和霓虹。
- 生图提示词必须包含这句背景层开头：`Mandatory visible background: full-canvas clean base, visible fine grid, a soft pastel color atmosphere of 1-3 neighbouring hues (sampled from the selected image or logo, softened to a creamy/dusty pastel) glowing gently from the edges or corners, very light grain; the atmosphere must be clearly visible yet soft — no neon or acid hues, no full-spectrum rainbow, no plain colorless canvas.`
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
- 产品介绍、原理讲解和展示幻灯片不能自动标成“实操”“实测”或亲自体验；没有真实操作证据时使用介绍措辞或不加副标题。
- 外层标题、Logo 和产品小标记只服务主主题和主产品。
- 用户要求突出品牌时，使用清楚的官方 Logo 与公司名组合；除非用户明确要求改标题，不把品牌名追加为新标题、不重复放大同一名称，也不能因此挤小原主标题。品牌与主标题在头像合成后都须完整可见。用户指定的新配色优先于参考截图配色。
- 截图里的承载工具、浏览器、编辑器、聊天框或发布环境默认只作为屏幕证据，不自动升级成联合品牌。
- 辅助品牌只有在内容明确讲它的工作流、集成、对比或教程时，才进入外层视觉。
- Claude Code、Codex、Cursor、OpenAI 等产品相关内容可以说明“实操 / 体验 / 工作流”，不要暗示官方合作。

## 构图规则

### 3:4 竖屏

- 必须是 exact 3:4 portrait cover，接近 1080x1440 的竖向构图；脚本 API 尺寸默认使用 `960x1280`。
- 标题更集中、更大，手机信息流里先看见标题再看见屏幕。
- 主标题每行横向铺满安全区宽度的约 90%-96%，每行字高约占画面高度 11%-15%；严格断成两行超大粗黑体（每行 3-5 个字），绝不要一行小字。
- 标题块建议放在上方 10%-42% 区域，屏幕块建议放在下方 42%-96% 区域。
- 屏幕默认放大到画面下半部，约占画面高度 55%-70%，可只露出 80%-95%。
- 标题和屏幕要通过轻微重叠、轴线、界面状态、选框或光标形成同一套画面秩序。
- 竖版可以加入克制点缀，点缀由当前内容决定，用来强调关键动作、界面状态或可见的工作流步骤。

### 4:3 横屏

- 必须是 exact 4:3 horizontal cover；脚本 API 尺寸默认使用 `1280x960`。
- 这是 B 站首页推荐主封面，也是 `video-publisher` 默认上传给 B 站的源文件；B 站当前建议尺寸至少 `1200x900`。
- 标题必须作为第一视觉锚点，不能变成左侧小标签。
- 标题和屏幕都要足够大，横版建议标题区约占画面宽度 45%-55%，屏幕证据约占画面宽度 45%-55%，两者可轻微重叠。
- 横版主标题每行字高约占画面高度 16%-22%，标题块整体（含副标题和装饰）约占画面高度 48%-62%；严格断为 2 行，每行 3-5 个字（严禁单行超过 5 个汉字导致字号缩小）。
- 屏幕可以更完整，保留清楚的浏览器或工具界面证据。
- 横版可以加入克制点缀，点缀类型由当前内容决定，用来强化标题阅读、界面状态或屏幕关键区域。
- 点缀要来自主题逻辑，并且能让读者更快理解当前工作流。

### 16:9 B 站个人空间伴随版

- 必须是 exact 16:9 horizontal cover；脚本 API 尺寸默认使用 `1280x720`。
- 这是 B 站个人空间伴随版，不作为默认上传源；B 站发布默认上传独立生成的 4:3 首页主封面。
- 标题必须作为第一视觉锚点，屏幕证据保持大且可读；利用额外横向空间延展背景和次要画面。
- 标题区建议约占画面宽度 38%-48%，屏幕证据约占画面宽度 52%-62%，两者可轻微重叠。
- 主标题每行字高约占画面高度 16%-22%，严格断为 2 行、每行 3-5 个字，让两行超大字撑满左侧视觉重心。
- 构图要兼顾 B 站信息流缩略图：标题、产品 Logo 和关键结果远离边缘，主证据在缩小后仍能被识别。

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
- 命令、参数、API 名称和执行结果必须逐字来自当前证据；截图中没有或看不清时省略，不凭工具名称补出看似合理的命令。

## 封面色彩体系

- 封面的外层设计色分三层：底与氛围、强调色、文字灰阶。三层必须合成一套有意图的配色方案，不是各自随机取色。
- **底色优先用干净清爽的纯白、冷白或极浅云灰白（`#F8FAFC`、`#FFFFFF`）**，画面要干净透亮；**禁止默认使用米白、奶油黄、暖黄或旧纸色（no cream, no warm ivory, no yellowish tint）**，避免每次背景看起来黄黄的。
- 背景必须有可感知的柔和色彩氛围，不能素到接近纯灰白。氛围层允许 1-3 个同家族或邻近清爽色相柔和融合（例如冰川蓝+淡雾紫 `#EBF3FF`+`#EEF2FF`、薄荷青+浅天蓝、淡樱粉+浅雾紫），像干净白纸边缘晕染的柔光，放在边缘、角落或屏幕后方，覆盖约 20%-40% 画面。
- 氛围层色调统一走「高明度清爽粉调（Crisp Clean Pastel）」：明快、干净、柔和不刺眼，不加暖黄滤镜。
- 强调色用于标题下方的干净手绘感下划线、局部单个词的文字变色或极轻装饰：与画面主色调和谐呼应（如深邃钴蓝 `#2563EB`、翡翠绿 `#10B981`、靛紫 `#4F46E5`）；**严禁默认使用实心彩色大胶囊把标题包起来，也严禁使用土味亮橙/促销红胶囊框**。
- 荧光绿、酸性黄绿等刺眼荧光色，禁止用于大面积背景；背景保持清爽白底配干净 pastel 柔光。
- 禁止全光谱彩虹（红橙黄绿蓝紫俱全）、高饱和霓虹渐变、喷雾状光斑团和泛黄脏灰浊色。
- 调色约束只管外层设计色：背景、标题装饰、点缀、小标签。屏幕证据内部的 UI 原色不受限制，真实截图该什么色就什么色。
- 颜色的气质基准：像 Apple 官网的清爽浅色编辑感，干净透亮，不泛黄、不土气。

## 背景和阴影

- 背景顺序：纯净清爽白底（`#F8FAFC` / `#FFFFFF`）、细网格、清爽 pastel 氛围层、极轻 grain。
- 网格要细、浅、均匀，在空白区域肉眼可见，不能被渐变冲掉。
- 当局部渐变或屏幕光感经过网格时，网格线可以出现极轻的取样色光泽，像柔和光线掠过白纸或磨砂玻璃。光泽只能增强层次，不能变成霓虹网格或复杂科技线条。
- 氛围层从选定关键帧、截图、Logo 或参考图取色相，并按「封面色彩体系」调成清爽干净的 pastel 柔光（不混入暖黄/米黄）。
- 氛围层默认放在边缘、角落或屏幕后方，覆盖约 20%-40% 画面。
- 不要泛黄米白底、荧光酸性色、脏灰底色、复杂科技线条、坐标纹或过度发光。
- 屏幕阴影默认使用清爽浅阴影：主阴影接近 `0 18px 44px rgba(30,35,40,0.10)`，接触阴影接近 `0 4px 12px rgba(30,35,40,0.06)`。
- 避免厚重黑影、强烈投影、大面积脏灰阴影、霓虹发光和悬浮过高的夸张阴影。

## 字体和标题

- 中文主标题所有行必须 100% 统一使用**粗壮有力的 Apple-like 现代无衬线粗黑体（接近苹方 PingFang SC Heavy / Bold / SF Pro Display Bold）**，字重饱满厚实，上下行字形风格完全一致。
- 严禁中文主标题出现宋体、明体、楷体、细体、书法笔锋、综艺花字、手写体、卡通字、廉价发光描边或立体金属字；严禁第一行与第二行中文字体不一致。
- 字体最多 2-3 种层次：中文超大粗黑体主标题、英文/数字衬线强调、小标签或副标题注释。
- 衬线体（Serif / Serif Italic）仅限用于英文产品名、工具名、模型名、英文关键词（如 `Agent`、`Skill`、`Claude`）或数字编号，绝不用于汉字。
- 中英文混排要统一字重、基线、深色和行距。
- **字数精炼以保证超大字号**：Agent 自拟主标题时默认 **`2 行 × 3-5 字`（最佳 `4+4` 字，总长 6-10 字，如 `"AI 写前端 / 风格统一"`）**，优先表达核心动作、对象或结果；长英文品牌名或 Skill 名拆为上方独立品牌小标，不塞进主标题行内挤小字号。用户指定标题或要求使用文件名时保留完整文字、型号和标点，通过断行适配画幅，不套用此长度建议。
- 定稿主标题只保留一套断行指令。逐行连接后必须与定稿原文一致，不因关键词高亮、chip 或小标签重复标题词；强调词跨行时只在原有字形上分段加样式，不另写一份。
- 可以加一句短副标题，明显小于主标题，只补一个动作、判断或边界，不写解释段落。当用户要求”只要标题””不需要副标题”时，外层只保留主标题。
- 标题装饰和副标题不是一回事。副标题可以解释内容，标题装饰负责让标题区域更有视觉层次，例如细笔触下划线、小标签、光标点或局部界面状态。
- Agent 自拟文字不使用夸张词、感叹号或 hashtag，不堆 3 个以上小标签；用户已经指定的标题原文优先。
- 如果用户说”不需要描述文字””只要标题””不要小标签”，外层只允许出现主标题。

## 关键词和点缀

- 一张封面最多 1-2 个强调区域，优先给产品名、工具名、模型名或关键结果词。
- **主标题无胶囊超大字排版（严禁套胶囊框与爆炸线）**：
  - 主标题两行超大粗黑体默认保持**纯正深石墨黑（`#1E2328`）**，或第一行深石墨黑（`#1E2328`）、第二行核心词直接采用**高可读性的深邃品牌色粗黑体文字**（如深钴蓝 `#1D4ED8` / 深翠绿 `#047857`，文字直接着深色，**外部绝不套任何胶囊框或色块底板**）。
  - **严禁给主标题套任何胶囊框、圆角贴片、色块底条或按钮背景（NO pill capsule, NO highlight box/chip behind title text）**，让超大号粗黑体文字直接落在干净清爽的白底上，并在第二行下方配一条干净利落的同色系笔触下划线（clean brush underline）即可，画面大气干净、重点一目了然。
  - 严禁在标题旁画放射短线/爆炸线（NO impact ticks / burst lines）。
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

- 脚本生成完成不代表视觉验收通过。执行 Agent 逐张检查最终图，并将结论写入生成记录；没有实际检查时不宣称通过。
- 必须修复的错误：标题、产品归因、Logo、型号或数字错误，主标题不可读，缺少要求的画幅，底图出现人物，配置启用的头像缺失。价格、跑分等数据只保留当前材料能够核对的项；不能可靠重绘时换用不含数据表的真实证据帧。
- 配色、装饰、网格、透视和留白按本文指导生成；只要没有违反用户明确要求或损害底图可读性，不因“还可以更好看”自动重做整套。用户要求审美调整时，以其反馈为准。
- 每个失败画幅默认最多自动返工一次，只修已经定位的错误，保留成功的标题、产品归因和主视觉。再次失败时交付已有可用画幅和明确缺口，不重复相同请求或宣称完成；用户明确要求继续时再生成。
- 用户明确选择某一已有版本后，以该版为准。保留对应图片和提示词，停止未选版本的生成，不再以通用风格偏好替换用户选择。

## 提示词骨架

```text
Use case: ads-marketing.
Asset type: <Xiaohongshu exact 3:4 portrait cover / exact 4:3 horizontal primary cover for Xiaohongshu and Bilibili homepage recommendations / Bilibili exact 16:9 personal-space companion cover>.
Input images: Image 1 is the selected real screen evidence frame. Image 2 is the product logo if provided.
Primary request: Create one complete person-free Apple-like AI tool tutorial base cover. Preserve real product identity and tutorial evidence. Remove person, webcam bubble, old subtitles, and unrelated clutter. <If creator portrait is enabled, deterministic local code adds it after generation; otherwise keep the final cover person-free.>
Content attribution: main topic is "<主主题>"; main product is "<主产品>"; host interface is "<承载界面或无>"; supporting brands are "<辅助品牌或无>".
Title text: "<主标题>" with exact line breaks "<换行方案>"; optional short subtitle "<可选副标题>" clearly smaller than the main title; small product mark "<主产品名或 Logo>".
Composition: <标题位置、屏幕位置、互动状态、Logo 位置、点缀类型> with strict editorial alignment and readable phone-feed hierarchy.
Local portrait composite guard: keep the generated base entirely person-free; do not draw a portrait, silhouette, placeholder, empty card, webcam bubble, avatar, mascot, or character.
Mandatory visible background: full-canvas clean crisp white/cool off-white (#F8FAFC) base, visible fine grid, a soft clean pastel color atmosphere of <1-3 个清爽邻近色相, 如 ice blue + soft periwinkle / mint + sky blue> (hues from <具体颜色来源>, softened to a clean crisp pastel without any yellowish or cream tint) glowing gently from <位置>, and very light grain; the atmosphere covers about <20%-40%> of the canvas and must be clearly visible yet soft.
Colour system: clean crisp white (#F8FAFC) base (strictly no yellowish cream or ivory tint) with a pastel atmosphere of <清爽邻近色相组>, plus massive bare heavy sans-serif title typography in deep graphite (#1E2328) with one clean brush underline in <主色强调色> under line 2 — never enclose any title text in a pill capsule or colored box.
Screen crop plan: one visible screen/browser object only; show about <比例>; offset <方向>; clip <边/角> by canvas edge, safe area, or invisible mask; keep only the screen object's own edge or browser chrome.
Screenshot distillation plan: treat the selected screenshot as evidence source, not a full screenshot to copy; extract only <2-3 个关键证据>; remove <侧栏/长文/字幕/头像/无关小字/路径/通知/状态栏>; rebuild the screen area as a simplified real-feeling UI with generous whitespace and a clear focal hierarchy.
Visual communication plan: one-glance subject is <0.5 秒内要读者看到的结果>; primary evidence is <最能证明结果的区域>; make it occupy <55%-75%> of the screen content area; supporting evidence is <辅助 UI> and must stay below <15%-30%>; sacrifice <可以删掉/裁掉/弱化的信息> if it makes the primary evidence smaller.
Screen refinement plan: refine and recompose the screen content by <强化重点>; clean <字幕/人像/杂边/冗余文字>; preserve <产品名/命令/关键 UI 状态>.
Shadow plan: screen object only, clean light graphite shadow close to `0 18px 44px rgba(30,35,40,0.10)` plus soft contact shadow close to `0 4px 12px rgba(30,35,40,0.06)`.
Text style: All Chinese characters in the main title MUST use the exact same massive, heavy modern geometric sans-serif font (Apple PingFang SC Heavy / Bold / SF Pro Display Bold) in deep graphite (#1E2328) across all lines (cap height 16%-22% in landscape, 11%-15% in portrait) — strictly no Songti/Mingti/Kaiti on Chinese characters; restrained serif accent is allowed ONLY on English words/product names "<具体英文词>".
Title decoration: keep the 2 massive title lines completely bare without any pill capsule or background box; add one clean brush underline under line 2, plus a small product mark above the title aligned to the title grid.
Decoration: <1-2 个内容相关点缀>, subtle, aligned, useful for reading the current topic.
Avoid: pill capsule or colored background chip/box around any title text, yellowish cream or warm ivory background tint, comic impact ticks or burst lines, Songti or serif Chinese headline fonts, small headline text, mismatched fonts between title lines, giant faded logo watermark in background, full screenshot copy, unfiltered raw screenshot, sidebar history list, long chat transcript, dense tiny text, extra showcase frame, white backing card, phone frame, device shell, second container, fake UI, person/avatar/face, watermark, hashtags, unrelated logo, low-resolution artifacts, acid or neon hues, fluorescent color blocks, full-spectrum rainbow gradient, plain colorless background, neon cyberpunk, heavy black shadow.
```
