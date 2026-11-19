#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
쇼츠 공방 편집기 — 내 컴퓨터에서만 도는 작은 웹 서버.

  python editor_server.py        → http://127.0.0.1:8765 이 브라우저에 열린다

음성 엔진은 shorts_tts.py, 구성 렌더러는 shorts_layout.py 를 쓴다.
API 키는 같은 폴더의 apikey.txt 에서 읽는다.
"""

import os
import sys
import json
import shutil
import threading
import subprocess
import webbrowser
import mimetypes
import urllib.parse
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

BASE = Path(__file__).resolve().parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))

import shorts_tts as engine          # noqa: E402
import shorts_layout as layout_mod   # noqa: E402
import variety                       # noqa: E402

PORT = 8765
VERSION = "2026.11.20-1"
WEB = BASE / "web"
CLIPS = BASE / "clips"
REFS = BASE / "refs"
RANK = BASE / "랭킹"                  # 랭킹 편집기 작업 칸
VAR = BASE / "예능"                   # 예능 편집기 작업 칸
OUT = RANK / "output"
SCRIPT_FILE = RANK / "대본.json"
LAYOUT_FILE = RANK / "구성.json"
VAR_EDIT = VAR / "편집.json"
VAR_SRC = VAR / "원본"
VAR_OUT = VAR / "output"


def migrate_layout():
    """예전(한 폴더) 구조였다면 랭킹 작업을 랭킹/ 으로 옮긴다. 옮기기 전에 설정 파일은 백업."""
    old = [BASE / n for n in ("구성.json", "대본.json", "업로드정보.json", "타임라인.json", "자막.srt")]
    if not (BASE / "구성.json").exists() or (RANK / "구성.json").exists():
        return
    import time as _t
    bak = BASE / "보관함" / f"_구조변경_백업_{_t.strftime('%y%m%d_%H%M')}"
    bak.mkdir(parents=True, exist_ok=True)
    RANK.mkdir(exist_ok=True)
    for f in old:
        if f.exists():
            shutil.copy2(f, bak / f.name)
            shutil.move(str(f), str(RANK / f.name))
    for name in ("output", "voice"):
        src, dst = BASE / name, RANK / name
        if src.is_dir():
            dst.mkdir(exist_ok=True)
            for x in list(src.iterdir()):
                shutil.move(str(x), str(dst / x.name))
            try:
                src.rmdir()
            except OSError:
                pass
    print(f"🗂 랭킹 작업을 랭킹/ 폴더로 옮겼어요 (설정 백업: 보관함/{bak.name})", flush=True)


migrate_layout()
engine.OUTDIR = RANK / "voice"
for p in (CLIPS, REFS, RANK, OUT, engine.OUTDIR, VAR, VAR_SRC, VAR_OUT, VAR / "voice"):
    p.mkdir(parents=True, exist_ok=True)

engine.VOICES.setdefault("vnarr", "")
engine.LABEL["vnarr"] = "예능 내레이터"
engine.VOICE_QUERIES["vnarr"] = "재치 있고 빠른 템포의 한국어 예능 내레이션, 유튜브 쇼츠 해설용"
ROLES = ("narr", "cat", "vnarr")

DEFAULT_SCRIPT = []
SCRIPT_KEYS = ("speaker", "text", "emotion", "intensity", "speed", "pitch", "slot")

STATE = {"connected": False, "credits": None, "error": None, "busy": None, "log": []}
LOCK = threading.Lock()
CLIENT = None

import sources as src_mod            # noqa: E402
NB = None                            # 클립 수첩 (log 정의 뒤에 만든다)


def log(msg):
    print(msg, flush=True)
    with LOCK:
        STATE["log"] = (STATE["log"] + [msg])[-60:]


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return json.loads(json.dumps(default))


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


UPLOAD_FILE = RANK / "업로드정보.json"

MODES = {
    "ranking": {"script": SCRIPT_FILE, "upload": UPLOAD_FILE, "out": OUT, "voice": RANK / "voice",
                "roles": ("narr", "cat"), "final": "완성본.mp4"},
    "variety": {"script": VAR / "대본.json", "upload": VAR / "업로드정보.json", "out": VAR_OUT,
                "voice": VAR / "voice", "roles": ("vnarr",), "final": "예능_완성본.mp4"},
}


def M(mode):
    return MODES.get(mode or "ranking", MODES["ranking"])


def load_edit():
    return variety.normalize(load_json(VAR_EDIT, variety.DEFAULT_EDIT))


def times_for(mode):
    return variety.seg_times(load_edit()) if mode == "variety" else clip_times(load_layout())
STYLE_KEYS = ("title1", "title1Color", "title2", "title2Color", "sub", "subColor", "bandHeight",
              "ranking", "order", "numColors", "keepAudio", "ref", "voiceEmo")


def reset_variety():
    import re as _re, time as _t
    ed = load_edit()
    stem = _re.sub(r'[\\/:*?"<>|\s]+', "_", ed.get("title1") or "예능").strip("_")[:30] or "예능"
    arc = BASE / "보관함" / f"{_t.strftime('%y%m%d_%H%M')}_예능_{stem}"
    arc.mkdir(parents=True, exist_ok=True)

    def move(src, dst):
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
    if VAR_EDIT.exists():
        shutil.copy2(VAR_EDIT, arc / VAR_EDIT.name)
    for f in (VAR / "대본.json", VAR / "업로드정보.json"):
        move(f, arc / f.name)
    for p in list(VAR_OUT.iterdir()):
        move(p, arc / "output" / p.name)
    for p in list((VAR / "voice").glob("*.wav")):
        move(p, arc / "voice" / p.name)
    if ed.get("source"):
        move(VAR_SRC / ed["source"], arc / "원본" / ed["source"])
    shutil.rmtree(VAR / "_작업", ignore_errors=True)
    new = {k: ed[k] for k in ("title1Color", "title2Color", "videoTop", "videoH")}
    save_json(VAR_EDIT, variety.normalize(new))
    save_json(VAR / "대본.json", [])
    log(f"🗂 지난 예능 작업을 보관함/{arc.name} 으로 옮겼어요. 새 예능 쇼츠를 시작해요!")
    return arc.name


def reset_project():
    """지금 작업을 보관함으로 옮기고, 디자인 설정만 남긴 채 새로 시작."""
    import re as _re, time as _t
    lay = load_layout()
    stem = _re.sub(r'[\\/:*?"<>|\s]+', "_", lay.get("title1") or "쇼츠").strip("_")[:30] or "쇼츠"
    arc = BASE / "보관함" / f"{_t.strftime('%y%m%d_%H%M')}_{stem}"
    arc.mkdir(parents=True, exist_ok=True)

    def move(src, dst):
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
    shutil.copy2(LAYOUT_FILE, arc / LAYOUT_FILE.name) if LAYOUT_FILE.exists() else None
    for f in (SCRIPT_FILE, UPLOAD_FILE, RANK / "타임라인.json", RANK / "자막.srt"):
        move(f, arc / f.name)
    for p in list(OUT.iterdir()):
        move(p, arc / "output" / p.name)
    for p in list(engine.OUTDIR.glob("*.wav")):
        move(p, arc / "voice" / p.name)
    used = {c["file"] for c in lay["clips"] if c.get("file")}
    for f in used:
        move(CLIPS / f, arc / "clips" / f)
    if (BASE / "분석").exists():
        move(BASE / "분석", arc / "분석")
    done = [e for e in NB.entries if e.get("file") in used]
    save_json(arc / "클립수첩.json", done)
    NB.entries = [e for e in NB.entries if e.get("file") not in used]
    NB.save()
    new = {k: lay[k] for k in STYLE_KEYS if k in lay}
    new["clips"] = [{"rank": r, "file": "", "label": "", "start": 0.0, "end": 0.0, "source": ""}
                    for r in range(1, 6)]
    new["brief"] = ""
    save_json(LAYOUT_FILE, new)
    save_json(SCRIPT_FILE, [])
    log(f"🗂 지난 작업을 보관함/{arc.name} 으로 옮겼어요. 새 쇼츠를 시작해요!")
    return arc.name


def load_layout():
    lay = load_json(LAYOUT_FILE, layout_mod.DEFAULT_LAYOUT)
    for k, v in layout_mod.DEFAULT_LAYOUT.items():
        lay.setdefault(k, v)
    return lay


# ── 타입캐스트 연결 ─────────────────────────────────────
def connect():
    global CLIENT
    key = os.environ.get("TYPECAST_API_KEY", "").strip()
    if not key and (BASE / "apikey.txt").exists():
        key = (BASE / "apikey.txt").read_text(encoding="utf-8-sig").strip()
        os.environ["TYPECAST_API_KEY"] = key
    if not key:
        STATE["error"] = "apikey.txt 가 없거나 비어 있습니다"
        log("❌ " + STATE["error"])
        return
    try:
        CLIENT = engine.make_client()
        sub = CLIENT.get_my_subscription()
        d = sub.model_dump() if hasattr(sub, "model_dump") else vars(sub)
        cr = d.get("credits", {}) or {}
        STATE["credits"] = (cr.get("plan_credits", 0) or 0) - (cr.get("used_credits", 0) or 0)
        STATE["connected"] = True
        STATE["error"] = None
        log(f"✅ 타입캐스트 연결 — 남은 크레딧 {STATE['credits']:,}")
        restore_voices()
    except Exception as e:
        STATE["error"] = str(e)
        log(f"❌ 연결 실패: {e}")


def restore_voices():
    saved = load_json(engine.VOICE_FILE, {})
    for role in ROLES:
        vid = saved.get(role)
        if not vid:
            continue
        try:
            engine.VOICES[role] = vid
            engine.load_profile(CLIENT, role)
        except Exception as e:
            log(f"⚠️ {role} 목소리 복원 실패: {e}")


# 타입캐스트 보이스 화면의 분류 (이름 순서 그대로)
VOICE_CATS = {
    "숏폼·쇼츠": "문정 다은 혜리 필재 혜진 박창수 상현 대진 서현 도윤 태우 예슬 태섭 준기 라연 한영 진우 선영 주영 강일",
    "아이·학생": "서윤 호빈이 하준 아찌 수아 토비 베리 우니 머루 소이 덕구 하율 루리 부끄 하은 채린이 류은 민수 예준 유성",
    "캐릭터·게임": "주완 종대 세우 창희 바빌론 아엘 티안 김고트 몽군 덕환 홍설록 보라 발키리 호빈이",
    "일상 대화": "필재 서현 문정 다은 강일 소예 이현 혜진 민욱 고은 상현 대진 효은 서진 민우 라연 도윤 세현 자인 재선 태우 정훈 형진 지선 명욱",
    "광고·홈쇼핑": "은채 박창수 필재 다은 쇼린이 혜진 문정 태중 홈쇼핑_성준 홈쇼핑_혜수 대길 원우",
    "다큐·나레이션": "지선 대진 태우 서현 이겸 진우 필재 한영 주하 종대 도현 모건 진희 시연 혜진 형진 예슬 도윤",
    "아나운서·뉴스": "서현 강일 송진섭_기자 송진섭_앵커 승재 진희 김경화_앵커 박찬_기자 강수정_기자 강춘식_기자",
}


def voices_in_cat(cat):
    names = [n.replace("_", " ") for n in VOICE_CATS.get(cat, "").split()]
    byname = {}
    for v in engine.all_voices(CLIENT):
        kor = (engine.vname(v)[0] or "").strip()
        if kor and kor not in byname and engine.vemotions(v):
            byname[kor] = v
    return [byname[n] for n in names if n in byname]


def voice_info(v):
    kor, eng = engine.vname(v)
    return {"id": v.voice_id, "name": f"{kor} ({eng})" if kor else eng,
            "gender": str(getattr(v, "gender", "") or ""), "age": str(getattr(v, "age", "") or ""),
            "emotions": sorted(engine.vemotions(v))}


def voice_name(vid):
    if not CLIENT or not vid:
        return ""
    try:
        for v in engine.all_voices(CLIENT):
            if v.voice_id == vid:
                return voice_info(v)["name"]
    except Exception:
        pass
    return vid


def state_payload(mode="ranking"):
    m = M(mode)
    voices = {}
    for role in ROLES:
        vid = engine.VOICES.get(role, "")
        voices[role] = {"id": vid, "name": voice_name(vid),
                        "emotions": sorted(engine.PROFILE.get(role, {}).get("emotions", []))}
    clips = sorted(p.name for p in CLIPS.iterdir()
                   if p.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv"))
    outs = sorted(p.name for p in m["out"].iterdir() if p.suffix.lower() == ".mp4")
    lay = load_layout()
    byfile = NB.by_file()
    try:
        cands = NB.candidates()
    except Exception:
        cands = {}
    return {
        "version": VERSION,
        "refs": sorted((p.name for p in REFS.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")),
                       key=lambda n: (REFS / n).stat().st_mtime, reverse=True),
        "sources": NB.entries, "candidates": cands, "watching": NB.watching,
        "canWatch": os.name == "nt",
        "clipCredit": {f: {"id": e["id"], "credit": src_mod.credit_text(e), "url": src_mod.clean_url(e["url"]),
                           "platform": src_mod.PLATFORM_LABEL.get(e["platform"], "")}
                       for f, e in byfile.items()},
        "connected": STATE["connected"], "credits": STATE["credits"], "error": STATE["error"],
        "busy": STATE["busy"], "log": STATE["log"][-12:],
        "voices": voices,
        "mode": mode if mode in MODES else "ranking", "roles": list(m["roles"]), "final": m["final"],
        "script": resolve_lines(load_json(m["script"], DEFAULT_SCRIPT), mode),
        "clipTimes": times_for(mode),
        "outTimes": {p.name: p.stat().st_mtime for p in m["out"].iterdir() if p.is_file()},
        "upload": load_json(m["upload"], None),
        "scriptStamp": m["script"].stat().st_mtime if m["script"].exists() else 0,
        "edit": load_edit(), "editLength": variety.total_length(load_edit()),
        "varSources": sorted(p.name for p in VAR_SRC.iterdir()
                             if p.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv", ".m4v")),
        "layout": lay, "clips": clips, "outputs": outs,
        "layoutLength": layout_mod.total_length(lay),
        "ffmpeg": layout_mod.ffmpeg_ok(),
    }


# ── 생성 ────────────────────────────────────────────────
def clip_times(lay):
    """재생 순서대로 각 클립이 완성 영상의 몇 초~몇 초인지."""
    t, out = 0.0, []
    for c in layout_mod.play_order(lay):
        s, e = float(c.get("start") or 0), float(c.get("end") or 0)
        if e <= s:
            continue
        out.append({"rank": c["rank"], "start": round(t, 2), "end": round(t + e - s, 2),
                    "label": c.get("label", ""), "file": c.get("file", "")})
        t += e - s
    return out


def resolve_lines(lines, mode="ranking"):
    """줄마다 id 를 붙이고, '몇 위 클립(예능은 구간)의 몇 초' 를 완성 영상 시각(start)으로 바꾼다."""
    import uuid
    ct = {c["rank"]: c for c in times_for(mode)}
    vdir = M(mode)["voice"]
    for ln in lines:
        ln.setdefault("id", uuid.uuid4().hex[:8])
        ln.setdefault("speed", 1.0)
        ln.setdefault("pitch", 0)
        ln.setdefault("intensity", 1.0)
        if ln.get("clip") in ct:
            ln["start"] = round(ct[ln["clip"]]["start"] + float(ln.get("at") or 0), 2)
        ln["fresh"] = bool(ln.get("file") and ln.get("key") == line_key(ln)
                           and (vdir / ln["file"]).exists())
    return lines


def line_key(ln):
    return json.dumps([ln.get(k) for k in SCRIPT_KEYS] + [engine.VOICES.get(ln.get("speaker"), "")],
                      ensure_ascii=False)


def generate_line(i, force=False, mode="ranking"):
    m = M(mode)
    lines = resolve_lines(load_json(m["script"], DEFAULT_SCRIPT), mode)
    ln = lines[i]
    role = ln["speaker"]
    if not engine.VOICES.get(role):
        raise RuntimeError(f"{engine.LABEL.get(role, role)} 목소리를 먼저 고르세요")
    if ln["fresh"] and not force:                       # 바뀐 게 없으면 크레딧 아끼기
        return {"duration": ln["duration"], "fit": ln.get("fit", True), "cached": True, "file": ln["file"]}
    emo, swapped = engine.resolve_emotion(role, [ln.get("emotion") or "normal", "normal"])
    speed, pitch = float(ln.get("speed") or 1.0), int(ln.get("pitch") or 0)
    slot = float(ln.get("slot") or 0)
    path = m["voice"] / f"{ln['id']}.wav"
    tempo = speed
    for _ in range(3):
        audio, dur, words = engine.synth(CLIENT, ln["text"], role, emo,
                                         float(ln.get("intensity", 1.0)), tempo, pitch)
        path.write_bytes(audio)
        if not slot or dur <= slot + engine.TOL:
            break
        nt = min(2.0, speed * 1.4, tempo * dur / max(0.3, slot - engine.TOL / 2))  # 넘치면 조금만 빠르게
        if nt - tempo < 0.01:
            break
        tempo = nt
    fit = not slot or dur <= slot + engine.TOL
    ln.update(emotion=emo, duration=round(dur, 3), file=path.name, tempo=round(tempo, 3), fit=fit,
              words=[{"text": w.text, "start": w.start, "end": w.end} for w in words])
    ln["key"] = line_key(ln)
    save_json(m["script"], lines)
    if mode == "ranking":
        write_timeline(lines)
    log(f"  [{i+1}] {dur:.2f}s" + (f" / {slot:.2f}s 안에 {'✅' if fit else '⚠️ 넘침'}" if slot else ""))
    return {"duration": ln["duration"], "fit": fit, "emotion": emo, "swapped": swapped, "file": path.name}


def finish_all(mode="ranking"):
    """음성(바뀐 줄만) → 구성 영상 → 더빙 합성까지 한 번에."""
    m = M(mode)
    lines = resolve_lines(load_json(m["script"], DEFAULT_SCRIPT), mode)
    todo = [i for i, l in enumerate(lines) if l.get("text", "").strip()]
    if not todo and mode == "ranking":
        raise RuntimeError("대본이 비어 있어요")
    for n, i in enumerate(todo, 1):
        STATE["busy"] = f"음성 만드는 중 {n}/{len(todo)}"
        generate_line(i, mode=mode)
    if not layout_mod.ffmpeg_ok():
        raise RuntimeError("영상 도구(ffmpeg)가 없어요. 편집기.bat 을 다시 켜면 설치돼요")
    if mode == "variety":
        ed = load_edit()
        src = VAR_SRC / (ed.get("source") or "_")
        if not src.exists():
            raise RuntimeError("예능 원본 영상을 먼저 골라 주세요")
        lines = resolve_lines(load_json(m["script"], DEFAULT_SCRIPT), mode)
        STATE["busy"] = "예능 영상 만드는 중"
        variety.render(ed, src, VAR_OUT / "예능_편집영상.mp4", lines, VAR / "_작업", log)
        STATE["busy"] = "더빙 합성 중"
        if any(l.get("file") and l.get("duration") for l in lines):
            mux_voices(VAR_OUT / "예능_편집영상.mp4", VAR_OUT / m["final"], mode)
        else:
            shutil.copy2(VAR_OUT / "예능_편집영상.mp4", VAR_OUT / m["final"])
        return
    STATE["busy"] = "구성 영상 만드는 중"
    layout_mod.render(load_layout(), CLIPS, OUT / "구성영상.mp4", log)
    STATE["busy"] = "더빙 합성 중"
    mux_voices(OUT / "구성영상.mp4", OUT / "완성본.mp4")


def write_timeline(lines):
    meta, srt = [], []

    class Wd:
        pass

    for i, ln in enumerate(lines):
        if not ln.get("duration") or ln.get("start") is None:
            continue
        meta.append({"id": i + 1, "speaker": ln["speaker"],
                     "voice_id": engine.VOICES.get(ln["speaker"], ""),
                     "emotion": ln.get("emotion"), "start": ln["start"], "slot": ln.get("slot"),
                     "duration": ln["duration"], "text": ln["text"],
                     "file": ln.get("file", f"{i+1:02d}_{ln['speaker']}.wav")})
        ws = []
        for w in ln.get("words", []):
            o = Wd()
            o.text, o.start, o.end = w["text"], w["start"], w["end"]
            ws.append(o)
        srt.append((ln["start"], ln["duration"], ln["text"], ws))
    save_json(RANK / "타임라인.json", meta)
    if srt:
        engine.build_srt(srt, str(RANK / "자막.srt"))


def mux_voices(video, out, mode="ranking"):
    """랭킹: 원본 소리를 낮추고 대사를 얹는다. 예능: 내레이션 나오는 동안만 원본 소리를 끈다."""
    m = M(mode)
    lines = [l for l in resolve_lines(load_json(m["script"], []), mode) if l.get("duration") and l.get("file")
             and l.get("start") is not None and (m["voice"] / l["file"]).exists()]
    if not lines:
        raise RuntimeError("생성된 대사가 없습니다")
    dur, has_a = layout_mod.probe(video)
    cmd = [layout_mod.FF, "-y", "-v", "error", "-i", str(video)]
    parts, labels = [], []
    for k, ln in enumerate(lines, start=1):
        f = m["voice"] / ln["file"]
        cmd += ["-i", str(f)]
        ms = int(round(float(ln["start"]) * 1000))
        parts.append(f"[{k}:a]adelay={ms}|{ms},aresample=44100,aformat=channel_layouts=stereo[a{k}]")
        labels.append(f"[a{k}]")
    if has_a and mode == "variety":
        mute = "".join(f"volume=enable='between(t,{float(l['start']) - 0.05:.3f},"
                       f"{float(l['start']) + float(l['duration']) + 0.1:.3f})':volume=0," for l in lines)
        parts.append(f"[0:a]{mute}aresample=44100,aformat=channel_layouts=stereo[o]")
        labels.insert(0, "[o]")
    elif has_a:
        parts.append("[0:a]volume=0.45,aresample=44100,aformat=channel_layouts=stereo[o]")
        labels.insert(0, "[o]")
    parts.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0,"
                 f"alimiter=limit=0.95,apad,atrim=0:{dur:.3f}[aout]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out)]
    subprocess.run(cmd, check=True)
    log(f"✅ 더빙 합성 완료: {Path(out).name}")


def run_bg(name, fn):
    def work():
        STATE["busy"] = name
        try:
            fn()
        except Exception as e:
            log(f"❌ {name} 실패: {e}")
        finally:
            STATE["busy"] = None
    threading.Thread(target=work, daemon=True).start()


# ── HTTP ────────────────────────────────────────────────
PICK_LOCK = threading.Lock()


def pick_video(target="clips"):
    """윈도우 '열기' 창을 띄워 영상을 고르게 한다. 다른 폴더 영상이면 clips(예능은 예능/원본)로 복사."""
    dest = VAR_SRC if target == "variety" else CLIPS
    import shutil
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return {"error": "nodialog"}
    if not PICK_LOCK.acquire(blocking=False):
        return {"error": "busy"}
    try:
        try:
            root = tk.Tk()
        except Exception:
            return {"error": "nodialog"}
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        f = filedialog.askopenfilename(parent=root, title="영상 고르기 — 보기를 '큰 아이콘'으로 바꾸면 썸네일이 보여요",
                                       initialdir=str(dest),
                                       filetypes=[("영상", "*.mp4 *.mov *.m4v *.webm *.mkv"), ("모든 파일", "*.*")])
        root.destroy()
    finally:
        PICK_LOCK.release()
    if not f:
        return {"cancel": True}
    src = Path(f).resolve()
    if src.parent == dest.resolve():
        return {"file": src.name}
    dst = dest / src.name
    if dst.exists() and dst.stat().st_size == src.stat().st_size:
        return {"file": dst.name}
    n = 2
    while dst.exists():
        dst = dest / f"{src.stem}_{n}{src.suffix}"
        n += 1
    shutil.copy2(src, dst)
    log(f"📂 {src.name} → {dest.relative_to(BASE)} 폴더로 복사")
    return {"file": dst.name, "copied": True}


def safe_child(folder, name):
    p = (folder / Path(urllib.parse.unquote(name)).name).resolve()
    if folder.resolve() not in p.parents:
        return None
    return p if p.exists() and p.is_file() else None


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def send_file(self, path):
        size = path.stat().st_size
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            start = int(a) if a else 0
            end = int(b) if b else size - 1
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 16, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        path = u.path
        try:
            if path in ("/", "/index.html"):
                return self.send_file(WEB / "index.html")
            if path == "/favicon.ico":
                return self.send_file(WEB / "img" / "cat.png")
            if path.startswith("/fonts/"):
                f = safe_child(WEB / "fonts", path[7:])
                return self.send_file(f) if f else self.send_error(404)
            if path.startswith("/img/"):
                f = safe_child(WEB / "img", path[5:])
                return self.send_file(f) if f else self.send_error(404)
            if path.startswith("/voice/"):
                f = safe_child(MODES["ranking"]["voice"], path[7:]) or safe_child(MODES["variety"]["voice"], path[7:])
                return self.send_file(f) if f else self.send_error(404)
            if path.startswith("/src/"):
                f = safe_child(VAR_SRC, path[5:])
                return self.send_file(f) if f else self.send_error(404)
            if path.startswith("/clips/"):
                f = safe_child(CLIPS, path[7:])
                return self.send_file(f) if f else self.send_error(404)
            if path.startswith("/out/"):
                f = safe_child(OUT, path[5:]) or safe_child(VAR_OUT, path[5:])
                return self.send_file(f) if f else self.send_error(404)
            if path == "/api/version":
                return self.send_json({"version": VERSION})
            if path.startswith("/refs/"):
                f = safe_child(REFS, path[6:])
                return self.send_file(f) if f else self.send_error(404)
            if path == "/api/state":
                return self.send_json(state_payload((q.get("mode") or ["ranking"])[0]))
            if path == "/api/voices":
                if not CLIENT:
                    return self.send_json({"error": "타입캐스트에 연결되지 않았습니다"}, 400)
                term = (q.get("q") or [""])[0].strip()
                cat = (q.get("cat") or [""])[0].strip()
                if cat:
                    return self.send_json({"voices": [voice_info(v) for v in voices_in_cat(cat)],
                                           "cats": list(VOICE_CATS)})
                vs = engine.search_voices(CLIENT, term) if term else engine.all_voices(CLIENT)
                return self.send_json({"voices": [voice_info(v) for v in vs[:60]]})
            if path == "/api/recommend":
                if not CLIENT:
                    return self.send_json({"error": "타입캐스트에 연결되지 않았습니다"}, 400)
                role = (q.get("role") or ["narr"])[0]
                rec = CLIENT.recommend_voices(engine.VOICE_QUERIES.get(role, ""), count=6)
                byid = {v.voice_id: v for v in engine.all_voices(CLIENT)}
                out = [voice_info(byid[r.voice_id]) for r in rec if r.voice_id in byid]
                return self.send_json({"voices": out})
            return self.send_error(404)
        except Exception as e:
            return self.send_json({"error": str(e)}, 500)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            data = self.body()
            if path == "/api/refs/upload":
                import base64, re as _re, time as _t
                raw = data.get("data", "")
                m = _re.match(r"data:image/(png|jpe?g|webp);base64,(.+)", raw, _re.S)
                if not m:
                    return self.send_json({"error": "PNG · JPG · WEBP 사진만 올릴 수 있어요"}, 400)
                blob = base64.b64decode(m.group(2))
                if len(blob) > 15 * 1024 * 1024:
                    return self.send_json({"error": "15MB 보다 작은 사진만 올릴 수 있어요"}, 400)
                ext = "jpg" if m.group(1).startswith("jp") else m.group(1)
                stem = _re.sub(r"[^\w.-]+", "_", Path(data.get("name") or "예시").stem)[:40] or "예시"
                f = REFS / f"{_t.strftime('%m%d_%H%M%S')}_{stem}.{ext}"
                f.write_bytes(blob)
                log(f"🖼 참고 예시 저장: {f.name}")
                return self.send_json({"ok": True, "name": f.name})
            if path == "/api/refs/delete":
                f = safe_child(REFS, data.get("name", ""))
                if f:
                    f.unlink()
                return self.send_json({"ok": True})
            if path == "/api/shutdown":
                threading.Timer(0.3, lambda: os._exit(0)).start()
                return self.send_json({"ok": True})
            if path == "/api/pick-video":
                return self.send_json(pick_video(data.get("target", "clips")))
            if path == "/api/variety/edit":
                save_json(VAR_EDIT, variety.normalize(data["edit"]))
                return self.send_json({"ok": True, "length": variety.total_length(load_edit())})
            if path == "/api/variety/silence":
                ed = load_edit()
                src = VAR_SRC / (ed.get("source") or "_")
                if not src.exists():
                    return self.send_json({"error": "원본 영상을 먼저 골라 주세요"}, 400)
                a, b = float(data.get("a", 0)), float(data.get("b", 0))
                if b <= a:
                    b = a + layout_mod.probe(src)[0]
                db = {"soft": -38, "normal": -32, "tight": -28}.get(data.get("sens"), -32)
                segs, n = variety.find_speech(src, a, min(b, layout_mod.probe(src)[0]), noise_db=db)
                ed["segments"] = [s for s in ed["segments"] if float(s["end"]) <= a or float(s["start"]) >= b] + segs
                ed["range"] = [a, b]
                save_json(VAR_EDIT, variety.normalize(ed))
                log(f"✂️ 빈 호흡 {n}곳 → 말하는 구간 {len(segs)}개")
                return self.send_json({"ok": True, "count": len(segs), "silences": n})
            if path.startswith("/api/sources/"):
                act = path.rsplit("/", 1)[1]
                if act == "add":
                    links = src_mod.extract_links(data.get("url", "")) or [data.get("url", "")]
                    added = [NB.add(u)[1] for u in links]
                    return self.send_json({"ok": True, "added": sum(added), "dup": len(added) - sum(added)})
                if act == "update":
                    return self.send_json({"ok": True, "entry": NB.update(data["id"], **data)})
                if act == "attach-clear":
                    for e in NB.entries:
                        if e.get("file") == data.get("file"):
                            e["file"] = ""
                    NB.save()
                    return self.send_json({"ok": True})
                if act == "delete":
                    NB.delete(data["id"])
                    return self.send_json({"ok": True})
                if act == "recheck":
                    NB.recheck(data["id"])
                    return self.send_json({"ok": True})
                if act == "import":
                    return self.send_json({"ok": True, "entry": NB.import_file(data["id"], data["path"])})
                if act == "attach":
                    return self.send_json({"ok": True, "entry": NB.attach_existing(data["id"], data["file"])})
                if act == "watch":
                    NB.watching = bool(data.get("on"))
                    log("📋 링크 자동 기록 " + ("켜짐" if NB.watching else "꺼짐"))
                    return self.send_json({"ok": True})
                return self.send_error(404)
            if path == "/api/reset":
                if STATE["busy"]:
                    return self.send_json({"error": "작업이 끝난 뒤에 눌러 주세요"}, 400)
                fn = reset_variety if data.get("mode") == "variety" else reset_project
                return self.send_json({"ok": True, "archive": fn()})
            if path == "/api/finish":
                if not CLIENT:
                    return self.send_json({"error": "타입캐스트에 연결되지 않았습니다"}, 400)
                if STATE["busy"]:
                    return self.send_json({"error": "다른 작업이 끝나면 눌러 주세요"}, 400)
                mode = data.get("mode", "ranking")
                run_bg("한 번에 완성하기", lambda: finish_all(mode))
                return self.send_json({"ok": True})
            if path == "/api/script":
                sf = M(data.get("mode"))["script"]
                save_json(sf, [{k: v for k, v in l.items() if k != "fresh"} for l in data["lines"]])
                return self.send_json({"ok": True, "stamp": sf.stat().st_mtime})
            if path == "/api/layout":
                save_json(LAYOUT_FILE, data["layout"])
                return self.send_json({"ok": True, "length": layout_mod.total_length(data["layout"])})
            if path == "/api/voice":
                role, vid = data["role"], data["voice_id"]
                engine.VOICES[role] = vid
                engine.load_profile(CLIENT, role)
                save_json(engine.VOICE_FILE, engine.VOICES)
                log(f"🎙 {engine.LABEL.get(role, role)} → {voice_name(vid)}")
                return self.send_json({"ok": True})
            if path == "/api/generate":
                if not CLIENT:
                    return self.send_json({"error": "타입캐스트에 연결되지 않았습니다"}, 400)
                return self.send_json(generate_line(int(data["index"]), bool(data.get("force")), data.get("mode", "ranking")))
            if path == "/api/open-folder":
                target = {"clips": CLIPS, "output": OUT, "voice": engine.OUTDIR, "vout": VAR_OUT,
                          "vsrc": VAR_SRC}.get(
                    data.get("name"), BASE)
                if hasattr(os, "startfile"):
                    os.startfile(str(target))
                return self.send_json({"ok": True, "path": str(target)})
            if path == "/api/render":
                lay = load_layout()
                out = OUT / "구성영상.mp4"
                run_bg("구성 영상 만들기", lambda: layout_mod.render(lay, CLIPS, out, log))
                return self.send_json({"ok": True})
            if path == "/api/mux":
                src = OUT / data.get("video", "구성영상.mp4")
                if not src.exists():
                    return self.send_json({"error": f"{src.name} 이 없습니다. 구성 영상을 먼저 만드세요"}, 400)
                out = OUT / "완성본.mp4"
                run_bg("더빙 합성", lambda: mux_voices(src, out))
                return self.send_json({"ok": True})
            return self.send_error(404)
        except Exception as e:
            log(f"❌ {e}")
            return self.send_json({"error": str(e)}, 500)


def main():
    global NB
    NB = src_mod.Notebook(BASE / "클립수첩.json", CLIPS, log)
    url = f"http://127.0.0.1:{PORT}/"
    srv = None
    for attempt in range(3):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
            break
        except OSError:
            if attempt == 0:
                print("예전 편집기가 켜져 있어요. 끄고 새로 켭니다…", flush=True)
            try:
                import urllib.request
                req = urllib.request.Request(url + "api/shutdown", data=b"{}", method="POST",
                                             headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=2)
            except Exception:
                pass
            import time
            time.sleep(1.5)
    if srv is None:
        print("=" * 52)
        print("  예전 편집기가 아직 켜져 있어서 새로 켤 수 없어요.")
        print("  열려 있는 검은 창(편집기)을 모두 닫고 다시 실행하세요.")
        print("=" * 52)
        sys.exit(1)
    threading.Thread(target=connect, daemon=True).start()
    NB.start_clipboard_watch()
    print("=" * 52)
    print("  쇼츠 공방 편집기가 켜졌습니다")
    print(f"  {url}")
    print("  이 창을 닫으면 편집기도 꺼집니다")
    print("=" * 52, flush=True)
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
