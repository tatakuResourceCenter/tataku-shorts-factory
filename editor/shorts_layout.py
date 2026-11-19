#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
랭킹 쇼츠 구성 렌더러.

구성.json 의 설정으로 1080x1920 세로 영상을 만든다.
  · 위 검정 띠 + 제목 2줄 + 작은 문구
  · 클립 5개를 순서대로 (기본 5위 → 1위)
  · 왼쪽 랭킹 숫자, 해당 클립이 나올 때 라벨이 붙고 끝까지 남음
  · 클립마다 출처를 오른쪽 아래에 작게

글자는 PIL 로 투명 PNG 를 그려 ffmpeg 로 얹는다 (drawtext 이스케이프 문제 회피).
"""

import re
import os
import json
import shutil
import tempfile
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920

DEFAULT_LAYOUT = {
    "title1": "지리게 말하는 고양이들",
    "title1Color": "#D9A6FF",
    "title2": "랭킹 TOP5",
    "title2Color": "#FFFFFF",
    "sub": "(몇번이 제일 잘 말함? ㅋㅋㅋ)",
    "subColor": "#FFFFFF",
    "bandHeight": 460,
    "ranking": True,
    "order": "5to1",
    "numColors": ["#FF3B3B", "#FF9F1C", "#FFE14D", "#FFFFFF", "#FFFFFF"],
    "keepAudio": True,
    "ref": "",
    "clips": [
        {"rank": r, "file": "", "label": "", "start": 0.0, "end": 0.0, "source": ""}
        for r in range(1, 6)
    ],
}

FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]


def find_font():
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def font(path, size):
    if path and path.endswith(".ttc"):
        return ImageFont.truetype(path, size, index=1)
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def fit_font(draw, text, fpath, start, maxw, stroke=0):
    s = start
    while s > 20:
        f = font(fpath, s)
        b = draw.textbbox((0, 0), text, font=f, stroke_width=stroke)
        if b[2] - b[0] <= maxw:
            return f
        s -= 2
    return font(fpath, 20)


def play_order(layout):
    """재생 순서 (클립 파일이 있는 것만)."""
    clips = {c["rank"]: c for c in layout["clips"] if c.get("file")}
    ranks = sorted(clips, reverse=(layout.get("order", "5to1") == "5to1"))
    return [clips[r] for r in ranks]


def rank_rows(layout):
    """랭킹 표시 위치: 숫자 1~N 을 위에서 아래로."""
    n = len(layout["clips"])
    top = layout["bandHeight"] + 70
    gap = 150
    return {r: top + (r - 1) * gap for r in range(1, n + 1)}


def draw_overlay(layout, revealed, current, fpath):
    """한 클립 동안 얹을 투명 오버레이. revealed = 라벨을 보여줄 순위 집합."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    band = int(layout["bandHeight"])

    d.rectangle([0, 0, W, band], fill=(0, 0, 0, 255))

    t1, t2, sub = layout.get("title1", ""), layout.get("title2", ""), layout.get("sub", "")
    f1 = fit_font(d, t1, fpath, 92, W - 100)
    f2 = fit_font(d, t2, fpath, 120, W - 100)
    fs = fit_font(d, sub, fpath, 44, W - 140)

    lines = [(t1, f1, layout.get("title1Color", "#FFFFFF")),
             (t2, f2, layout.get("title2Color", "#FFFFFF"))]
    if sub:
        lines.append((sub, fs, layout.get("subColor", "#FFFFFF")))
    heights = [d.textbbox((0, 0), t, font=f)[3] - d.textbbox((0, 0), t, font=f)[1] for t, f, _ in lines]
    gap = 26
    total = sum(heights) + gap * (len(lines) - 1)
    y = (band - total) // 2 + 10
    for (t, f, c), h in zip(lines, heights):
        if t:
            d.text((W // 2, y + h // 2), t, font=f, fill=hexc(c), anchor="mm")
        y += h + gap

    if layout.get("ranking", True):
        rows = rank_rows(layout)
        fn = font(fpath, 84)
        fl = font(fpath, 62)
        colors = layout.get("numColors", DEFAULT_LAYOUT["numColors"])
        for r, ry in rows.items():
            col = hexc(colors[r - 1] if r - 1 < len(colors) else "#FFFFFF")
            d.text((60, ry), f"{r}.", font=fn, fill=col,
                   stroke_width=6, stroke_fill=(0, 0, 0), anchor="lm")
            clip = next((c for c in layout["clips"] if c["rank"] == r), None)
            if clip and r in revealed and clip.get("label"):
                d.text((175, ry), clip["label"], font=fl, fill=col,
                       stroke_width=6, stroke_fill=(0, 0, 0), anchor="lm")

    if current and current.get("source"):
        fsrc = font(fpath, 32)
        d.text((W - 40, H - 60), current["source"], font=fsrc,
               fill=(255, 255, 255, 220), stroke_width=3, stroke_fill=(0, 0, 0), anchor="rm")
    return im


def ffmpeg_exe():
    """PC 에 깔린 ffmpeg, 없으면 pip 로 받은 imageio-ffmpeg 안의 ffmpeg."""
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


FF = ffmpeg_exe()


def probe(path):
    """(길이 초, 소리 있음?) — ffprobe 없이 ffmpeg 출력으로 읽는다."""
    r = subprocess.run([FF or "ffmpeg", "-hide_banner", "-i", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    return dur, bool(re.search(r"Stream #.*Audio:", r.stderr))


def has_audio(path):
    return probe(path)[1]


def ffmpeg_ok():
    return FF is not None


def render(layout, clips_dir, out_path, log=print):
    if not ffmpeg_ok():
        raise RuntimeError("ffmpeg 이 없습니다")
    fpath = find_font()
    seq = play_order(layout)
    if not seq:
        raise RuntimeError("파일이 지정된 클립이 없습니다")

    band = int(layout["bandHeight"])
    vh = H - band
    tmp = Path(tempfile.mkdtemp(prefix="shorts_"))
    parts = []
    revealed = set()
    keep = layout.get("keepAudio", True)

    for i, c in enumerate(seq, 1):
        src = Path(clips_dir) / c["file"]
        if not src.exists():
            raise RuntimeError(f"클립 파일이 없습니다: {c['file']}")
        revealed.add(c["rank"])
        ov = tmp / f"ov{i}.png"
        draw_overlay(layout, set(revealed), c, fpath).save(ov)

        start = float(c.get("start") or 0)
        end = float(c.get("end") or 0)
        cut = ["-ss", f"{start:.3f}"] + (["-to", f"{end:.3f}"] if end > start else [])
        part = tmp / f"p{i}.mp4"

        audio_in = keep and has_audio(src)
        cmd = [FF, "-y", "-v", "error"] + cut + ["-i", str(src), "-i", str(ov)]
        if not audio_in:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        fc = (f"color=c=black:s={W}x{H}:r=30[bg];"
              f"[0:v]scale={W}:{vh}:force_original_aspect_ratio=increase,"
              f"crop={W}:{vh},setsar=1,fps=30[v];"
              f"[bg][v]overlay=0:{band}:shortest=1[b];"
              f"[b][1:v]overlay=0:0,format=yuv420p[out]")
        cmd += ["-filter_complex", fc, "-map", "[out]"]
        cmd += ["-map", "0:a:0" if audio_in else "2:a:0", "-shortest"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", str(part)]
        log(f"  [{i}/{len(seq)}] {c['rank']}위 · {c['file']}")
        subprocess.run(cmd, check=True)
        parts.append(part)

    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    subprocess.run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(out_path)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"✅ 구성 영상 완성: {out_path}")
    return out_path


def total_length(layout):
    t = 0.0
    for c in play_order(layout):
        s, e = float(c.get("start") or 0), float(c.get("end") or 0)
        if e > s:
            t += e - s
    return round(t, 2)


if __name__ == "__main__":
    import sys
    lay = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    render(lay, sys.argv[2], sys.argv[3])
