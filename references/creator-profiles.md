# 按平台保存作者名称与头像

这些资料属于使用者本机，不属于开源 Skill。默认目录是 `~/.oil-cover/creators/`；设置 `OIL_COVER_CREATOR_HOME` 可改位置，但不得放在 Skill 或准备发布的仓库内。

## 制作时如何询问

先完成风格选择。设计分享风格首次使用时，一次询问：

> 准备用于哪些平台？请分别提供每个平台的账号名称和头像。小红书、公众号、抖音等可以不同；也可以明确告诉我哪些平台共用一套。

已经保存的平台直接读取，只补缺失字段。用户已上传资料时不要再询问。账号名保留空格和大小写；不要把维护者、README 示例或历史任务的名称当成当前使用者。多个平台的图片归属不清时，只澄清映射，先继续视频分析。

## 本地入口

`SKILL_DIR` 为本次使用的 Skill 目录；下列 Python 命令在 Windows、macOS、Linux 均可用。导入头像需要 Pillow，可用 `python -m pip install Pillow` 安装。

```bash
python "<SKILL_DIR>/scripts/creator_profiles.py" list
python "<SKILL_DIR>/scripts/creator_profiles.py" set --platform xiaohongshu --name "你的账号名称" --avatar "<头像图片路径>"
python "<SKILL_DIR>/scripts/creator_profiles.py" set --platform wechat --name "你的公众号名称" --avatar "<公众号头像路径>" --signature "你的公众号名称"
python "<SKILL_DIR>/scripts/creator_profiles.py" set --platform douyin --name "你的抖音名称" --avatar "<抖音头像路径>"
python "<SKILL_DIR>/scripts/creator_profiles.py" show --platform xiaohongshu
```

支持中文别名：小红书 → `xiaohongshu`；公众号 → `wechat`；抖音 → `douyin`；B站 → `bilibili`；通用 → `default`。其他平台用英文、数字、下划线或连字符命名。`default` 不自动覆盖任何平台资料。

首次 `set` 需要名称和头像，后续可仅更换一项：

```bash
python "<SKILL_DIR>/scripts/creator_profiles.py" set --platform xiaohongshu --name "新的名称"
python "<SKILL_DIR>/scripts/creator_profiles.py" set --platform xiaohongshu --avatar "<新的头像路径>"
```

改名时默认署名同步为 `@新名称`；需要特殊署名就同时传 `--signature`。只改头像时保留原名称和署名。本工具只管理封面显示资料，不登录平台、不上传图片、不发布帖子。

## 保存与读取约定

- `profiles.json` 使用 `schema_version: 1` 和 `profiles` 平台映射，保存 `display_name`、`signature`、相对头像路径 `avatar`。
- 原图复制到 `avatars/`，验证 PNG/JPEG/WebP 后原样保存，不因聊天缓存被清理而丢失。新头像使用新文件名，不覆盖旧头像文件。
- 更新一个平台时保留其他平台和未知扩展字段；配置损坏或格式不支持时停止写入，不重置为空。
- `show` 返回本次名称、署名与已验证位于资料目录内的绝对头像路径；只有读取结果才是本次生成依据。头像缺失时保留名称，补传头像后恢复。
- `list` 返回平台、名称、署名和 `ready` 状态；读取空配置不会创建目录。退出码 0 为成功，2 表示缺少资料或校验失败。
- 写入采用临时文件与原子替换。POSIX 新建目录为 0700、文件为 0600；Windows 沿用当前用户目录 ACL，不声称提供跨用户加密。不要把 Key、密码或登录凭据存入此文件。
- 配置与头像不进入 Skill、Git 或示例目录。发布仓库中的头像仅属于经授权展示的成品案例，不能作为新用户默认头像。

## 多平台输出

用户可以逐个平台提供不同资料，也可以明确指定多平台共用资料。生成前读取每个平台的 `show` 结果，把对应名称和头像传给内置图像工具；不得只保存而仍用旧名称生成。

不同资料的文件名加入平台，例如 `<视频名>_xiaohongshu_3x4.png`、`<视频名>_wechat_4x3.png`。三种基础比例不等于所有平台的全部规格；有特定发布位置要求时再按要求生成额外尺寸。
