#!/usr/bin/env python3
"""
Generate oil-cover Xiaohongshu covers with Zenmux.

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

    Prefer the Claude skill, fall back to the Codex copy, so the script keeps
    working across machines/users. Override with OIL_COVER_SKILL_DIR if needed.
    """
    override = os.environ.get("OIL_COVER_SKILL_DIR", "").strip()
    candidates = [Path(override)] if override else []
    candidates += [
        Path.home() / ".claude" / "skills" / "oil-cover",
        Path.home() / ".codex" / "skills" / "oil-cover",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


SKILL_DIR = _resolve_skill_dir()
DEFAULT_RULES_FILE = SKILL_DIR / "references" / "cover-rules.md"
DEFAULT_API_BASE = "https://zenmux.ai/api/v1"
DEFAULT_ANALYSIS_MODEL = "google/gemini-3.5-flash"
DEFAULT_IMAGE_MODEL = "openai/gpt-image-2"
DEFAULT_API_KEY_FILE = Path(__file__).resolve().parent.parent / ".zenmux_api_key"
PRODUCT_LOGO_DIR = SKILL_DIR / "assets" / "product-logos"
RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}
AUTO_PRODUCT_LOGOS = [
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
        help="Optional local file containing the Zenmux API key. Default: .zenmux_api_key",
    )
    parser.add_argument("--frame-count", type=int, default=12, help="Candidate frames for video input. More candidates give the model better frame choices.")
    parser.add_argument(
        "--candidate-seconds",
        default="",
        help="Comma-separated timestamps to extract from the video, for example 1,8,24.5. Overrides automatic frame selection.",
    )
    parser.add_argument(
        "--frame-select",
        choices=("video", "sample"),
        default="video",
        help="How to pick evidence frames for video input. 'video' (default) sends a compressed clip to the analysis model and lets it watch the whole video and choose the best timestamp(s); 'sample' falls back to blind uniform sampling. Ignored when --candidate-seconds is set.",
    )
    parser.add_argument("--select-fps", type=float, default=1.0, help="Frames-per-second when compressing the clip sent for video timestamp selection.")
    parser.add_argument("--select-width", type=int, default=512, help="Scaled width of the compressed clip sent for video timestamp selection.")
    parser.add_argument("--select-count", type=int, default=1, help="How many candidate timestamps the model returns in 'video' frame-select mode (best first). Default 1: trust the single best moment it picks from the whole video.")
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
        "--generation-only",
        action="store_true",
        help="Use /images/generations instead of /images/edits, so reference images are not uploaded to the image API.",
    )
    parser.add_argument(
        "--aspect",
        choices=("both", "3x4", "4x3"),
        default="both",
        help="Which cover aspect to generate. Analysis still prepares both prompts.",
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


def candidate_times(args: argparse.Namespace, duration: float) -> list[float]:
    if args.candidate_seconds.strip():
        values = []
        for raw in args.candidate_seconds.split(","):
            raw = raw.strip()
            if raw:
                values.append(max(0.0, min(float(raw), duration)))
        return unique_times(values)

    count = max(2, args.frame_count)
    start = min(0.2, duration * 0.02)
    if count == 2:
        return unique_times([start, duration * 0.55])
    values = [start]
    for idx in range(count - 1):
        ratio = 0.12 + (0.80 * idx / max(count - 2, 1))
        values.append(duration * ratio)
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


def extract_video_frames(
    args: argparse.Namespace, run_dir: Path, api_key: str = ""
) -> list[dict[str, str]]:
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

    first = frames_dir / "first_frame.jpg"
    extract_frame(video, 0.0, first, args.max_frame_width)
    frames.append({"label": "first_frame", "path": str(first), "timestamp": "0.00"})

    for idx, timestamp in enumerate(resolve_candidate_timestamps(args, api_key, run_dir, duration), start=1):
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


def compress_for_selection(args: argparse.Namespace, run_dir: Path) -> Path:
    """Down-sample the video to a small low-fps clip for whole-video timestamp selection."""
    clip = run_dir / "select_clip.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(args.video),
            "-vf",
            f"fps={args.select_fps},scale={args.select_width}:-2",
            "-c:v",
            "libx264",
            "-crf",
            "30",
            "-preset",
            "veryfast",
            "-an",
            str(clip),
        ]
    )
    return clip


def select_timestamps_via_video(
    args: argparse.Namespace, api_key: str, run_dir: Path, duration: float
) -> list[float]:
    """Send a compressed clip of the whole video to the analysis model and let it choose the
    best cover-frame timestamp(s). Returns timestamps in seconds, best first."""
    clip = compress_for_selection(args, run_dir)
    data_url = f"data:video/mp4;base64,{base64.b64encode(clip.read_bytes()).decode()}"
    want = max(1, args.select_count)
    pick_clause = (
        "choose the single best moment"
        if want == 1
        else f"choose up to {want} candidate moments, best first,"
    )
    subject_hint = " / ".join(part for part in [args.title.strip(), args.topic.strip()] if part)
    subject_line = (
        f"The video's subject, use this to anchor your choice: {subject_hint}. "
        if subject_hint
        else ""
    )
    instruction = (
        f"This is a roughly {duration:.0f}s screen-recording tutorial for an AI tool. "
        f"{subject_line}"
        f"Watch the whole video and {pick_clause} that would make the strongest Xiaohongshu cover. "
        "The frame must let a viewer recognize WHICH tool or product the video is about: prefer a moment that "
        "clearly shows the main tool/product named in the subject actually in use (its real interface, panel, "
        "or workflow), not merely the prettiest end-result or generated output that any tool could have produced "
        "and that hides the subject. Favor a clean, information-rich screen tied to the subject. Avoid "
        "transitions, loading or empty/placeholder states, blurry frames, pure title/intro cards, and "
        "webcam/face-only shots. "
        'Return strict JSON: {"candidates": [{"timestamp_seconds": <number>, "reason": "<short>"}]}.'
    )
    messages = [
        {"role": "system", "content": "You are a precise video cover-frame selector. Return strict JSON only."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": instruction},
                {"type": "video_url", "video_url": {"url": data_url}},
            ],
        },
    ]
    payload = {
        "model": args.analysis_model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    select_timeout = max(args.timeout, 300)
    data: dict[str, Any] | None = None
    last_error: Exception | None = None
    for attempt in range(3):
        response = post_json(
            f"{args.api_base.rstrip('/')}/chat/completions", payload, api_key, select_timeout
        )
        try:
            data = extract_json_from_text(response["choices"][0]["message"]["content"])
            break
        except RuntimeError as exc:
            last_error = exc
            print(f"Frame-selection JSON parse failed (attempt {attempt + 1}/3): {exc}", file=sys.stderr)
    if data is None:
        raise RuntimeError(f"video frame selection did not return valid JSON: {last_error}")
    (run_dir / "frame_selection.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    times: list[float] = []
    seen: set[int] = set()
    for item in data.get("candidates") or []:
        if not isinstance(item, dict):
            continue
        try:
            ts = float(item.get("timestamp_seconds"))
        except (TypeError, ValueError):
            continue
        ts = max(0.0, min(ts, max(duration - 0.05, 0.0)))
        marker = int(round(ts * 10))
        if marker in seen:
            continue
        seen.add(marker)
        times.append(round(ts, 2))
        if len(times) >= want:
            break
    if not times:
        raise RuntimeError("video frame selection returned no usable timestamps")
    return times


def resolve_candidate_timestamps(
    args: argparse.Namespace, api_key: str, run_dir: Path, duration: float
) -> list[float]:
    """Decide which timestamps to extract as candidate evidence frames."""
    if args.candidate_seconds.strip():
        return candidate_times(args, duration)
    if args.frame_select == "video" and not args.dry_run and api_key:
        try:
            picks = select_timestamps_via_video(args, api_key, run_dir, duration)
            if picks:
                print(
                    "Frame selection (video): " + ", ".join(f"{t:.2f}s" for t in picks),
                    file=sys.stderr,
                )
                return picks
        except Exception as exc:
            print(
                f"Video frame selection failed, falling back to uniform sampling: {exc}",
                file=sys.stderr,
            )
    return candidate_times(args, duration)


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


def image_to_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def build_analysis_messages(
    args: argparse.Namespace,
    frames: list[dict[str, str]],
    logos: list[dict[str, str]],
    skill_rules: str,
    subtitle_text: str,
) -> list[dict[str, Any]]:
    frame_list = "\n".join(
        f"- {item['label']}: {item['path']} timestamp={item.get('timestamp', '')}" for item in frames
    )
    logo_list = "\n".join(f"- {item['label']}: {item['path']}" for item in logos) or "None"
    subtitle_instruction = (
        "A short external subtitle is allowed when it strengthens the cover; keep it clearly smaller "
        "than the main title and aligned on the same editorial grid."
        if args.allow_subtitle
        else "Do not add an external subtitle; keep the outside cover text limited to the main title and the small product mark."
    )
    system_text = (
        "You are an expert cover art director for Xiaohongshu AI tool tutorial videos. "
        "Use the supplied oil-cover skill rules as the design spec. "
        "Treat supplied screenshots as evidence sources, not as full images to copy. "
        "Before writing prompts, decide the one-glance subject: what result should be visible "
        "within 0.5 seconds in a phone feed. Make that subject the dominant visual evidence, "
        "and make every other UI element serve or yield to it. "
        "Extract the few UI signals that explain the topic, rebuild them into a clean cover-ready screen, "
        "and remove irrelevant navigation, long transcripts, old subtitles, avatars, paths, timestamps, and tiny noisy text. "
        "The final image generator is Zenmux openai/gpt-image-2. The local script only extracts frames, "
        "copies files, saves prompts, and calls Zenmux APIs; it never composes, crops, adds text, pastes "
        "logos, or repairs the cover locally. The image model receives the selected frame, and the product "
        "logo if any, as edit references. "
        "IMPORTANT: each prompt you write IS the final and complete instruction sent to the image model; "
        "no extra rules are appended afterwards. So make every prompt fully self-contained and internally "
        "consistent. State the screenshot distillation, the visual-communication priority, the screen crop, "
        "the layout, the text styling, and a short avoid list ONCE each, in plain language. Do not repeat the "
        "same instruction in different words, do not give conflicting numbers or directions, and never rely "
        "on post-processing to fix the prompt. Prefer a tight, unambiguous prompt over a long padded one. "
        "Visual quality bar, fold these naturally into the one prompt without padding: "
        "(1) name the actual sampled hues for the background glow and the title accent, for example warm "
        "orange, cool blue, or lime green, instead of vaguely saying 'sampled from the image'; "
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
        "extreme skew, fisheye, warping, or heavy rotation. "
        "Return strict JSON only."
    )
    user_text = f"""
Task:
Create a complete external Zenmux workflow plan for an oil-cover style Xiaohongshu cover.

Known title:
{args.title or "None"}

Extra topic/context:
{args.topic or "None"}

Candidate frames:
{frame_list}

Logo/reference images:
{logo_list}

Subtitle/transcript/script excerpt:
{subtitle_text or "None"}

Oil-cover skill rules:
{skill_rules}

Output strict JSON with this schema:
{{
  "task_type": "video_cover or image_cover",
  "first_frame_judgement": {{
    "type": "real_interface/result_page/title_card/intro/plain_text/existing_cover/unknown",
    "usable_as_main_visual": true,
    "reason": ""
  }},
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
    }}
  }},
  "quality_checklist": []
}}

Important:
- Choosing selected_frame is the single biggest quality lever. Prefer a sharp, well-composed frame where the key UI, result, or action is fully visible, clean, and large. Reject blurry or motion-blurred frames, fade/transition frames, near-empty intros, loading states, frames that are mostly plain text, and frames where the main evidence is occluded, cropped, or tiny. If several frames are similar, pick the cleanest and most readable; list the next best ones in backup_frames.
- The two prompts must explicitly mention exact 3:4 and exact 4:3 respectively.
- The prompts must include the mandatory visible background sentence from the rules.
- The prompts must tell gpt-image-2 to create one complete final cover in one image.
- The prompts must preserve real tutorial evidence from the selected frame and remove people/webcam/avatar/subtitles.
- The prompts must not copy the selected screenshot as-is. They must specify a screenshot distillation plan: keep only 2-3 essential UI signals, remove noisy sidebars/long text/unrelated details, and rebuild the screen area as a clean real-feeling UI.
- The prompts must include a visual communication plan: the one-glance subject, the primary evidence, the maximum size of supporting evidence, and what to delete/crop if the primary evidence becomes too small.
- If the primary evidence is a row/grid/gallery/list of result cards, cover thumbnails, generated images, or comparison examples, the prompts must make those results large and readable as the dominant gallery. Do not shrink them into a faithful full-workspace screenshot.
- The prompts must include a title decoration plan: the title area cannot be plain text only. Add 1-2 tasteful, content-related title accents such as a subtle keyword highlight, thin underline, small workflow label, cursor mark, bracket, or UI state chip derived from the current title, screenshot, subtitle, topic, or product identity.
- The prompts must not ask for local post-processing.
- {subtitle_instruction}
- For the 4:3 horizontal prompt, the main title must be the first visual anchor, while the selected screen evidence remains large and readable.
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
    if args.aspect == "both":
        return ("3x4", "4x3")
    return (args.aspect,)


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
    aspect_phrase = "3:4" if aspect_key == "3x4" else "4:3"

    if aspect_phrase not in prompt:
        prompt += f" Output exactly one complete {aspect_phrase} cover in a single image."
        notes.append(f"{aspect_key}: backfilled exact aspect.")

    if "grid" not in low or "background" not in low:
        prompt += (
            " Mandatory visible background: full-canvas clean base, visible fine grid, restrained "
            "low-opacity local gradient glow sampled from the selected image, very light grain."
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
            prompt += f" Colour sampling: draw the background glow from specific hues — {detail}{tail}."
            notes.append(f"{aspect_key}: backfilled specific colour sampling.")
        else:
            prompt += (
                " Colour sampling: name and use the actual dominant hues of the selected screen for the "
                "background glow and title accent, not a flat gray wash."
            )
            notes.append(f"{aspect_key}: backfilled colour-hue instruction.")

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

    if "person" not in low and "avatar" not in low and "webcam" not in low and "face" not in low:
        prompt += (
            " Remove every human face, portrait, avatar, and webcam bubble, including inside rebuilt "
            "UI cards and thumbnails; keep the cover people-free."
        )
        notes.append(f"{aspect_key}: backfilled no-person rule.")

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
    We only enforce non-negotiables (exact aspect, mandatory background, no
    people, real logo) when the prompt omitted them, keeping it tight and
    self-consistent.
    """
    if not isinstance(analysis, dict):
        return analysis
    logos = logos or []

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


def write_cover_plan(run_dir: Path, analysis: dict[str, Any], frames: list[dict[str, str]], logos: list[dict[str, str]]) -> None:
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
) -> str:
    selected = analysis.get("selected_frame", {})
    return f"""# Oil Cover Prompt Sidecar

Use: Xiaohongshu oil-cover external Zenmux test
Aspect: {aspect_key}
Size: {size}
Selected frame: {selected.get("label", "")} {selected.get("path", "")}
Reference images:
{chr(10).join(f"- {path}" for path in refs) if refs else "- None"}

Generation result: {result_path}
Status: {status}

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
        size = args.portrait_size if key == "3x4" else args.landscape_size
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


def selected_reference_paths(analysis: dict[str, Any], frames: list[dict[str, str]], logos: list[dict[str, str]]) -> list[Path]:
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
        # Do not silently fall back to first_frame (often a title/intro card).
        non_first = [it for it in frames if it.get("label") != "first_frame"]
        fallback = non_first[0] if non_first else frames[0]
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
        size = args.portrait_size if key == "3x4" else args.landscape_size
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
                        args.portrait_size if key == "3x4" else args.landscape_size,
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

    # A single failed aspect must not discard the other one that already succeeded.
    if failures and not results:
        raise RuntimeError(f"All image generations failed: {failures}")
    if failures:
        print(
            f"Warning: {len(failures)} aspect(s) failed ({failures}); delivered {list(results)}.",
            file=sys.stderr,
        )
    return results


def main() -> None:
    args = parse_args()
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
    frames = extract_video_frames(args, work_dir, api_key) if args.video else copy_input_images(args, work_dir)
    logos = copy_logos(args, work_dir, subtitle_text)

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
        "dry_run": args.dry_run,
        "skip_generate": args.skip_generate,
        "aspect": args.aspect,
        "allow_subtitle": args.allow_subtitle,
    }
    (work_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    messages = build_analysis_messages(args, frames, logos, skill_rules, subtitle_text)
    analysis = run_analysis(args, api_key, messages, work_dir)
    analysis = apply_script_guards(args, analysis, work_dir, logos)
    write_cover_plan(work_dir, analysis, frames, logos)

    refs = selected_reference_paths(analysis, frames, logos)
    sidecars = save_prompt_sidecars(args, work_dir, analysis, refs)
    results: dict[str, str] = {}
    if not args.skip_generate and not args.dry_run:
        results = generate_images(args, api_key, work_dir, base_dir, stem, analysis, refs, sidecars)

    final_manifest = {
        **manifest,
        "analysis_path": str(work_dir / "analysis.json"),
        "cover_plan_path": str(work_dir / "cover_plan.md"),
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
