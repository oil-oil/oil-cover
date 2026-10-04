import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        shutil.copy2(ROOT / "setup.sh", self.work / "setup.sh")
        shutil.copy2(ROOT / "requirements.txt", self.work / "requirements.txt")
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.log = self.work / "commands.log"
        self.python = self.bin / "python3"
        self.python.write_text(
            """#!/bin/sh
printf 'base:%s\\n' \"$*\" >> \"$FAKE_LOG\"
if [ \"$1\" = '-m' ] && [ \"$2\" = 'venv' ]; then
    mkdir -p \"$3/bin\"
    cat > \"$3/bin/python3\" <<'EOF'
#!/bin/sh
printf 'venv:%s\\n' \"$*\" >> \"$FAKE_LOG\"
exit 0
EOF
    chmod +x \"$3/bin/python3\"
fi
exit 0
""",
            encoding="utf-8",
        )
        self.python.chmod(0o755)

    def environment(self, ffmpeg):
        env = os.environ.copy()
        env.update({
            "FAKE_LOG": str(self.log),
            "FFMPEG": str(ffmpeg),
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "PYTHON": str(self.python),
        })
        return env

    def test_setup_creates_and_reuses_the_skill_virtualenv(self):
        ffmpeg = self.bin / "ffmpeg"
        ffmpeg.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        ffmpeg.chmod(0o755)

        first = subprocess.run(
            ["bash", str(self.work / "setup.sh")],
            env=self.environment(ffmpeg),
            check=False,
            capture_output=True,
            text=True,
        )
        second = subprocess.run(
            ["bash", str(self.work / "setup.sh")],
            env=self.environment(ffmpeg),
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        commands = self.log.read_text(encoding="utf-8")
        self.assertEqual(commands.count("base:-m venv"), 1)
        self.assertIn("venv:-m pip install --quiet --upgrade pip", commands)
        self.assertIn(
            f"venv:-m pip install --quiet -r {self.work / 'requirements.txt'}",
            commands,
        )
        self.assertIn("venv:-c import numpy; from PIL import Image", commands)
        self.assertIn("oil-cover setup complete.", second.stdout)

    def test_setup_reports_missing_ffmpeg_before_creating_a_virtualenv(self):
        result = subprocess.run(
            ["bash", str(self.work / "setup.sh")],
            env=self.environment(self.bin / "missing-ffmpeg"),
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FFMPEG does not point to an executable", result.stderr)
        self.assertFalse((self.work / ".venv").exists())


if __name__ == "__main__":
    unittest.main()
