# -*- coding: utf-8 -*-
"""
예능 편집기 — 긴 원본 하나를 잘게 잘라 예능 쇼츠로 만든다.

  · 빈 호흡 찾기 (silencedetect) → 남길 구간 후보
  · 후킹: 고른 구간을 맨 앞에 한 번 더 보여 준다
  · 얼빡: 구간마다 확대 · 좌우 위치
  · 자막 두 가지: 대사(흰 글씨) / 내레이션(형광 노랑, 아래 띠)
  · 내레이션이 나오는 동안 원본 소리는 끈다

화면: 1080×1920, 위 검정 띠(제목 2줄) · 가운데 영상 · 아래 검정 띠(내레이션 자막 · 출처)
"""
import re
import json
import uuid
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import shorts_layout as L

W, H = 1080, 1920
FPS = 30

DEFAULT_EDIT = {
    "source": "",                 # 예능/원본 안의 파일 이름
    "range": [0.0, 0.0],          # 작업할 원본 구간 (빈 호흡 찾기 범위)
    "title1": "", "title1Color": "#FFE14D",
    "title2": "", "title2Color": "#4FE3FF",
    "credit": "",                 # 예: 출처 - JTBC 아는 형님
    "rights": "",                 # 권리 확인 메모 (화이트리스트 / 허락 받음 등)
    "rightsOk": False,
    "videoTop": 330, "videoH": 1100,
    "segments": [],               # {id,start,end,keep,hook,zoom,x}
    "captions": [],               # 대사 자막 {id,t,dur,text}  t = 원본 기준 초
    "brief": "",
}

HERE = Path(__file__).resolve().parent
FONT_DIR = HERE / "web" / "fonts"
TITLE_FONTS = [FONT_DIR / "BlackHanSans-Regular.ttf"] + [Path(p) for p in L.FONT_CANDIDATES]
BODY_FONTS = [Path("C:/Windows/Fonts/malgunbd.ttf"), FONT_DIR / "BlackHanSans-Regular.ttf"] + \
             [Path(p) for p in L.FONT_CANDIDATES]


def _font(cands, size):
    for p in cands:
        try:
            if Path(p).exists():
                if str(p).endswith(".ttc"):
                    return ImageFont.truetype(str(p), size, index=1)
                return ImageFont.truetype(str(p), size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fit(d, text, cands, size, maxw, minsize=28):
    while size > minsize:
        f = _font(cands, size)
        if d.textlength(text, font=f) <= maxw:
            return f
        size -= 4
    return _font(cands, minsize)


def new_id(prefix="s"):
    return prefix + uuid.uuid4().hex[:5]


def normalize(edit):
    e = json.loads(json.dumps(DEFAULT_EDIT))
    e.update(edit or {})
    for s in e["segments"]:
        s.setdefault("id", new_id())
        s.setdefault("keep", True)
        s.setdefault("hook", False)
        s.setdefault("zoom", 1.0)
        s.setdefault("x", 0.5)
    for c in e["captions"]:
        c.setdefault("id", new_id("c"))
        c.setdefault("dur", 1.5)
    e["segments"].sort(key=lambda s: float(s["start"]))
    return e


# ── 구간 → 완성 영상 순서 ─────────────────────────────────
def pieces(edit):
    """완성 영상에 실제로 나오는 조각들. 후킹 구간이 맨 앞에 먼저 나오고, 그다음 남긴 구간이 원본 순서대로."""
    segs = [s for s in edit["segments"] if float(s["end"]) > float(s["start"])]
    hooks = [s for s in segs if s.get("hook")]
    body = [s for s in segs if s.get("keep", True)]
    out, t = [], 0.0
    for s, is_hook in [(s, True) for s in hooks] + [(s, False) for s in body]:
        d = float(s["end"]) - float(s["start"])
        out.append({"seg": s["id"], "start": float(s["start"]), "end": float(s["end"]),
                    "out_start": round(t, 3), "out_end": round(t + d, 3), "hook": is_hook,
                    "zoom": float(s.get("zoom", 1.0)), "x": float(s.get("x", 0.5))})
        t += d
    return out


def total_length(edit):
    p = pieces(edit)
    return p[-1]["out_end"] if p else 0.0


def seg_times(edit):
    """대본 편집에서 '클립' 칸으로 쓰는 목록: 남긴 구간(본편) 기준. 후킹 앞부분은 빼고."""
    out, n = [], 0
    for p in pieces(edit):
        if p["hook"]:
            continue
        n += 1
        out.append({"rank": p["seg"], "start": p["out_start"], "end": p["out_end"],
                    "label": f"구간 {n} · 원본 {fmt(p['start'])}", "no": n})
    return out


def fmt(sec):
    sec = max(0, float(sec))
    return f"{int(sec // 60)}:{sec % 60:04.1f}"


# ── 빈 호흡 찾기 ─────────────────────────────────────────
def find_speech(src, a, b, noise_db=-32, min_sil=0.35, pad=0.08, min_len=0.35):
    """원본 a~b 초에서 조용한 곳을 찾아, 말소리가 있는 구간 목록을 돌려준다."""
    cmd = [L.FF or "ffmpeg", "-hide_banner", "-nostats", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(src),
           "-vn", "-af", f"silencedetect=noise={noise_db}dB:d={min_sil}", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sil, cur = [], None
    for line in r.stderr.splitlines():
        m = re.search(r"silence_start:\s*([\d.]+)", line)
        if m:
            cur = float(m.group(1))
        m = re.search(r"silence_end:\s*([\d.]+)", line)
        if m and cur is not None:
            sil.append((cur, float(m.group(1))))
            cur = None
    if cur is not None:
        sil.append((cur, b - a))
    speech, t = [], 0.0
    for s0, s1 in sil:
        if s0 - t > 0:
            speech.append((t, s0))
        t = s1
    if (b - a) - t > 0:
        speech.append((t, b - a))
    segs = []
    for s0, s1 in speech:
        s0, s1 = max(0.0, s0 - pad), min(b - a, s1 + pad)
        if s1 - s0 >= min_len:
            segs.append({"id": new_id(), "start": round(a + s0, 2), "end": round(a + s1, 2),
                         "keep": True, "hook": False, "zoom": 1.0, "x": 0.5})
    return segs, len(sil)


# ── 그림 (띠 · 자막) ─────────────────────────────────────
def _rgb(h):
    h = (h or "#FFFFFF").lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def band_png(edit, path):
    top, vh = int(edit["videoTop"]), int(edit["videoH"])
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, top], fill=(0, 0, 0, 255))
    d.rectangle([0, top + vh, W, H], fill=(0, 0, 0, 255))
    lines = [(edit.get("title1", ""), edit.get("title1Color")), (edit.get("title2", ""), edit.get("title2Color"))]
    lines = [(t.strip(), c) for t, c in lines if t and t.strip()]
    if lines:
        size = 112 if len(lines) == 2 else 128
        fonts = [_fit(d, t, TITLE_FONTS, size, W - 70) for t, _ in lines]
        hs = [f.size for f in fonts]
        gap = 14
        y = (top - (sum(hs) + gap * (len(lines) - 1))) // 2
        for (t, c), f in zip(lines, fonts):
            d.text((W // 2, y), t, font=f, fill=_rgb(c), anchor="mt", stroke_width=5, stroke_fill=(0, 0, 0))
            y += f.size + gap
    if edit.get("credit"):
        f = _font(BODY_FONTS, 30)
        d.text((W - 36, H - 46), edit["credit"], font=f, fill=(150, 150, 150), anchor="rs")
    im.save(path)


def caption_png(text, kind, path, scale=1.0):
    """kind: dialog (흰 글씨, 영상 아래쪽) / narr (형광 노랑, 아래 띠) / hook (빨강, 크게)"""
    im = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if kind == "narr":
        size, fill, cands, stroke = 76, (240, 255, 0), TITLE_FONTS, 7
    elif kind == "hook":
        size, fill, cands, stroke = 84, (255, 59, 48), TITLE_FONTS, 8
    else:
        size, fill, cands, stroke = 64, (255, 255, 255), BODY_FONTS, 7
    size = int(size * scale)
    f = _fit(d, text, cands, size, int((W - 80) * scale), 30)
    # 그림자
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((W // 2 + 5, 135), text, font=f, fill=(0, 0, 0, 170), anchor="mm",
                            stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
    im.alpha_composite(sh)
    d.text((W // 2, 130), text, font=f, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=(0, 0, 0))
    im.save(path)


# ── 자막 타이밍 ──────────────────────────────────────────
def caption_events(edit, narr_lines):
    """완성 영상 기준 (시작, 끝, 글, 종류) 목록."""
    ev = []
    ps = pieces(edit)
    for c in edit["captions"]:
        t, dur, text = float(c["t"]), float(c.get("dur", 1.5)), (c.get("text") or "").strip()
        if not text:
            continue
        for p in ps:
            if p["start"] <= t < p["end"]:
                a = p["out_start"] + (t - p["start"])
                b = min(a + dur, p["out_end"])
                ev.append((round(a, 3), round(b, 3), text, "hook" if p["hook"] else "dialog"))
    for ln in narr_lines:
        if ln.get("start") is None or not ln.get("duration") or not (ln.get("text") or "").strip():
            continue
        a = float(ln["start"])
        ev.append((round(a, 3), round(a + float(ln["duration"]) + 0.15, 3), ln["text"].strip(), "narr"))
    return sorted(ev)


# ── 렌더 ────────────────────────────────────────────────
def render(edit, src, out_path, narr_lines, work, log=print):
    """구간 이어붙이기 → 띠 · 자막 얹기. 소리는 원본 그대로 (내레이션 합성은 mux 에서)."""
    FF = L.FF or "ffmpeg"
    ps = pieces(edit)
    if not ps:
        raise RuntimeError("남길 구간이 없어요. 컷 편집에서 구간을 먼저 정해 주세요")
    work = Path(work)
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    top, vh = int(edit["videoTop"]), int(edit["videoH"])
    has_a = L.has_audio(src)
    parts = []
    for i, p in enumerate(ps, 1):
        z, x = max(1.0, p["zoom"]), min(1.0, max(0.0, p["x"]))
        # 영상 칸(1080×vh)을 꽉 채우도록 키운 뒤 확대, 좌우 위치에 맞춰 자르기
        vf = (f"scale=w='ceil(max({W}/iw\\,{vh}/ih)*iw*{z}/2)*2':h='ceil(max({W}/iw\\,{vh}/ih)*ih*{z}/2)*2',"
              f"crop={W}:{vh}:x='(iw-{W})*{x:.3f}':y='(ih-{vh})/2',"
              f"pad={W}:{H}:0:{top}:black,fps={FPS},setsar=1,format=yuv420p")
        out = work / f"p{i:03d}.mp4"
        cmd = [FF, "-y", "-v", "error", "-ss", f"{p['start']:.3f}", "-to", f"{p['end']:.3f}", "-i", str(src)]
        if not has_a:
            cmd += ["-f", "lavfi", "-t", f"{p['end'] - p['start']:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
        cmd += ["-vf", vf, "-map", "0:v:0", "-map", "0:a:0" if has_a else "1:a:0",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest", str(out)]
        subprocess.run(cmd, check=True)
        parts.append(out)
        log(f"  ✂️ 조각 {i}/{len(ps)}{' (후킹)' if p['hook'] else ''}")
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    body = work / "body.mp4"
    subprocess.run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(body)],
                   check=True, cwd=str(work))
    total = total_length(edit)

    # 띠 + 자막 그림 얹기
    band = work / "band.png"
    band_png(edit, band)
    inputs = ["-i", str(body), "-loop", "1", "-t", f"{total:.3f}", "-i", str(band)]
    fl = ["[0:v][1:v]overlay=0:0:shortest=1[v0]"]
    cur, k = "v0", 2
    cap_y = {"dialog": top + vh - 230, "hook": top + vh - 250, "narr": top + vh + 40}
    for n, (a, b, text, kind) in enumerate(caption_events(edit, narr_lines)):
        big, small = work / f"c{n}.png", work / f"c{n}s.png"
        caption_png(text, kind, big)
        caption_png(text, kind, small, scale=0.86)
        y = cap_y[kind]
        pop = min(b, a + 0.1)          # 처음 0.1초는 작게 → 뿅
        inputs += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(small),
                   "-loop", "1", "-t", f"{total:.3f}", "-i", str(big)]
        xs = "8*sin(2*PI*t*11)" if kind == "hook" else "0"
        fl.append(f"[{cur}][{k}:v]overlay=x={xs}:y={y}:enable='between(t,{a:.3f},{pop:.3f})'[v{k}]")
        fl.append(f"[v{k}][{k + 1}:v]overlay=x={xs}:y={y}:enable='between(t,{pop:.3f},{b:.3f})'[v{k + 1}]")
        cur, k = f"v{k + 1}", k + 2
    cmd = [FF, "-y", "-v", "error"] + inputs + ["-filter_complex", ";".join(fl), "-map", f"[{cur}]", "-map", "0:a",
                                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                                                "-pix_fmt", "yuv420p", "-c:a", "copy", "-t", f"{total:.3f}",
                                                str(out_path)]
    subprocess.run(cmd, check=True)
    log(f"✅ 예능 편집 영상 완성: {Path(out_path).name} ({total:.1f}초)")
    return total
