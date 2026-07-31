# oil-cover

为小红书「AI 工具实操」内容生成稳定、清楚、干净、精致的视频封面的 Claude / Codex Skill。

方向是 **真实屏幕证据 + Apple-like 产品视觉 + 清晰标题 + 无人物干净构图**，一次性整图生成，不靠本地贴字拼图。

> 作者：oil 欧呦（[@oil-oil](https://github.com/oil-oil)）

## 封面示例

<p align="center">
  <img src="docs/showcase/gallery.png" width="860">
</p>
<p align="center">
  <img src="docs/showcase/gallery-4x3.png" width="640">
</p>

## 特点

- **视频选帧**：把整段视频压成小 clip 交给多模态模型看完全片、按内容挑出最适合做封面的一帧（带理由），比盲采等距帧准得多。
- **完整视觉规范**：`references/cover-rules.md` 覆盖构图、背景层、字体标题、点缀、自动质检和提示词骨架。
- **默认三画幅**：并行出小红书 `3:4` 竖版、B 站首页主封面 `4:3` 横版和个人空间伴随版 `16:9` 横版。
- **产品 Logo 自动匹配**：内置 Claude / Codex / Cursor / Gemini / GitHub 等常用 AI 产品 Logo。

## 两种执行模式

| | 脚本模式（默认） | Agent 自主执行 |
| --- | --- | --- |
| 怎么跑 | 跑 `scripts/generate_oil_cover.py` | 执行的 Agent 自己读 SOP 端到端完成 |
| 选帧 / 分析 | ZenMux 上的 Gemini | Agent 自身多模态视觉 |
| 生图 | ZenMux `gpt-image-2` | Agent 自带图像生成工具（图生图） |
| 依赖 | Python + ffmpeg + ZenMux key | 仅需带生图工具的 Agent（如 Codex 内置 `image_gen`） |
| 适合 | 高保真、可复现 | 零外部依赖、零 key |

模式偏好记在 `~/.oil-cover/config.json`，设一次以后不再问。自主模式完整流程见 [`references/agent-native-flow.md`](references/agent-native-flow.md)。

## 安装

把本仓库克隆到 Claude Code 或 Codex 的 skills 目录：

```bash
# Claude Code
git clone https://github.com/oil-oil/oil-cover.git ~/.claude/skills/oil-cover

# 或 Codex
git clone https://github.com/oil-oil/oil-cover.git ~/.codex/skills/oil-cover
```

脚本按 `OIL_COVER_SKILL_DIR` → `~/.claude/skills/oil-cover` → `~/.codex/skills/oil-cover` 的顺序自动定位规则文件和 Logo 资产，装到上面任一位置即开箱可用，无需配置环境变量。

## 用法（脚本模式）

```bash
python3 ~/.claude/skills/oil-cover/scripts/generate_oil_cover.py \
  --video "<视频路径>" \
  --title "<标题或主题>" \
  --topic "<补充背景>"
```

截图 / 关键帧输入：

```bash
python3 ~/.claude/skills/oil-cover/scripts/generate_oil_cover.py \
  --image "<截图路径>" \
  --logo "<可选 Logo 路径>" \
  --title "<标题>"
```

默认并行出 `3:4` + `4:3` + `16:9`。完整参数（取帧策略、`--dry-run`、`--skip-generate` 等）见 [`SKILL.md`](SKILL.md)。

### 配置 ZenMux key（仅脚本模式需要）

脚本调用 ZenMux（Gemini 分析 + `gpt-image-2` 生图），需要 API key。按优先级读取：

1. `--api-key` 参数
2. `ZENMUX_API_KEY` 环境变量
3. skill 目录根的 `.zenmux_api_key` 文件（已被 `.gitignore` 忽略，**切勿提交**）

### 依赖

- Python 3.9+
- `ffmpeg`（视频抽帧）
- 一个 ZenMux 账号与 API key

## 用法（Agent 自主执行）

在带图像生成工具的 Agent（如 Codex）里触发，Agent 会读 [`references/agent-native-flow.md`](references/agent-native-flow.md) 自己完成选帧、分析、出图，**不需要 ZenMux key**。生图那一步在 Codex 里用其系统级 `imagegen` 的内置 `image_gen` 工具（图生图）。

## 目录结构

```
SKILL.md                        技能主说明（两种模式 + 参数）
scripts/generate_oil_cover.py   脚本模式实现
references/
  cover-rules.md                完整视觉规范
  agent-native-flow.md          Agent 自主执行 SOP
  impact-tech-cover-style.md    可选的冲击型科技封面风格
  product-assets.md             产品 Logo 资产清单
assets/product-logos/           内置 AI 产品 Logo
```

## 商标与第三方资产

`assets/product-logos/` 内的产品 Logo 为各自公司商标，仅作封面参考资产，**不在本项目 MIT 许可范围内**，收录于此不代表任何合作或背书。来源与归属见 [NOTICE](NOTICE)。

## License

[MIT](LICENSE) © 2026 oil 欧呦
