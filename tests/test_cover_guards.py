import copy
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("oil_cover", ROOT / "scripts/generate_oil_cover.py")
COVER = importlib.util.module_from_spec(SPEC)
with tempfile.TemporaryDirectory() as directory:
    config = Path(directory) / "config.json"
    config.write_text("{}", encoding="utf-8")
    with patch.dict(os.environ, {"OIL_COVER_CONFIG": str(config), "OIL_COVER_SKILL_DIR": str(ROOT)}):
        SPEC.loader.exec_module(COVER)


class CoverGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)

    def run_pipeline(self, title="未知产品体验", topic="", subtitle="Codex 实操", extra=(), prompt=None):
        transcript = self.work / "transcript.txt"
        transcript.write_text(subtitle, encoding="utf-8")
        argv = [
            "generate_oil_cover.py", "--image", str(ROOT / "assets/product-logos/codex-openai.png"),
            "--title", title, "--topic", topic, "--subtitle", str(transcript),
            "--output-root", str(self.work), "--dry-run", "--no-default-creator-portrait",
            "--api-key-file", str(self.work / "missing-key"), *extra,
        ]
        model_result = {
            "selected_frame": {"label": "input_01"},
            "title": {"main": "错误旧标题", "line_breaks": ["错误", "旧标题"]},
            "logo_plan": {"outside_logo_or_mark": "错误品牌"},
            "prompts": {
                aspect: {"prompt": prompt if prompt is not None else
                         'Title text: "错误旧标题" with exact line breaks "错误\\n旧标题"; optional subtitle "演示".'}
                for aspect in ("3x4", "4x3", "16x9")
            },
        }
        output = io.StringIO()
        with patch.object(sys, "argv", argv), patch.dict(os.environ, {"ZENMUX_API_KEY": ""}), \
                patch.object(COVER, "run_analysis", return_value=copy.deepcopy(model_result)), \
                patch.object(COVER, "post_json", side_effect=AssertionError("不允许网络调用")), \
                patch.object(COVER, "generate_images", side_effect=AssertionError("不允许生图调用")), \
                redirect_stdout(output):
            COVER.main()
        manifest = json.loads(output.getvalue())
        analysis = json.loads(Path(manifest["analysis_path"]).read_text(encoding="utf-8"))
        return manifest, analysis

    def test_secret_command_argument_is_rejected_without_echo(self):
        with self.assertRaises(ValueError) as error:
            self.run_pipeline(extra=("--api-key", "fake-test-secret"))
        self.assertNotIn("fake-test-secret", str(error.exception))

    def test_unknown_title_does_not_take_a_brand_from_subtitles(self):
        manifest, analysis = self.run_pipeline()
        self.assertEqual(manifest["logos"], [])
        self.assertEqual(analysis["logo_plan"]["outside_logo_or_mark"], "")
        for prompt in analysis["prompts"].values():
            self.assertIn("no verified product logo reference", prompt["prompt"])

    def test_title_brand_wins_over_topic_and_subtitles(self):
        manifest, _ = self.run_pipeline(title="Grok 实操", topic="Codex 辅助开发")
        self.assertEqual([item["label"] for item in manifest["logos"]], ["logo_01_grok"])

    def test_missing_primary_asset_does_not_select_the_topic_brand(self):
        logo_dir = self.work / "logos"
        logo_dir.mkdir()
        (logo_dir / "codex-openai.png").write_bytes((ROOT / "assets/product-logos/codex-openai.png").read_bytes())
        with patch.object(COVER, "PRODUCT_LOGO_DIR", logo_dir):
            manifest, _ = self.run_pipeline(title="Grok 实操", topic="Codex 辅助开发")
        self.assertEqual(manifest["logos"], [])

    def test_topic_can_supply_a_logo_without_a_title(self):
        manifest, _ = self.run_pipeline(title="", topic="飞书 CLI")
        self.assertEqual([item["label"] for item in manifest["logos"]], ["logo_01_feishu"])

    def test_subtitle_fallback_requires_no_title_or_topic(self):
        manifest, _ = self.run_pipeline(title="", topic="")
        self.assertEqual([item["label"] for item in manifest["logos"]], ["logo_01_codex-openai"])

    def test_explicit_logo_disables_automatic_selection(self):
        asset = ROOT / "assets/product-logos/deepseek.png"
        manifest, _ = self.run_pipeline(title="Codex 对比", extra=("--logo", str(asset)))
        self.assertEqual([item["label"] for item in manifest["logos"]], ["logo_01_deepseek"])

    def test_locked_title_reaches_every_written_sidecar(self):
        title = 'GPT-5.6 与 oil-html："A" 和 B\'s'
        manifest, analysis = self.run_pipeline(title=title)
        self.assertEqual(analysis["title"]["main"], title)
        self.assertEqual(len(manifest["prompt_sidecars"]), 3)
        for path in manifest["prompt_sidecars"].values():
            text = Path(path).read_text(encoding="utf-8")
            self.assertIn(json.dumps(title, ensure_ascii=False), text)
            self.assertNotIn("错误旧标题", text)
            self.assertNotIn("错误\\n旧标题", text)

    def test_prompt_without_title_field_gets_explicit_title(self):
        manifest, _ = self.run_pipeline(title="确定标题", prompt="Create a clean cover.")
        for path in manifest["prompt_sidecars"].values():
            self.assertIn('Title text: "确定标题"', Path(path).read_text(encoding="utf-8"))

    def test_short_or_latin_titles_are_not_split_inside_the_word(self):
        for title in ("好", "Codex", "GPT-5.6"):
            with self.subTest(title=title):
                _, analysis = self.run_pipeline(title=title)
                self.assertEqual(analysis["title"]["line_breaks"], [title])

    def test_reapplying_guards_does_not_duplicate_title_instructions(self):
        manifest, analysis = self.run_pipeline(title="确定标题")
        before = copy.deepcopy(analysis["prompts"])
        args = type("Args", (), {"title": "确定标题", "default_creator_portrait": False, "allow_subtitle": True})()
        COVER.apply_script_guards(args, analysis, Path(manifest["analysis_path"]).parent, [])
        self.assertEqual(analysis["prompts"], before)


if __name__ == "__main__":
    unittest.main()
