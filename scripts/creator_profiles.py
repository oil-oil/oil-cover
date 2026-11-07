#!/usr/bin/env python3
"""Offline, per-platform creator profiles stored outside the installed skill."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid


SKILL_DIR = Path(__file__).resolve().parents[1]
ALIASES = {
    "小红书": "xiaohongshu", "xhs": "xiaohongshu",
    "公众号": "wechat", "微信公众号": "wechat", "weixin": "wechat",
    "抖音": "douyin", "b站": "bilibili", "哔哩哔哩": "bilibili",
    "通用": "default",
}


class ProfileError(ValueError):
    pass


def platform_id(value: str) -> str:
    value = value.strip().lower()
    value = ALIASES.get(value, value)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", value):
        raise ProfileError("平台使用小红书/公众号/抖音/B站，或 1–48 位英文、数字、下划线、连字符。")
    return value


def single_line(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise ProfileError(f"{label}必须是文字。")
    value = value.strip()
    if not value or len(value) > 100 or any(ord(c) < 32 for c in value):
        raise ProfileError(f"{label}必须为 1–100 字的单行文字。")
    return value


def private_write(path: Path, content: bytes) -> None:
    """Atomic replacement; no truncation of an existing profile on failure."""
    if path.is_symlink():
        raise ProfileError("不覆盖符号链接配置文件。")
    fd, temporary = tempfile.mkstemp(prefix=".profile-", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            temp_path.chmod(0o600)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


class ProfileStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or os.environ.get(
            "OIL_COVER_CREATOR_HOME", str(Path.home() / ".oil-cover" / "creators")
        )).expanduser().resolve()
        if self.root == SKILL_DIR or SKILL_DIR in self.root.parents:
            raise ProfileError("个人资料必须保存在 Skill 目录之外，避免被安装包或 Git 发布。")
        self.path = self.root / "profiles.json"

    def read(self) -> dict:
        if not self.path.exists():
            return {"schema_version": 1, "profiles": {}}
        if self.path.is_symlink():
            raise ProfileError("资料配置不能是符号链接。")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ProfileError("资料配置无法读取；保留原文件，请先修复。") from exc
        if (not isinstance(data, dict) or data.get("schema_version") != 1
                or not isinstance(data.get("profiles"), dict)
                or any(not isinstance(p, dict) for p in data["profiles"].values())):
            raise ProfileError("不支持的资料格式；保留原文件，不自动覆盖。")
        return data

    def avatar_path(self, relative: str) -> Path:
        if not isinstance(relative, str) or not relative:
            raise ProfileError("头像路径缺失。")
        path = (self.root / relative).resolve()
        avatar_root = self.root / "avatars"
        if (avatar_root.resolve() != avatar_root or avatar_root not in path.parents):
            raise ProfileError("头像必须位于本机资料目录的 avatars 子目录。")
        return path

    def show(self, platform: str) -> dict:
        key = platform_id(platform)
        profile = self.read()["profiles"].get(key)
        if not profile:
            raise ProfileError(f"尚未保存 {key} 的名称和头像。")
        name = single_line(profile.get("display_name", ""), "账号名称")
        signature = single_line(profile.get("signature", ""), "署名")
        avatar = self.avatar_path(profile.get("avatar", ""))
        if not avatar.is_file():
            raise ProfileError(f"{key} 的头像文件缺失；补充头像即可，名称仍已保存。")
        return {"platform": key, "display_name": name, "signature": signature,
                "avatar_path": str(avatar)}

    def list(self) -> list[dict]:
        result = []
        for key, value in self.read()["profiles"].items():
            try:
                self.show(key)
                ready = True
            except (ProfileError, AttributeError, TypeError):
                ready = False
            result.append({"platform": key, "display_name": value.get("display_name", ""),
                           "signature": value.get("signature", ""), "ready": ready})
        return result

    def save(self, platform: str, name: str | None = None,
             avatar: Path | None = None, signature: str | None = None) -> dict:
        key = platform_id(platform)
        data = self.read()
        profile = dict(data["profiles"].get(key, {}))
        display_name = single_line(name if name is not None else profile.get("display_name", ""), "账号名称")
        if signature is None:
            signature = (profile.get("signature") if name is None else None) or (
                display_name if display_name.startswith("@") else "@" + display_name)
        profile.update(display_name=display_name, signature=single_line(signature, "署名"))
        payload = None
        extension = ""
        if avatar is not None:
            source = Path(avatar).expanduser().resolve()
            if not source.is_file() or not 0 < source.stat().st_size <= 16 * 1024 * 1024:
                raise ProfileError("头像需为存在的本地图片，大小不超过 16 MB。")
            try:
                from PIL import Image
                with Image.open(source) as image:
                    extensions = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}
                    extension = extensions.get(image.format, "")
                    if not extension or image.width < 32 or image.height < 32:
                        raise ProfileError("头像使用至少 32×32 的 PNG、JPEG 或 WebP。")
                    image.verify()
                payload = source.read_bytes()
            except ImportError as exc:
                raise ProfileError("验证头像需要 Pillow：python -m pip install Pillow") from exc
            except (OSError, ValueError, SyntaxError) as exc:
                raise ProfileError("头像不是有效的 PNG、JPEG 或 WebP 图片。") from exc
        else:
            saved_avatar = self.avatar_path(profile.get("avatar", ""))
            if not saved_avatar.is_file():
                raise ProfileError("首次保存或头像丢失时需要 --avatar 本地图片路径。")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink():
            raise ProfileError("不覆盖符号链接配置文件。")
        if payload is not None:
            relative = f"avatars/{key}-{uuid.uuid4().hex}{extension}"
            target = self.avatar_path(relative)
            target.parent.mkdir(exist_ok=True, mode=0o700)
            private_write(target, payload)
            profile["avatar"] = relative
        data["profiles"][key] = profile
        private_write(self.path, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        return self.show(key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="列出已保存的平台，不联网")
    show = sub.add_parser("show", help="读取本次生成需要的账号名、署名、头像路径")
    show.add_argument("--platform", required=True)
    save = sub.add_parser("set", help="保存或更新一个平台；其他平台保持不变")
    save.add_argument("--platform", required=True)
    save.add_argument("--name")
    save.add_argument("--signature", help="可选自定义署名，省略则默认 @名称")
    save.add_argument("--avatar", type=Path)
    args = parser.parse_args()
    try:
        store = ProfileStore()
        if args.command == "list":
            result = store.list()
        elif args.command == "show":
            result = store.show(args.platform)
        else:
            result = store.save(args.platform, args.name, args.avatar, args.signature)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ProfileError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
