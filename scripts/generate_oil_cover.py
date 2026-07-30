#!/usr/bin/env python3
"""
Generate oil-cover Xiaohongshu and Bilibili covers with Zenmux.

The script reads the oil-cover reference rules, asks Gemini to select/plan a
cover, then calls gpt-image-2 to generate the final cover images.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


def _resolve_skill_dir() -> Path:
    """Locate the installed oil-cover skill directory without hardcoding a user.

    Prefer an explicit override, then the directory that owns this script. A
    project-local copy of the script falls back to installed Codex/Claude skills.
    Override with OIL_COVER_SKILL_DIR if needed.
    """
    override = os.environ.get("OIL_COVER_SKILL_DIR", "").strip()
    candidates = [Path(override)] if override else []
    script_skill_dir = Path(__file__).resolve().parent.parent
    if (script_skill_dir / "references" / "cover-rules.md").exists():
        candidates.append(script_skill_dir)
    candidates += [
        Path.home() / ".codex" / "skills" / "oil-cover",
        Path.home() / ".claude" / "skills" / "oil-cover",
    ]
    for candidate in candidates:
        if (candidate / "references" / "cover-rules.md").exists():
            return candidate
    return candidates[-1]


SKILL_DIR = _resolve_skill_dir()
DEFAULT_RULES_FILE = SKILL_DIR / "references" / "cover-rules.md"
DEFAULT_API_BASE = "https://zenmux.ai/api/v1"
DEFAULT_ANALYSIS_MODEL = "google/gemini-3.5-flash"
DEFAULT_IMAGE_MODEL = "openai/gpt-image-2"

USER_CONFIG_FILE = Path(
    os.environ.get("OIL_COVER_CONFIG", str(Path.home() / ".oil-cover" / "config.json"))
).expanduser()


def load_user_config() -> dict[str, Any]:
    if not USER_CONFIG_FILE.exists():
        return {}
    try:
        payload = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid oil-cover user config: {USER_CONFIG_FILE}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"oil-cover user config must be a JSON object: {USER_CONFIG_FILE}")
    return payload


USER_CONFIG = load_user_config()
CREATOR_NAME = str(USER_CONFIG.get("creator_name") or "the creator").strip()
configured_api_key_file = str(USER_CONFIG.get("api_key_file") or "").strip()
DEFAULT_API_KEY_FILE = (
    Path(configured_api_key_file).expanduser()
    if configured_api_key_file
    else Path.home() / ".config" / "oil-cover" / "zenmux_api_key"
)
PRODUCT_LOGO_DIR = SKILL_DIR / "assets" / "product-logos"
creator_portrait_config = USER_CONFIG.get("creator_portrait") or {}
if not isinstance(creator_portrait_config, dict):
    raise RuntimeError(f"creator_portrait config must be an object: {USER_CONFIG_FILE}")
configured_portrait_path = str(creator_portrait_config.get("path") or "").strip()
DEFAULT_CREATOR_PORTRAIT_OVERLAY = {
    "label": "configured_creator_portrait",
    "path": Path(configured_portrait_path).expanduser() if configured_portrait_path else None,
    "role": "local_code_composite",
}
DEFAULT_CREATOR_PORTRAIT_ENABLED = bool(creator_portrait_config.get("enabled", False))
CREATOR_PORTRAIT_LAYOUTS = {
    # The transparent asset is intentionally allowed to extend below the canvas.
    "3x4": {
        "width_ratio": 0.55,
        "top_ratio": 0.58,
        "right_ratio": -0.06,
        "safe_area": "x=48%-100%, y=56%-100%",
    },
    "4x3": {
        "width_ratio": 0.38,
        "top_ratio": 0.40,
        "right_ratio": -0.03,
        "safe_area": "x=60%-100%, y=37%-100%",
    },
    "16x10": {
        "width_ratio": 0.34,
        "top_ratio": 0.40,
        "right_ratio": -0.03,
        "safe_area": "x=64%-100%, y=37%-100%",
    },
}
RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}
AUTO_PRODUCT_LOGOS = [
    (r"\bkimi(?:\s+k3)?\b|月之暗面|Moonshot(?:\s*AI)?", "kimi.png"),
    (r"\bclaude\s+code\b|Claude Code|ClaudeCode|claude-code", "claude-code.png"),
    (r"\bcodex\b|Codex|代码智能体|Coding Agent", "codex-openai.png"),
    (r"\bchatgpt\b|ChatGPT|\bopenai\b|OpenAI", "openai.png"),
    (r"\bgemini\b|Gemini", "gemini.png"),
    (r"\banthropic\b|Anthropic", "anthropic.png"),
    (r"\bclaude\b|Claude", "claude.png"),
    (r"\bcursor\b|Cursor", "cursor.png"),
    (r"\bcopilot\b|Copilot|GitHub Copilot", "github-copilot.png"),
    (r"\bgithub\b|GitHub", "github.png"),
    (r"\bego\s+lite\b|ego-lite|ego browser|ego-browser", "ego-lite.png"),
    (r"\bselector\b|Selector|Visual Element Picker|元素选择器", "selector.png"),
    (r"\bqoder\b|Qoder", "qoder.png"),
    (r"\bqwen\b|Qwen|通义千问|千问|通义", "qwen.png"),
    (r"\blongcat(?:[-\s]?2(?:\.0)?)?\b|LongCat|Long Cat|美团龙猫", "longcat.png"),
]


def retry_delay(attempt: int) -> float:
    return min(2 ** attempt, 8) + attempt * 0.25


def read_urlopen_json(request: urllib.request.Request, timeout: int, *, attempts: int = 3) -> dict[str, Any]:
    last_error: BaseException | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE_HTTP_CODES or attempt == attempts - 1:
                body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"HTTP {exc.code} from {request.full_url}: {body}") from exc
            last_error = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == attempts - 1:
                raise RuntimeError(f"Network error from {request.full_url}: {exc}") from exc
            last_error = exc
        time.sleep(retry_delay(attempt))
    raise RuntimeError(f"Request failed after retries: {last_error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate oil-cover images with Zenmux.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", type=Path, help="Input video file.")
    source.add_argument(
        "--image",
        action="append",
        type=Path,
        help="Input screenshot/keyframe. Can be passed multiple times.",
    )
    source.add_argument(
        "--composite-base",
        type=Path,
        help="Composite the default creator portrait onto an already-generated person-free base image, without API calls.",
    )
    parser.add_argument(
        "--composite-output",
        type=Path,
        help="Output path for --composite-base. Default: <base>_with_creator.png.",
    )
    parser.add_argument(
        "--composite-aspect",
        choices=("3x4", "4x3", "16x10"),
        help="Layout for --composite-base. If omitted, infer it from the base dimensions.",
    )
    parser.add_argument("--title", default="", help="Known video title or desired topic title.")
    parser.add_argument("--topic", default="", help="Extra topic/context for the cover.")
    parser.add_argument("--subtitle", type=Path, help="Optional subtitle, transcript, or script file.")
    parser.add_argument("--logo", action="append", type=Path, help="Optional product logo image.")
    parser.add_argument("--rules-file", type=Path, default=DEFAULT_RULES_FILE)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Output root for frames, prompts, images, and logs. Default: output to the video (or image) directory.",
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--analysis-model", default=DEFAULT_ANALYSIS_MODEL)
    parser.add_argument("--image-model", default=DEFAULT_IMAGE_MODEL)
    parser.add_argument("--api-key", default="", help="Optional API key. Prefer ZENMUX_API_KEY.")
    parser.add_argument(
        "--api-key-file",
        type=Path,
        default=DEFAULT_API_KEY_FILE,
        help="Optional local file containing the Zenmux API key. Default: user config or ~/.config/oil-cover/zenmux_api_key.",
    )
    parser.add_argument("--frame-count", type=int, default=8, help="How many candidate frames the local prefilter surfaces for the analysis model to choose from. More candidates give the model better frame choices but a larger payload.")
    parser.add_argument(
        "--candidate-seconds",
        default="",
        help="Comma-separated timestamps to extract from the video, for example 1,8,24.5. Explicit manual override that skips the local prefilter.",
    )
    parser.add_argument(
        "--scan-fps",
        type=float,
        default=0.0,
        help="Sampling rate for the local prefilter scan. 0 = auto (2 fps for videos <= 5 min, otherwise 1 fps).",
    )
    parser.add_argument("--max-frame-width", type=int, default=1280)
    parser.add_argument(
        "--portrait-size",
        default="960x1280",
        help="Exact 3:4 size for the image API. Zenmux requires width and height divisible by 16.",
    )
    parser.add_argument(
        "--landscape-size",
        default="1280x960",
        help="Exact 4:3 size for the image API. Zenmux requires width and height divisible by 16.",
    )
    parser.add_argument(
        "--bilibili-size",
        default="1280x800",
        help="Exact 16:10 Bilibili size for the image API. Zenmux requires width and height divisible by 16.",
    )
    parser.add_argument(
        "--generation-only",
        action="store_true",
        help="Use /images/generations instead of /images/edits, so reference images are not uploaded to the image API.",
    )
    parser.add_argument(
        "--default-creator-portrait",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_CREATOR_PORTRAIT_ENABLED,
        help="Composite the configured transparent creator portrait with deterministic local code. Public default: disabled; configure creator_portrait.enabled or pass --default-creator-portrait.",
    )
    parser.add_argument(
        "--aspect",
        choices=("all", "both", "3x4", "4x3", "16x10"),
        default="all",
        help="Which cover aspect to generate. Default: all three in parallel. Legacy 'both' keeps 3x4 + 4x3.",
    )
    parser.add_argument(
        "--allow-subtitle",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether Gemini may add an external subtitle. Default: enabled. Use --no-allow-subtitle to keep only the main title.",
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Only run Gemini analysis and write prompts. Do not call the image API.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare local files and prompts for the analysis call, but do not call any API.",
    )
    parser.add_argument("--timeout", type=int, default=180)
    return parser.parse_args()


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def slugify(value: str, fallback: str = "oil-cover") -> str:
    value = value.strip() or fallback
    value = re.sub(r"[^\w\-\u4e00-\u9fff]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-_")
    return value[:80] or fallback


def read_text(path: Path | None, limit: int = 60000) -> str:
    if not path:
        return ""
    if not path.exists():
        fail(f"file does not exist: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > limit:
        return text[:limit] + "\n\n[TRUNCATED BY SCRIPT]\n"
    return text


def api_key_from_args(args: argparse.Namespace) -> str:
    key = args.api_key or os.environ.get("ZENMUX_API_KEY", "")
    if not key and args.api_key_file and args.api_key_file.exists():
        key = args.api_key_file.read_text(encoding="utf-8").strip()
    if not key and not args.dry_run:
        fail(
            f"ZENMUX_API_KEY is not set. Export it, put it in {DEFAULT_API_KEY_FILE}, or pass --dry-run."
        )
    return key


def ffprobe_duration(video: Path) -> float:
    if not shutil.which("ffprobe"):
        fail("ffprobe is required for video input.")
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ]
    )
    try:
        return max(float(result.stdout.strip()), 0.1)
    except ValueError as exc:
        raise RuntimeError(f"could not read duration for {video}") from exc


def parse_candidate_seconds(args: argparse.Namespace, duration: float) -> list[float]:
    """Parse the explicit --candidate-seconds manual override into clamped timestamps."""
    values = []
    for raw in args.candidate_seconds.split(","):
        raw = raw.strip()
        if raw:
            values.append(max(0.0, min(float(raw), duration)))
    return unique_times(values)


def unique_times(values: list[float]) -> list[float]:
    output: list[float] = []
    seen: set[int] = set()
    for value in values:
        marker = int(round(value * 10))
        if marker in seen:
            continue
        seen.add(marker)
        output.append(round(value, 2))
    return output


def extract_video_frames(args: argparse.Namespace, run_dir: Path) -> list[dict[str, str]]:
    video = args.video
    if not video or not video.exists():
        fail(f"video does not exist: {video}")
    if not shutil.which("ffmpeg"):
        fail("ffmpeg is required for video input.")

    frames_dir = run_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob("*.jpg"):
        stale.unlink()
    duration = ffprobe_duration(video)
    frames: list[dict[str, str]] = []

    # No forced first_frame: the local prefilter already scans the opening seconds, and a
    # forced t=0 frame is almost always a title/intro card that just pollutes the candidate set.
    for idx, timestamp in enumerate(resolve_candidate_timestamps(args, run_dir, duration), start=1):
        out = frames_dir / f"candidate_{idx:02d}_{timestamp:06.2f}s.jpg"
        extract_frame(video, timestamp, out, args.max_frame_width)
        frames.append({"label": f"candidate_{idx:02d}", "path": str(out), "timestamp": f"{timestamp:.2f}"})

    return frames


def extract_frame(video: Path, timestamp: float, output: Path, max_width: int) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            f"scale={max_width}:-2:force_original_aspect_ratio=decrease",
            "-q:v",
            "3",
            str(output),
        ]
    )


def _laplacian_variance(gray: Any) -> float:
    """Variance of the 4-neighbour Laplacian: a cheap, robust sharpness proxy.

    Low values mean blur / motion-blur / out-of-focus; high values mean crisp edges
    and detail. Computed with plain numpy slicing so no scipy/opencv dependency is needed.
    """
    lap = (
        4.0 * gray[1:-1, 1:-1]
        - gray[:-2, 1:-1]
        - gray[2:, 1:-1]
        - gray[1:-1, :-2]
        - gray[1:-1, 2:]
    )
    return float(lap.var())


def _scan_video_frames(
    args: argparse.Namespace, run_dir: Path, fps: float, width: int
) -> list[Path]:
    """Down-sample the whole video to small JPEGs for local scoring (one decode pass)."""
    scan_dir = run_dir / "scan"
    scan_dir.mkdir(parents=True, exist_ok=True)
    for stale in scan_dir.glob("scan_*.jpg"):
        stale.unlink()
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(args.video),
            "-vf",
            f"fps={fps},scale={width}:-2",
            "-q:v",
            "5",
            "-an",
            str(scan_dir / "scan_%05d.jpg"),
        ]
    )
    return sorted(scan_dir.glob("scan_*.jpg"))


def select_timestamps_local(
    args: argparse.Namespace, run_dir: Path, duration: float
) -> list[float]:
    """Pick candidate cover-frame timestamps locally, with no model call.

    Scans the whole video at a low resolution/fps, scores every sampled frame for
    sharpness (Laplacian variance), brightness and content (std-dev), hard-drops
    black / blown-out / near-uniform (blank/loading) frames, then returns the sharpest
    surviving frame in each of N time buckets so candidates are technically clean AND
    spread across the video. The analysis model then chooses the best one semantically.
    """
    try:
        import numpy as np
        from PIL import Image
    except Exception as exc:  # pragma: no cover - dependency guard
        raise RuntimeError(f"local frame selection needs numpy + Pillow: {exc}") from exc

    want = max(2, args.frame_count)
    scan_fps = args.scan_fps if args.scan_fps and args.scan_fps > 0 else (2.0 if duration <= 300 else 1.0)
    files = _scan_video_frames(args, run_dir, scan_fps, 384)
    if not files:
        raise RuntimeError("local scan produced no frames")

    scored: list[dict[str, Any]] = []
    for idx, path in enumerate(files):
        try:
            with Image.open(path) as im:
                gray = np.asarray(im.convert("L"), dtype=np.float32)
        except Exception:
            continue
        if gray.shape[0] < 3 or gray.shape[1] < 3:
            continue
        mean = float(gray.mean())
        std = float(gray.std())
        sharp = _laplacian_variance(gray)
        ts = idx / scan_fps
        if duration > 0.1:
            ts = min(ts, duration - 0.05)
        # Hard-reject: near-black, blown-out white, and near-uniform (blank/solid/loading) frames.
        usable = 15.0 <= mean <= 248.0 and std >= 8.0
        scored.append(
            {"ts": round(ts, 2), "mean": mean, "std": std, "sharp": sharp, "usable": usable}
        )

    if not scored:
        raise RuntimeError("local scan scored no frames")
    pool = [s for s in scored if s["usable"]] or scored

    # Temporal spread: split the timeline into `want` buckets, keep the sharpest survivor in each.
    buckets = max(1, want)
    seg = duration / buckets if duration > 0 else max((s["ts"] for s in pool), default=1.0) + 1.0
    picks: list[dict[str, Any]] = []
    for b in range(buckets):
        lo, hi = b * seg, (b + 1) * seg
        in_bucket = [s for s in pool if lo <= s["ts"] < hi]
        if not in_bucket:
            continue
        picks.append(max(in_bucket, key=lambda s: s["sharp"]))

    # Top up from the sharpest unused survivors if some buckets were empty.
    if len(picks) < want:
        chosen = {p["ts"] for p in picks}
        for s in sorted((s for s in pool if s["ts"] not in chosen), key=lambda s: s["sharp"], reverse=True):
            picks.append(s)
            chosen.add(s["ts"])
            if len(picks) >= want:
                break

    picks.sort(key=lambda s: s["ts"])
    times = unique_times([p["ts"] for p in picks])[:want]

    (run_dir / "frame_selection_local.json").write_text(
        json.dumps(
            {
                "scan_fps": scan_fps,
                "sampled": len(scored),
                "usable": sum(1 for s in scored if s["usable"]),
                "buckets": buckets,
                "picked": times,
                "detail": [
                    {
                        "ts": p["ts"],
                        "sharp": round(p["sharp"], 1),
                        "mean": round(p["mean"], 1),
                        "std": round(p["std"], 1),
                        "usable": p["usable"],
                    }
                    for p in picks
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if not times:
        raise RuntimeError("local frame selection produced no timestamps")
    return times


def resolve_candidate_timestamps(
    args: argparse.Namespace, run_dir: Path, duration: float
) -> list[float]:
    """Decide which timestamps to extract as candidate evidence frames.

    Either the explicit --candidate-seconds manual override, or the local ffmpeg
    prefilter. There is no silent quality-degrading fallback: if the prefilter
    cannot produce frames, the run fails loudly so the problem is visible.
    """
    if args.candidate_seconds.strip():
        return parse_candidate_seconds(args, duration)
    picks = select_timestamps_local(args, run_dir, duration)
    print(
        "Frame selection (local prefilter): " + ", ".join(f"{t:.2f}s" for t in picks),
        file=sys.stderr,
    )
    return picks


def copy_input_images(args: argparse.Namespace, run_dir: Path) -> list[dict[str, str]]:
    frames_dir = run_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames: list[dict[str, str]] = []
    for idx, src in enumerate(args.image or [], start=1):
        if not src.exists():
            fail(f"image does not exist: {src}")
        suffix = src.suffix.lower() or ".png"
        dst = frames_dir / f"input_{idx:02d}{suffix}"
        shutil.copy2(src, dst)
        frames.append({"label": f"input_{idx:02d}", "path": str(dst), "timestamp": ""})
    return frames


def infer_auto_logo_paths(args: argparse.Namespace, subtitle_text: str) -> list[Path]:
    if args.logo:
        return []

    primary_text = "\n".join(part for part in [args.title, args.topic] if part)
    fallback_text = subtitle_text[:4000]

    matched: list[Path] = []
    seen: set[str] = set()
    for text in [primary_text, fallback_text]:
        if not text.strip():
            continue
        for pattern, filename in AUTO_PRODUCT_LOGOS:
            if filename in seen:
                continue
            if re.search(pattern, text, flags=re.I):
                path = PRODUCT_LOGO_DIR / filename
                if path.exists():
                    matched.append(path)
                    seen.add(filename)
        if matched:
            break
    return matched[:3]


def convert_svg_to_png(src: Path, dst: Path) -> None:
    if not shutil.which("qlmanage"):
        fail(f"SVG logo requires qlmanage conversion on this system: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["qlmanage", "-t", "-s", "1024", "-o", str(dst.parent), str(src)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    generated = dst.parent / f"{src.name}.png"
    if not generated.exists():
        fail(f"failed to convert SVG logo to PNG: {src}\n{result.stdout}\n{result.stderr}")
    generated.replace(dst)
    trim_png_to_content(dst)


def trim_png_to_content(path: Path) -> None:
    try:
        from PIL import Image, ImageChops
    except Exception:
        return

    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")

        if alpha.getextrema()[0] < 250:
            bbox = alpha.point(lambda value: 255 if value > 8 else 0).getbbox()
            content = rgba
            mask = alpha
        else:
            background = rgba.getpixel((rgba.width - 1, rgba.height - 1))
            diff = ImageChops.difference(rgba, Image.new("RGBA", rgba.size, background))
            mask = diff.convert("L").point(lambda value: 255 if value > 10 else 0)
            bbox = mask.getbbox()
            content = rgba

        if not bbox:
            return

        cropped = content.crop(bbox)
        cropped_mask = mask.crop(bbox)
        cropped.putalpha(cropped_mask)
        padding = max(16, int(max(cropped.size) * 0.08))
        side = max(cropped.width, cropped.height) + padding * 2
        output = Image.new("RGBA", (side, side), (255, 255, 255, 0))
        output.paste(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2), cropped)
        output.save(path)


def copy_logos(args: argparse.Namespace, run_dir: Path, subtitle_text: str = "") -> list[dict[str, str]]:
    refs_dir = run_dir / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)
    refs: list[dict[str, str]] = []
    logo_sources = list(args.logo or []) + infer_auto_logo_paths(args, subtitle_text)
    seen: set[Path] = set()
    for idx, src in enumerate(logo_sources, start=1):
        src = src.resolve()
        if src in seen:
            continue
        seen.add(src)
        if not src.exists():
            fail(f"logo/reference does not exist: {src}")
        suffix = src.suffix.lower() or ".png"
        if suffix == ".svg":
            dst = refs_dir / f"logo_{idx:02d}_{slugify(src.stem)}.png"
            convert_svg_to_png(src, dst)
        else:
            dst = refs_dir / f"logo_{idx:02d}_{slugify(src.stem)}{suffix}"
            shutil.copy2(src, dst)
        refs.append({"label": f"logo_{idx:02d}_{src.stem}", "path": str(dst)})
    return refs


def prepare_creator_portrait_overlay(run_dir: Path) -> dict[str, Any]:
    overlays_dir = run_dir / "overlays"
    overlays_dir.mkdir(parents=True, exist_ok=True)
    configured_path = DEFAULT_CREATOR_PORTRAIT_OVERLAY.get("path")
    if not configured_path:
        fail(
            "creator portrait is enabled but creator_portrait.path is missing "
            f"from {USER_CONFIG_FILE}"
        )
    src = Path(configured_path)
    if not src.exists():
        fail(f"default creator portrait overlay is missing: {src}")
    dst = overlays_dir / "creator-portrait.png"
    shutil.copy2(src, dst)
    return {
        "label": str(DEFAULT_CREATOR_PORTRAIT_OVERLAY["label"]),
        "path": str(dst),
        "source_path": str(src),
        "role": str(DEFAULT_CREATOR_PORTRAIT_OVERLAY["role"]),
        "layouts": CREATOR_PORTRAIT_LAYOUTS,
    }


def creator_portrait_plan(enabled: bool, overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    if not enabled:
        return {
            "enabled": False,
            "mode": "none",
            "placement": "none",
            "reserve_base_area": False,
        }
    return {
        "enabled": True,
        "mode": "local_code_composite",
        "asset": str((overlay or {}).get("path", DEFAULT_CREATOR_PORTRAIT_OVERLAY["path"])),
        "placement": "lower-right, right-edge anchored, bottom-clipped",
        "reserve_base_area": True,
        "layouts": CREATOR_PORTRAIT_LAYOUTS,
    }


def creator_portrait_prompt_guard(aspect_key: str) -> str:
    layout = CREATOR_PORTRAIT_LAYOUTS[aspect_key]
    right_ratio = float(layout["right_ratio"])
    right_placement = (
        f"extends {abs(right_ratio):.0%} past the right edge"
        if right_ratio < 0
        else f"right offset {right_ratio:.0%}"
    )
    return (
        " Local portrait composite guard: keep the generated base entirely person-free. "
        f"Reserve the bottom-right overlay-safe area {layout['safe_area']}; do not place the title, product "
        "logo, small labels, or primary evidence there. Continue the background and only noncritical screen "
        "detail beneath that area; do not draw a portrait, silhouette, placeholder, empty card, webcam bubble, "
        f"avatar, mascot, or character. After generation, deterministic local code will composite {CREATOR_NAME}'s "
        f"transparent paper-cut portrait at {layout['width_ratio']:.0%} of canvas width, {right_placement}, "
        f"top {layout['top_ratio']:.0%}, with natural bottom/right edge clipping."
    )


def composite_creator_portrait(
    base_path: Path,
    output_path: Path,
    overlay_path: Path,
    aspect_key: str,
) -> dict[str, Any]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for the default creator portrait composite.") from exc

    layout = CREATOR_PORTRAIT_LAYOUTS[aspect_key]
    with Image.open(base_path) as base_image, Image.open(overlay_path) as portrait_image:
        base = base_image.convert("RGBA")
        portrait = portrait_image.convert("RGBA")
        if portrait.getchannel("A").getbbox() is None:
            raise RuntimeError(f"creator portrait overlay has no visible alpha content: {overlay_path}")

        target_width = max(1, round(base.width * float(layout["width_ratio"])))
        target_height = max(1, round(portrait.height * target_width / portrait.width))
        portrait = portrait.resize((target_width, target_height), Image.Resampling.LANCZOS)

        right_offset = round(base.width * float(layout["right_ratio"]))
        x = base.width - right_offset - target_width
        y = round(base.height * float(layout["top_ratio"]))
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        layer.paste(portrait, (x, y), portrait)
        merged = Image.alpha_composite(base, layer).convert("RGB")

        temp_path = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp.png")
        merged.save(temp_path, format="PNG", optimize=True)
        os.replace(temp_path, output_path)

    return {
        "mode": "local_code_composite",
        "asset": str(overlay_path),
        "base_image": str(base_path),
        "output_image": str(output_path),
        "canvas": {"width": base.width, "height": base.height},
        "placement": {
            "x": x,
            "y": y,
            "width": target_width,
            "height": target_height,
            "width_ratio": layout["width_ratio"],
            "top_ratio": layout["top_ratio"],
            "right_ratio": layout["right_ratio"],
            "clipped_bottom_px": max(0, y + target_height - base.height),
            "clipped_right_px": max(0, x + target_width - base.width),
        },
    }


def infer_creator_portrait_aspect(base_path: Path) -> str:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for the default creator portrait composite.") from exc
    with Image.open(base_path) as image:
        if image.height >= image.width:
            return "3x4"
        ratio = image.width / image.height
        return "16x10" if abs(ratio - 1.6) < abs(ratio - (4 / 3)) else "4x3"


def image_to_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def build_analysis_messages(
    args: argparse.Namespace,
    frames: list[dict[str, str]],
    logos: list[dict[str, str]],
    creator_portrait_overlay: dict[str, Any] | None,
    skill_rules: str,
    subtitle_text: str,
) -> list[dict[str, Any]]:
    frame_list = "\n".join(
        f"- {item['label']}: {item['path']} timestamp={item.get('timestamp', '')}" for item in frames
    )
    logo_list = "\n".join(f"- {item['label']}: {item['path']}" for item in logos) or "None"
    portrait_plan = creator_portrait_plan(args.default_creator_portrait, creator_portrait_overlay)
    subtitle_instruction = (
        "A short external subtitle is allowed when it strengthens the cover; keep it clearly smaller "
        "than the main title and aligned on the same editorial grid."
        if args.allow_subtitle
        else "Do not add an external subtitle; keep the outside cover text limited to the main title and the small product mark."
    )
    system_text = (
        f"You are an expert cover art director for {CREATOR_NAME}'s Xiaohongshu and Bilibili AI tool tutorial videos. "
        "Use the supplied oil-cover skill rules as the design spec. "
        "Treat supplied screenshots as evidence sources, not as full images to copy. "
        "Before writing prompts, decide the one-glance subject: what result should be visible "
        "within 0.5 seconds in a phone feed. Make that subject the dominant visual evidence, "
        "and make every other UI element serve or yield to it. "
        "Extract the few UI signals that explain the topic, rebuild them into a clean cover-ready screen, "
        "and remove irrelevant navigation, long transcripts, old subtitles, random avatars, paths, timestamps, and tiny noisy text. "
        +
        (
            "The generated base must stay completely person-free. Reserve the deterministic lower-right portrait overlay-safe "
            "area described below so the title, logo, labels, and primary evidence remain unobstructed. Do not draw the creator, "
            "a silhouette, a placeholder, an avatar, a webcam bubble, a mascot, or any other person. A local code step adds the "
            "single supplied transparent paper-cut creator portrait after generation. "
            if args.default_creator_portrait
            else "This cover must stay completely person-free: do not add any human, face, creator portrait, avatar, webcam bubble, mascot, or character. "
        )
        +
        "The final image generator is Zenmux openai/gpt-image-2. The local script only extracts frames, "
        "copies files, saves prompts, calls Zenmux APIs"
        +
        (
            ", and performs one permitted deterministic post-step: alpha-compositing the fixed creator portrait overlay. "
            "The image model receives only the selected frame and product logo references; the creator portrait is never "
            "uploaded as a generation reference. "
            if args.default_creator_portrait
            else ". No portrait post-processing is performed for this explicitly person-free cover. "
        )
        +
        "It never adds text, pastes Logos, changes layout, crops the generated cover, or performs visual repairs locally. "
        +
        "IMPORTANT: each prompt you write IS the final and complete instruction sent to the image model; "
        "no extra rules are appended afterwards. So make every prompt fully self-contained and internally "
        "consistent. State the screenshot distillation, the visual-communication priority, the screen crop, "
        "the layout, the text styling, and a short avoid list ONCE each, in plain language. Do not repeat the "
        "same instruction in different words, do not give conflicting numbers or directions, and never rely "
        "on post-processing to fix the prompt. Prefer a tight, unambiguous prompt over a long padded one. "
        "Visual quality bar, fold these naturally into the one prompt without padding: "
        "(1) design an intentional colour scheme with real atmosphere: a clean light base (white, light "
        "gray, or a very pale tinted paper) carrying a soft pastel colour atmosphere of 1-3 neighbouring "
        "hues that blend gently at the edges/corners/behind the screen — name the hues explicitly, for "
        "example dusty periwinkle + soft pink, or cream + pale gold. Sample hues from the frame or logo "
        "but soften them to a creamy/dusty pastel; never the raw high-saturation UI colour (no acid lime, "
        "no neon green, no electric blue, no fluorescent blocks) and never a full-spectrum rainbow. The "
        "atmosphere must be clearly visible — a nearly colorless gray canvas reads as unfinished — yet "
        "stay soft and airy. Pair it with one pastel keyword chip on the title whose hue echoes the "
        "atmosphere; "
        "(2) make the screen/browser object intentionally overflow and get clipped by at least one canvas "
        "edge, showing only about 80%-95% of it while keeping a visible top-left window edge, for a premium "
        "editorial close-up with real depth, never a small fully-centered complete screenshot; "
        "(3) ground the screen with a soft graphite drop shadow plus a subtle contact shadow; "
        "(4) when the evidence is a row of cards or thumbnails, show 3 oversized cards fully plus a 4th "
        "clipped at the edge, not a flat strip of small ones; "
        "(5) place the screen/browser object at a subtle 3D perspective tilt — rotated only a few degrees in "
        "space (about 5-12 degrees) as if seen slightly from one side, with one edge nearer the viewer — for "
        "gentle parallax depth and dimensionality; this intentionally overrides any 'front-facing flat / "
        "0-degree rotation / no diagonal edge' default in the rules; keep all UI text readable and avoid "
        "extreme skew, fisheye, warping, or heavy rotation; "
        "(6) make the main title unmistakably large — the covers live in phone and desktop feeds: in the 3:4 portrait "
        "prompt each title line spans about 90%-96% of the safe-area width with a cap height around 8%-12% "
        "of the canvas height; in the 4:3 landscape prompt each title line's cap height is about 11%-15% of "
        "the canvas height with 3-6 characters per line; in the 16:10 Bilibili prompt use the same cap-height "
        "range and keep the title as the first anchor while using the extra width for larger screen evidence; "
        "when unsure, go bigger and break the title into "
        "two short lines instead of shrinking it. "
        "Return strict JSON only."
    )
    user_text = f"""
Task:
Create a complete external Zenmux workflow plan for an oil-cover style Xiaohongshu and Bilibili cover set.

Known title (already distilled by the operator; treat as the final cover headline):
{args.title or "None"}

Extra topic/context:
{args.topic or "None"}

Candidate frames:
{frame_list}

Logo/reference images:
{logo_list}

Deterministic creator portrait overlay plan (not a generation reference image):
{json.dumps(portrait_plan, ensure_ascii=False, indent=2)}

Subtitle/transcript/script excerpt:
{subtitle_text or "None"}

Oil-cover skill rules:
{skill_rules}

Output strict JSON with this schema:
{{
  "task_type": "video_cover or image_cover",
  "selected_frame": {{
    "label": "",
    "path": "",
    "timestamp": "",
    "score": 0,
    "reason": ""
  }},
  "backup_frames": [
    {{"label": "", "path": "", "reason": ""}}
  ],
  "content_attribution": {{
    "main_topic": "",
    "main_product": "",
    "host_interface": "",
    "supporting_brands": []
  }},
  "title": {{
    "main": "",
    "line_breaks": [],
    "subtitle": ""
  }},
  "logo_plan": {{
    "outside_logo_or_mark": "",
    "source": "",
    "reason": ""
  }},
  "creator_portrait_plan": {{
    "enabled": {str(bool(args.default_creator_portrait)).lower()},
    "mode": "{'local_code_composite' if args.default_creator_portrait else 'none'}",
    "placement": "{'lower-right, right-edge anchored, bottom-clipped' if args.default_creator_portrait else 'none'}",
    "reserve_base_area": {str(bool(args.default_creator_portrait)).lower()},
    "reason": ""
  }},
  "color_plan": {{
    "base": "",
    "gradient_source": "",
    "accent": "",
    "text_colors": ""
  }},
  "screenshot_distillation": {{
    "keep": [],
    "remove": [],
    "rebuild_as": "",
    "reason": ""
  }},
  "visual_communication": {{
    "one_glance_subject": "",
    "primary_evidence": "",
    "supporting_evidence": [],
    "sacrifice_if_crowded": [],
    "primary_evidence_share": "55%-75% of the screen content area",
    "phone_feed_readability_note": ""
  }},
  "cover_direction_markdown": "",
  "prompts": {{
    "3x4": {{
      "size": "{args.portrait_size}",
      "prompt": ""
    }},
    "4x3": {{
      "size": "{args.landscape_size}",
      "prompt": ""
    }},
    "16x10": {{
      "size": "{args.bilibili_size}",
      "prompt": ""
    }}
  }},
  "quality_checklist": []
}}

Important:
- When a known title is provided, it is the final cover headline already distilled by the operator from the video content: use it as title.main essentially verbatim — you own only line breaks, typographic emphasis, and dropping a leading filler word if one slipped in. Do not rewrite it, soften it, or revert it to a generic video-title phrasing. Only when the known title is None should you distill title.main yourself from the subtitle/transcript, preferring the strongest concrete verdict in the speaker's own words.
- Choosing selected_frame is the single biggest quality lever. The candidate frames have already been locally prefiltered for technical quality (sharpness, brightness, content) and spread across the video, so they should all be reasonably crisp — spend your judgement on WHICH one best represents the subject: prefer the frame that most clearly shows the named tool/product actually in use (its real interface, panel, result, or action), fully visible, clean, and large. Still reject any that slipped through: blurry/motion-blurred, fade/transition, near-empty intros, loading states, mostly-plain-text, or frames where the main evidence is occluded, cropped, or tiny. If several frames are similar, pick the cleanest and most on-topic; list the next best ones in backup_frames.
- The three prompts must explicitly mention exact 3:4, exact 4:3, and exact 16:10 respectively.
- The prompts must include the mandatory visible background sentence from the rules.
- The color_plan must follow the cover colour system from the rules: a clean light base plus a soft pastel atmosphere of 1-3 neighbouring hues, and one keyword-chip accent echoing the atmosphere. Write gradient_source as the named pastel hues (e.g. "dusty periwinkle + soft pink") and accent as the chip colour — creamy/dusty versions, never the raw saturated UI colour, never neon or full-spectrum rainbow.
- The prompts must tell gpt-image-2 to create one complete final cover in one image.
- The prompts must preserve real tutorial evidence from the selected frame and remove unrelated people/webcam/avatar/subtitles from the source screen and rebuilt UI.
- {"The prompts must keep the generated base person-free and reserve the lower-right portrait overlay-safe area. For 3:4 reserve x=48%-100%, y=56%-100%; for 4:3 reserve x=60%-100%, y=37%-100%; for 16:10 reserve x=64%-100%, y=37%-100%. Put no title, logo, label, or primary evidence there. Continue only background and noncritical screen detail under it; never draw a placeholder or portrait. The local script will composite the fixed transparent paper-cut portrait after generation." if args.default_creator_portrait else "The prompts must not add a creator portrait. Keep the final cover completely person-free: no human face, no avatar, no webcam bubble, no mascot, no character, and no portrait thumbnail."}
- {"Do not request or depend on the creator portrait as a generation reference. The portrait is applied later at a fixed layout: 3:4 = 55% canvas width, 6% past the right edge, top 58%; 4:3 = 38% canvas width, 3% past the right edge, top 40%; 16:10 = 34% canvas width, 3% past the right edge, top 40%; natural bottom/right clipping is intentional." if args.default_creator_portrait else "Use software UI evidence, product logo, workflow chips, cursor marks, panels, and text hierarchy as the personal-brand signal instead of any person or face."}
- The prompts must not copy the selected screenshot as-is. They must specify a screenshot distillation plan: keep only 2-3 essential UI signals, remove noisy sidebars/long text/unrelated details, and rebuild the screen area as a clean real-feeling UI.
- The prompts must include a visual communication plan: the one-glance subject, the primary evidence, the maximum size of supporting evidence, and what to delete/crop if the primary evidence becomes too small.
- If the primary evidence is a row/grid/gallery/list of result cards, cover thumbnails, generated images, or comparison examples, the prompts must make those results large and readable as the dominant gallery. Do not shrink them into a faithful full-workspace screenshot.
- The prompts must include a title decoration plan: the title area cannot be plain text only. Add 1-2 tasteful, content-related title accents such as a subtle keyword highlight, thin underline, small workflow label, cursor mark, bracket, or UI state chip derived from the current title, screenshot, subtitle, topic, or product identity.
- The prompts must not ask for local post-processing.
- {subtitle_instruction}
- For the 4:3 and 16:10 horizontal prompts, the main title must be the first visual anchor, while the selected screen evidence remains large and readable. All prompts must state the title size explicitly (portrait: each line spans ~90%-96% of the safe-area width; landscape: cap height ~11%-15% of canvas height) so the title cannot come out small.
"""
    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    for item in frames:
        content.append({"type": "text", "text": f"Frame {item['label']} timestamp={item.get('timestamp', '')}"})
        content.append({"type": "image_url", "image_url": {"url": image_to_data_uri(Path(item["path"]))}})
    for item in logos:
        content.append({"type": "text", "text": f"Logo/reference {item['label']}"})
        content.append({"type": "image_url", "image_url": {"url": image_to_data_uri(Path(item["path"]))}})
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": content},
    ]


def post_json(url: str, payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    return read_urlopen_json(request, timeout)


def post_multipart(
    url: str,
    fields: dict[str, str],
    files: list[tuple[str, Path]],
    api_key: str,
    timeout: int,
) -> dict[str, Any]:
    boundary = f"----oilcover-{uuid.uuid4().hex}"
    body = bytearray()

    def add_line(value: str) -> None:
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    for name, value in fields.items():
        add_line(f"--{boundary}")
        add_line(f'Content-Disposition: form-data; name="{name}"')
        add_line("")
        add_line(value)

    for field_name, path in files:
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        add_line(f"--{boundary}")
        add_line(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"'
        )
        add_line(f"Content-Type: {mime}")
        add_line("")
        body.extend(path.read_bytes())
        body.extend(b"\r\n")

    add_line(f"--{boundary}--")

    request = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    return read_urlopen_json(request, timeout)


def extract_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini did not return valid JSON: {exc}\n{text[:2000]}") from exc


def run_analysis(
    args: argparse.Namespace,
    api_key: str,
    messages: list[dict[str, Any]],
    run_dir: Path,
) -> dict[str, Any]:
    payload = {
        "model": args.analysis_model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    (run_dir / "analysis_request.json").write_text(
        json.dumps(redact_payload(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if args.dry_run:
        analysis = {
            "task_type": "dry_run",
            "selected_frame": {},
            "prompts": {
                "3x4": {"size": args.portrait_size, "prompt": ""},
                "4x3": {"size": args.landscape_size, "prompt": ""},
                "16x10": {"size": args.bilibili_size, "prompt": ""},
            },
            "cover_direction_markdown": "Dry run only. No API call was made.",
        }
        (run_dir / "analysis.json").write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return analysis

    last_error: Exception | None = None
    analysis: dict[str, Any] | None = None
    for attempt in range(3):
        response = post_json(
            f"{args.api_base.rstrip('/')}/chat/completions",
            payload,
            api_key,
            args.timeout,
        )
        (run_dir / "analysis_response.raw.json").write_text(
            json.dumps(response, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        text = response["choices"][0]["message"]["content"]
        try:
            analysis = extract_json_from_text(text)
            break
        except RuntimeError as exc:
            last_error = exc
            print(f"Analysis JSON parse failed (attempt {attempt + 1}/3): {exc}", file=sys.stderr)
    if analysis is None:
        raise RuntimeError(f"Gemini analysis did not return valid JSON after retries: {last_error}")
    (run_dir / "analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return analysis


def redact_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        out = {}
        for key, value in payload.items():
            if key == "url" and isinstance(value, str) and value.startswith("data:"):
                out[key] = value[:64] + "...[base64 omitted]"
            else:
                out[key] = redact_payload(value)
        return out
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    return payload


def requested_aspects(args: argparse.Namespace) -> tuple[str, ...]:
    if args.aspect == "all":
        return ("3x4", "4x3", "16x10")
    if args.aspect == "both":
        return ("3x4", "4x3")
    return (args.aspect,)


def aspect_size(args: argparse.Namespace, aspect_key: str) -> str:
    return {
        "3x4": args.portrait_size,
        "4x3": args.landscape_size,
        "16x10": args.bilibili_size,
    }[aspect_key]


def strip_external_subtitle(prompt: str) -> str:
    patterns = [
        r";?\s*optional subtitle\s+['\"“][^'\"”]+['\"”]\.?",
        r";?\s*subtitle\s+['\"“][^'\"”]+['\"”]\.?",
        r";?\s*with subtitle\s+['\"“][^'\"”]+['\"”]\.?",
        r";?\s*副标题\s*[：:]\s*['\"“][^'\"”]+['\"”]\.?",
    ]
    for pattern in patterns:
        prompt = re.sub(pattern, ".", prompt, flags=re.I)
    prompt = re.sub(r"\s+\.", ".", prompt)
    prompt = re.sub(r"\.{2,}", ".", prompt)
    return prompt.strip()


def product_logo_guard(logos: list[dict[str, str]]) -> str:
    if not logos:
        return ""
    names = ", ".join(Path(item.get("path", "")).name for item in logos if item.get("path"))
    return (
        " Product identity guard: use the supplied logo reference image"
        f"{'s' if len(logos) > 1 else ''} ({names}) for the real product mark. "
        "Preserve the reference logo's actual silhouette, proportions, and mark style. "
        "Do not invent, simplify, replace, or approximate it with a generic code icon, braces icon, "
        "random abstract symbol, unrelated app logo, or text-only substitute."
    )


def hard_rule_backfill(
    prompt: str,
    aspect_key: str,
    logos: list[dict[str, str]],
    analysis: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    """Append a rule ONLY when the model's own prompt omitted it.

    The Gemini prompt is trusted to cover distillation, visual priority, crop,
    layout and decoration in one self-contained pass (see the system prompt). The
    script does not re-stack those guards; it enforces the few non-negotiables and
    backfills the depth/colour quality cues the model skipped, so prompts stay
    short and never contradict themselves.
    """
    analysis = analysis or {}
    notes: list[str] = []
    low = prompt.lower()
    aspect_phrase = {
        "3x4": "3:4",
        "4x3": "4:3",
        "16x10": "16:10",
    }[aspect_key]

    if aspect_phrase not in prompt:
        prompt += f" Output exactly one complete {aspect_phrase} cover in a single image."
        notes.append(f"{aspect_key}: backfilled exact aspect.")

    if "grid" not in low or "background" not in low:
        prompt += (
            " Mandatory visible background: full-canvas clean base, visible fine grid, a soft pastel "
            "colour atmosphere of 1-3 neighbouring hues (sampled from the selected image, softened to a "
            "creamy/dusty pastel) glowing gently from the edges or corners, very light grain; the "
            "atmosphere must be clearly visible yet soft — no neon or acid hues, no full-spectrum "
            "rainbow, no plain colourless canvas."
        )
        notes.append(f"{aspect_key}: backfilled mandatory background.")

    # Specific colour sampling: avoid a vague 'sampled from the image' with no named hue.
    color_plan = analysis.get("color_plan", {}) if isinstance(analysis.get("color_plan"), dict) else {}
    gradient_source = str(color_plan.get("gradient_source", "")).strip()
    accent = str(color_plan.get("accent", "")).strip()
    hues = ("orange", "blue", "green", "red", "purple", "pink", "cyan", "amber", "teal",
            "violet", "warm", "cool", "cream", "lime", "indigo", "gold", "yellow")
    if not any(h in low for h in hues):
        if gradient_source or accent:
            detail = gradient_source or "the dominant tones of the selected image"
            tail = f"; title accent uses {accent}" if accent else ""
            prompt += (
                f" Colour sampling: build the background atmosphere from {detail}{tail}; soften every hue "
                "to a creamy/dusty pastel before use."
            )
            notes.append(f"{aspect_key}: backfilled specific colour sampling.")
        else:
            prompt += (
                " Colour sampling: sample 1-3 neighbouring hues of the selected screen for the background "
                "atmosphere and title accent, softened to creamy/dusty pastels."
            )
            notes.append(f"{aspect_key}: backfilled colour-hue instruction.")

    # Colour discipline: a visible pastel atmosphere — neither neon nor colourless.
    if not any(k in low for k in ("pastel", "creamy", "dusty", "muted", "desaturat", "soft pink",
                                  "pale gold", "periwinkle")):
        prompt += (
            " Colour discipline: the background must carry a clearly visible soft pastel atmosphere of 1-3 "
            "neighbouring hues blending gently at the edges or behind the screen, with one pastel keyword "
            "chip echoing it — never neon or acid hues, fluorescent blocks, or a full-spectrum rainbow; but "
            "never a plain colourless gray canvas either."
        )
        notes.append(f"{aspect_key}: backfilled colour discipline.")

    # Screen depth crop: overflow + edge clip for the premium close-up (立体感).
    if not any(k in low for k in ("overflow", "clipped by", "cropped by", "clip the", "crop the",
                                  "bleed", "off the canvas", "beyond the canvas", "edge of the canvas")):
        prompt += (
            " Screen depth crop: the screen/browser object must intentionally overflow and be clipped by at "
            "least one canvas edge, showing only about 80%-95% of it while keeping a visible top-left window "
            "edge, for a premium editorial close-up with real depth; never a small fully-centered complete screenshot."
        )
        notes.append(f"{aspect_key}: backfilled screen overflow crop.")

    # Subtle 3D perspective tilt for parallax depth (overrides the flat default).
    if not any(k in low for k in ("perspective tilt", "3d perspective", "parallax", "tilted", "angled view", "isometric")):
        prompt += (
            " Perspective override: render the screen object at a subtle 3D perspective tilt of about 5-12 degrees "
            "(seen slightly from one side, one edge nearer the viewer) for gentle parallax depth; this overrides any "
            "front-facing-flat or 0-degree wording above. Keep UI text readable; avoid extreme skew or warping."
        )
        notes.append(f"{aspect_key}: backfilled subtle 3D perspective tilt.")

    # Shadow with a grounding contact layer for depth.
    if "shadow" not in low:
        prompt += (
            " Shadow: clean light graphite drop shadow close to `0 18px 44px rgba(30,35,40,0.10)` plus a soft "
            "contact shadow `0 4px 12px rgba(30,35,40,0.06)` under the screen object for grounded depth."
        )
        notes.append(f"{aspect_key}: backfilled layered shadow.")
    elif "contact" not in low:
        prompt += " Add a soft contact shadow close to `0 4px 12px rgba(30,35,40,0.06)` under the screen for grounded depth."
        notes.append(f"{aspect_key}: backfilled contact shadow.")

    logo_guard = product_logo_guard(logos)
    if logo_guard and "Product identity guard:" not in prompt and "logo reference" not in low:
        prompt += logo_guard
        notes.append(f"{aspect_key}: backfilled product logo reference.")

    return prompt, notes


def apply_script_guards(
    args: argparse.Namespace,
    analysis: dict[str, Any],
    run_dir: Path,
    logos: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Lean link: trust the model's self-contained prompt; backfill hard rules only.

    Unlike the legacy link, this does NOT append distillation / visual / crop /
    decoration / layout guards onto every prompt. Those are the model's job now.
    We only enforce non-negotiables such as exact aspect, mandatory background,
    depth cues, real logo, and the deterministic creator-overlay safe area when
    the prompt omitted them.
    """
    if not isinstance(analysis, dict):
        return analysis
    logos = logos or []
    analysis["creator_portrait_plan"] = creator_portrait_plan(args.default_creator_portrait)

    title = analysis.setdefault("title", {})
    if isinstance(title, dict) and not args.allow_subtitle:
        title["subtitle"] = ""

    prompts = analysis.setdefault("prompts", {})
    if not isinstance(prompts, dict):
        return analysis

    postprocess_notes: list[str] = []
    for key, item in prompts.items():
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt", "")).strip()
        if not prompt:
            continue

        if not args.allow_subtitle:
            updated = strip_external_subtitle(prompt)
            if updated != prompt:
                postprocess_notes.append(f"{key}: removed external subtitle from prompt.")
            prompt = updated
            if "No external subtitle" not in prompt:
                prompt += " No external subtitle outside the main title; keep the outside cover text limited to the main title and the small product mark."
                postprocess_notes.append(f"{key}: enforced no-subtitle.")

        prompt, notes = hard_rule_backfill(prompt, key, logos, analysis)
        postprocess_notes.extend(notes)

        if (
            args.default_creator_portrait
            and key in CREATOR_PORTRAIT_LAYOUTS
            and "Local portrait composite guard:" not in prompt
        ):
            prompt += creator_portrait_prompt_guard(key)
            postprocess_notes.append(f"{key}: reserved deterministic creator portrait overlay area.")

        item["prompt"] = prompt

    if postprocess_notes:
        analysis["script_postprocess_notes"] = postprocess_notes
        (run_dir / "script_postprocess_notes.json").write_text(
            json.dumps(postprocess_notes, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    (run_dir / "analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return analysis


def write_cover_plan(
    run_dir: Path,
    analysis: dict[str, Any],
    frames: list[dict[str, str]],
    logos: list[dict[str, str]],
    creator_portrait_overlay: dict[str, Any] | None,
) -> None:
    lines = [
        "# Oil Cover Zenmux Test",
        "",
        "## Selected Frame",
        "",
        json.dumps(analysis.get("selected_frame", {}), ensure_ascii=False, indent=2),
        "",
        "## Content Attribution",
        "",
        json.dumps(analysis.get("content_attribution", {}), ensure_ascii=False, indent=2),
        "",
        "## Title",
        "",
        json.dumps(analysis.get("title", {}), ensure_ascii=False, indent=2),
        "",
        "## Creator Portrait Plan",
        "",
        json.dumps(analysis.get("creator_portrait_plan", {}), ensure_ascii=False, indent=2),
        "",
        "## Screenshot Distillation",
        "",
        json.dumps(analysis.get("screenshot_distillation", {}), ensure_ascii=False, indent=2),
        "",
        "## Direction",
        "",
        analysis.get("cover_direction_markdown", ""),
        "",
        "## Local References",
        "",
        "Frames:",
        *[f"- {item['label']}: {item['path']} timestamp={item.get('timestamp', '')}" for item in frames],
        "",
        "Logos:",
        *([f"- {item['label']}: {item['path']}" for item in logos] or ["- None"]),
        "",
        "Creator Portrait Local Overlay (not sent to the image model):",
        json.dumps(creator_portrait_overlay or {"enabled": False}, ensure_ascii=False, indent=2),
    ]
    (run_dir / "cover_plan.md").write_text("\n".join(lines), encoding="utf-8")


def prompt_sidecar_text(
    aspect_key: str,
    size: str,
    prompt: str,
    analysis: dict[str, Any],
    refs: list[Path],
    result_path: str = "PENDING",
    status: str = "PENDING",
    portrait_composite: dict[str, Any] | None = None,
) -> str:
    selected = analysis.get("selected_frame", {})
    composite_text = json.dumps(portrait_composite, ensure_ascii=False, indent=2) if portrait_composite else "None"
    return f"""# Oil Cover Prompt Sidecar

Use: Xiaohongshu and Bilibili oil-cover external Zenmux workflow
Aspect: {aspect_key}
Size: {size}
Selected frame: {selected.get("label", "")} {selected.get("path", "")}
Reference images:
{chr(10).join(f"- {path}" for path in refs) if refs else "- None"}

Generation result: {result_path}
Status: {status}
Creator portrait composite:
{composite_text}

## Final Prompt

{prompt}
"""


def save_prompt_sidecars(
    args: argparse.Namespace,
    run_dir: Path,
    analysis: dict[str, Any],
    refs: list[Path],
) -> dict[str, Path]:
    prompts = analysis.get("prompts", {})
    paths: dict[str, Path] = {}
    for key in requested_aspects(args):
        item = prompts.get(key, {})
        prompt = item.get("prompt", "")
        size = aspect_size(args, key)
        sidecar = run_dir / f"{key}.prompt.md"
        sidecar.write_text(
            prompt_sidecar_text(key, size, prompt, analysis, refs),
            encoding="utf-8",
        )
        paths[key] = sidecar
    return paths


def find_output_value(value: Any, key: str) -> str:
    if isinstance(value, dict):
        if isinstance(value.get(key), str):
            return value[key]
        for child in value.values():
            found = find_output_value(child, key)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = find_output_value(child, key)
            if found:
                return found
    return ""


def save_image_response(response: dict[str, Any], output: Path, timeout: int) -> None:
    b64 = find_output_value(response, "b64_json")
    if b64:
        output.write_bytes(base64.b64decode(b64))
        return
    url = find_output_value(response, "url")
    if url:
        request = urllib.request.Request(url)
        last_error: BaseException | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=timeout) as resp:
                    output.write_bytes(resp.read())
                return
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt == 2:
                    raise RuntimeError(f"Network error while downloading image: {exc}") from exc
                last_error = exc
                time.sleep(retry_delay(attempt))
        raise RuntimeError(f"Image download failed after retries: {last_error}")
    raise RuntimeError("image response did not include b64_json or url")


def _normalize_label(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def selected_reference_paths(
    analysis: dict[str, Any],
    frames: list[dict[str, str]],
    logos: list[dict[str, str]],
) -> list[Path]:
    selected: list[Path] = []

    def match(label: str) -> Path | None:
        target = _normalize_label(label)
        if not target:
            return None
        for item in frames:
            if _normalize_label(item["label"]) == target:
                return Path(item["path"])
        return None

    requested = (analysis.get("selected_frame", {}) or {}).get("label", "")
    chosen = match(requested)

    if chosen is None:
        for backup in analysis.get("backup_frames", []) or []:
            if isinstance(backup, dict):
                chosen = match(backup.get("label", ""))
                if chosen is not None:
                    break

    if chosen is None and frames:
        # Defensive guard for a malformed model label: every candidate is already a
        # prefiltered, technically-clean frame, so the first one is a safe pick.
        fallback = frames[0]
        chosen = Path(fallback["path"])
        print(
            f"Warning: selected_frame label '{requested}' did not match any extracted "
            f"frame; falling back to '{fallback['label']}'.",
            file=sys.stderr,
        )

    if chosen is not None:
        selected.append(chosen)
    selected.extend(Path(item["path"]) for item in logos)
    return selected


def generate_images(
    args: argparse.Namespace,
    api_key: str,
    work_dir: Path,
    base_dir: Path,
    stem: str,
    analysis: dict[str, Any],
    refs: list[Path],
    sidecars: dict[str, Path],
) -> dict[str, str]:
    results: dict[str, str] = {}
    prompts = analysis.get("prompts", {})

    jobs = []
    for key in requested_aspects(args):
        item = prompts.get(key, {})
        prompt = item.get("prompt", "").strip()
        size = aspect_size(args, key)
        if not prompt:
            print(f"Skip {key}: empty prompt")
            continue
        jobs.append((key, prompt, size))

    if not jobs:
        return results

    def generate_one(key: str, prompt: str, size: str) -> tuple[str, str]:
        print(f"Generating {key} cover via {args.image_model} at {size}...")

        output = base_dir / f"{stem}_{key}.png"
        if args.generation_only or not refs:
            payload = {
                "model": args.image_model,
                "prompt": prompt,
                "n": 1,
                "size": size,
            }
            response = post_json(
                f"{args.api_base.rstrip('/')}/images/generations",
                payload,
                api_key,
                args.timeout,
            )
        else:
            fields = {
                "model": args.image_model,
                "prompt": prompt,
                "n": "1",
                "size": size,
            }
            files = [("image[]", path) for path in refs]
            response = post_multipart(
                f"{args.api_base.rstrip('/')}/images/edits",
                fields,
                files,
                api_key,
                args.timeout,
            )

        raw_path = work_dir / f"{key}.response.json"
        raw_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
        save_image_response(response, output, args.timeout)

        sidecars[key].write_text(
            prompt_sidecar_text(key, size, prompt, analysis, refs, str(output), "GENERATED"),
            encoding="utf-8",
        )
        return key, str(output)

    failures: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as executor:
        future_map = {executor.submit(generate_one, *job): job[0] for job in jobs}
        for future in concurrent.futures.as_completed(future_map):
            key = future_map[future]
            try:
                result_key, path = future.result()
                results[result_key] = path
            except Exception as exc:
                sidecars[key].write_text(
                    prompt_sidecar_text(
                        key,
                        aspect_size(args, key),
                        prompts.get(key, {}).get("prompt", ""),
                        analysis,
                        refs,
                        "FAILED",
                        f"FAILED: {exc}",
                    ),
                    encoding="utf-8",
                )
                print(f"Error: {key} generation failed: {exc}", file=sys.stderr)
                failures.append(key)

    # A single failed aspect must not discard the others that already succeeded.
    if failures and not results:
        raise RuntimeError(f"All image generations failed: {failures}")
    if failures:
        print(
            f"Warning: {len(failures)} aspect(s) failed ({failures}); delivered {list(results)}.",
            file=sys.stderr,
        )
    return results


def apply_creator_portrait_composites(
    args: argparse.Namespace,
    work_dir: Path,
    analysis: dict[str, Any],
    refs: list[Path],
    sidecars: dict[str, Path],
    results: dict[str, str],
    creator_portrait_overlay: dict[str, Any] | None,
) -> dict[str, Any]:
    if not args.default_creator_portrait or not results:
        return {}
    if not creator_portrait_overlay:
        raise RuntimeError("default creator portrait is enabled but no overlay asset was prepared")

    records: dict[str, Any] = {}
    overlay_path = Path(str(creator_portrait_overlay["path"]))
    prompts = analysis.get("prompts", {})
    for key, output_value in results.items():
        output_path = Path(output_value)
        base_path = work_dir / f"{key}.generated-base.png"
        shutil.copy2(output_path, base_path)
        record = composite_creator_portrait(base_path, output_path, overlay_path, key)
        records[key] = record

        prompt = str((prompts.get(key, {}) or {}).get("prompt", ""))
        size = aspect_size(args, key)
        sidecars[key].write_text(
            prompt_sidecar_text(
                key,
                size,
                prompt,
                analysis,
                refs,
                str(output_path),
                "GENERATED_AND_CODE_COMPOSITED",
                record,
            ),
            encoding="utf-8",
        )

    (work_dir / "portrait_composite.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return records


def main() -> None:
    args = parse_args()
    if args.composite_base:
        base_path = args.composite_base.expanduser().resolve()
        if not base_path.exists():
            fail(f"composite base image does not exist: {base_path}")
        configured_path = DEFAULT_CREATOR_PORTRAIT_OVERLAY.get("path")
        if not configured_path:
            fail(
                "creator portrait compositing requires creator_portrait.path "
                f"in {USER_CONFIG_FILE}"
            )
        overlay_path = Path(configured_path)
        if not overlay_path.exists():
            fail(f"default creator portrait overlay is missing: {overlay_path}")
        aspect_key = args.composite_aspect or infer_creator_portrait_aspect(base_path)
        output_path = (
            args.composite_output.expanduser().resolve()
            if args.composite_output
            else base_path.with_name(f"{base_path.stem}_with_creator.png")
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        record = composite_creator_portrait(base_path, output_path, overlay_path, aspect_key)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return

    api_key = api_key_from_args(args)

    if args.video:
        stem = args.video.stem
    elif args.image:
        stem = slugify(args.title) if args.title.strip() else args.image[0].stem
    else:
        stem = "oil-cover"

    if args.output_root is not None:
        base_dir = args.output_root
    elif args.video:
        base_dir = args.video.parent
    elif args.image:
        base_dir = args.image[0].parent
    else:
        base_dir = Path.cwd()
    base_dir = base_dir.expanduser()

    work_dir = base_dir / f"{stem}.oil-cover"
    work_dir.mkdir(parents=True, exist_ok=True)

    skill_rules = read_text(args.rules_file)
    subtitle_text = read_text(args.subtitle, limit=20000)
    frames = extract_video_frames(args, work_dir) if args.video else copy_input_images(args, work_dir)
    logos = copy_logos(args, work_dir, subtitle_text)
    creator_portrait_overlay = prepare_creator_portrait_overlay(work_dir) if args.default_creator_portrait else None

    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "api_base": args.api_base,
        "analysis_model": args.analysis_model,
        "image_model": args.image_model,
        "video": str(args.video) if args.video else "",
        "images": [str(path) for path in args.image or []],
        "title": args.title,
        "topic": args.topic,
        "subtitle": str(args.subtitle) if args.subtitle else "",
        "frames": frames,
        "logos": logos,
        "creator_portrait_overlay": creator_portrait_overlay,
        "dry_run": args.dry_run,
        "skip_generate": args.skip_generate,
        "aspect": args.aspect,
        "allow_subtitle": args.allow_subtitle,
        "default_creator_portrait": args.default_creator_portrait,
    }
    (work_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    messages = build_analysis_messages(args, frames, logos, creator_portrait_overlay, skill_rules, subtitle_text)
    analysis = run_analysis(args, api_key, messages, work_dir)
    analysis = apply_script_guards(args, analysis, work_dir, logos)
    write_cover_plan(work_dir, analysis, frames, logos, creator_portrait_overlay)

    refs = selected_reference_paths(analysis, frames, logos)
    sidecars = save_prompt_sidecars(args, work_dir, analysis, refs)
    results: dict[str, str] = {}
    portrait_composites: dict[str, Any] = {}
    if not args.skip_generate and not args.dry_run:
        results = generate_images(args, api_key, work_dir, base_dir, stem, analysis, refs, sidecars)
        portrait_composites = apply_creator_portrait_composites(
            args,
            work_dir,
            analysis,
            refs,
            sidecars,
            results,
            creator_portrait_overlay,
        )

    final_manifest = {
        **manifest,
        "analysis_path": str(work_dir / "analysis.json"),
        "cover_plan_path": str(work_dir / "cover_plan.md"),
        "creator_portrait_overlay": creator_portrait_overlay,
        "portrait_composites": portrait_composites,
        "prompt_sidecars": {key: str(value) for key, value in sidecars.items()},
        "generated_images": results,
    }
    (work_dir / "manifest.final.json").write_text(
        json.dumps(final_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(final_manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        fail("interrupted")
