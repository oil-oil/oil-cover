import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/creator_profiles.py"
SPEC = importlib.util.spec_from_file_location("creator_profiles", SCRIPT)
PROFILES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILES)


class CreatorProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.store = PROFILES.ProfileStore(self.work / "private")
        self.avatar = self.work / "upload.png"
        Image.new("RGB", (64, 64), "blue").save(self.avatar)

    def test_first_use_is_read_only_and_has_no_author_defaults(self):
        self.assertEqual(self.store.list(), [])
        self.assertFalse(self.store.root.exists())
        with self.assertRaises(PROFILES.ProfileError):
            self.store.show("小红书")

    def test_avatar_survives_temporary_upload_removal(self):
        expected = self.avatar.read_bytes()
        self.store.save("小红书", "测试设计", self.avatar)
        self.avatar.unlink()
        result = self.store.show("xhs")
        self.assertEqual(result["signature"], "@测试设计")
        self.assertEqual(Path(result["avatar_path"]).read_bytes(), expected)
        self.assertNotIn(str(self.work / "upload.png"), self.store.path.read_text(encoding="utf-8"))

    def test_multiple_platforms_update_without_losing_other_data(self):
        self.store.save("小红书", "设计账号", self.avatar)
        wechat = self.store.save("公众号", "长文账号", self.avatar, "长文账号")
        data = self.store.read()
        data["extension"] = {"keep": True}
        self.store.path.write_text(json.dumps(data), encoding="utf-8")
        self.store.save("xiaohongshu", "新名称")
        self.assertEqual(self.store.show("wechat"), wechat)
        self.assertEqual(self.store.show("小红书")["signature"], "@新名称")
        self.assertEqual(self.store.read()["extension"], {"keep": True})

    def test_bad_avatar_does_not_overwrite_saved_profile(self):
        self.store.save("douyin", "视频账号", self.avatar)
        before = self.store.path.read_bytes()
        invalid = self.work / "fake.png"
        invalid.write_text("not an image", encoding="utf-8")
        with self.assertRaises(PROFILES.ProfileError):
            self.store.save("douyin", "错误更新", invalid)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_missing_avatar_preserves_name_until_replacement(self):
        saved = self.store.save("bilibili", "视频作者", self.avatar)
        Path(saved["avatar_path"]).unlink()
        self.assertFalse(self.store.list()[0]["ready"])
        with self.assertRaises(PROFILES.ProfileError):
            self.store.show("bilibili")
        self.assertEqual(self.store.save("bilibili", avatar=self.avatar)["display_name"], "视频作者")

    def test_corrupt_config_is_not_reset(self):
        self.store.root.mkdir()
        self.store.path.write_bytes(b"{invalid")
        with self.assertRaises(PROFILES.ProfileError):
            self.store.save("wechat", "新账号", self.avatar)
        self.assertEqual(self.store.path.read_bytes(), b"{invalid")

    def test_path_escape_and_skill_local_storage_are_rejected(self):
        with self.assertRaises(PROFILES.ProfileError):
            PROFILES.ProfileStore(ROOT / ".oil-cover" / "creators")
        with self.assertRaises(PROFILES.ProfileError):
            self.store.save("../escape", "名字", self.avatar)
        with self.assertRaises(PROFILES.ProfileError):
            self.store.avatar_path("../../secret.png")

    @unittest.skipIf(os.name == "nt", "Windows uses inherited user ACLs")
    def test_private_file_permissions(self):
        saved = self.store.save("wechat", "测试账号", self.avatar)
        for path in (self.store.path, Path(saved["avatar_path"])):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.store.root.stat().st_mode), 0o700)

    def test_cli_roundtrip_and_missing_platform_exit_code(self):
        env = dict(os.environ, OIL_COVER_CREATOR_HOME=str(self.store.root))
        def run(*args):
            return subprocess.run([sys.executable, str(SCRIPT), *args], env=env,
                                  capture_output=True, encoding="utf-8")
        self.assertEqual(run("show", "--platform", "wechat").returncode, 2)
        saved = run("set", "--platform", "公众号", "--name", "CLI 账号", "--avatar", str(self.avatar))
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertEqual(json.loads(run("show", "--platform", "wechat").stdout)["display_name"], "CLI 账号")
        self.assertTrue(json.loads(run("list").stdout)[0]["ready"])


if __name__ == "__main__":
    unittest.main()
