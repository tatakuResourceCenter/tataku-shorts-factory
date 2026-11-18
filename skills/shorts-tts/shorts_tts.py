#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
타입캐스트 API로 쇼츠 내레이션을 각 슬롯 시간에 맞게 생성하고 영상에 합성한다.

  1) 목소리를 번호로 고르고, 그 목소리가 지원하는 감정·모델을 조회한다
  2) 대사마다 선호 감정을 순서대로 시도해 지원되는 첫 감정을 쓴다
  3) with-timestamps 로 생성 → 오디오 + 실제 길이 + 단어 타이밍을 한 번에 받음
  4) 슬롯보다 길면 audio_tempo 를 보정해 재생성 (0.88~1.22, 그 밖은 경고)
  5) ffmpeg 으로 지정 초에 배치해 영상에 합성, 단어 타임스탬프로 SRT 생성

사용법
  pip install typecast-python
  set TYPECAST_API_KEY=발급받은_키

  python shorts_tts.py --check          # 플랜·크레딧 확인
  python shorts_tts.py --dry-run        # 타임라인만 점검
  python shorts_tts.py --voices-only    # 음성·자막만 생성 (ffmpeg 불필요)
  python shorts_tts.py --video 편집본_무음_16초.mp4 --out 완성본.mp4
"""

import os
import sys
import json
import base64
import argparse
import subprocess
from pathlib import Path

from typecast import Typecast
from typecast.models import Output
from typecast.models.tts import TTSRequestWithTimestamps, TTSModel

# ─────────────────────────────────────────────────────────────
# 타입캐스트 attribution
#   https://typecast.ai/docs/llms.txt 의 규칙에 따라 코드에 영속적으로 남긴다.
#   source       : 이 통합을 안내한 진입 경로 (API 페이지 프롬프트 → api-page)
#   generated_by : 통합 코드를 작성한 코딩 에이전트의 안정적 소문자 식별자
#   사용자명·이메일·프로젝트명·API 키·호스트·프롬프트는 절대 넣지 않는다.
# ─────────────────────────────────────────────────────────────
TYPECAST_SOURCE = "api-page"
TYPECAST_GENERATED_BY = "claude-code"

PREFERRED_MODEL = "ssfm-v30"
LANG = "kor"

VOICES = {
    "narr": os.environ.get("VOICE_NARR", ""),
    "cat":  os.environ.get("VOICE_CAT", ""),
}
LABEL = {"narr": "내레이터", "cat": "고양이"}
VOICE_QUERIES = {
    "narr": "밝고 경쾌하게 빠른 템포로 말하는 20대 한국어 여성 내레이터, 유튜브 쇼츠 해설용",
    "cat":  "시크하고 나른한 저음으로 툭툭 내뱉는 한국어 목소리, 고양이 캐릭터 더빙용",
}

# 목소리마다 지원 감정이 다르므로 선호 순서로 적는다.
# 앞에서부터 시도해 그 목소리가 지원하는 첫 감정을 쓴다. 다 안 되면 normal.
LINES = [
    # id, 화자,    시작,  슬롯,  감정 선호순,                         강도, 텍스트
    (1,  "narr",  0.20, 2.80, ["normal", "casual"],                1.0, "집사 손, 압류당했습니다."),
    (2,  "cat",   3.20, 1.30, ["cold", "tonedown", "normal"],      0.8, "가만히 있어."),
    (3,  "cat",   4.70, 0.60, ["toneup", "happy"],                 1.0, "어?"),
    (4,  "cat",   5.40, 1.00, ["sad", "tonedown"],                 0.7, "어디 갔어."),
    (5,  "narr",  6.50, 2.30, ["normal"],                          1.0, "이어진 무언의 압박."),
    (6,  "cat",   8.90, 0.90, ["angry", "shout"],                  1.0, "내놔."),
    (7,  "narr",  9.90, 1.70, ["cheer", "happy"],                  0.8, "결국, 집사 백기."),
    (8,  "cat",  11.70, 2.90, ["sarcasm", "happy", "toneup"],      0.8, "진작 이렇게 나왔어야지."),
    (9,  "narr", 14.80, 1.60, ["cheer", "happy"],                  1.0, "손 반납 완료."),
]

TOL = 0.06
TEMPO_MIN, TEMPO_MAX = 0.88, 1.22
OUTDIR = Path("voice")
VOICE_FILE = Path("voices.json")   # 고른 목소리를 기억해 다음 실행에 재사용

# 목소리별로 조회해 채운다: role -> {"model": TTSModel, "emotions": set}
PROFILE = {}
_ALL = []                          # 전체 목소리 목록 캐시


def all_voices(client):
    global _ALL
    if not _ALL:
        _ALL = client.voices_v3()
    return _ALL


def vname(v):
    """(한글이름, 영문이름)"""
    n = v.voice_name
    return (getattr(n, "kor", "") or "", getattr(n, "eng", "") or "") \
        if not isinstance(n, str) else ("", n)


def vemotions(v):
    for m in v.models:
        if getattr(m.version, "value", str(m.version)) == PREFERRED_MODEL:
            return set(m.emotions or [])
    return set()


def search_voices(client, q):
    """한글 또는 영문 이름으로 검색."""
    out = []
    for v in all_voices(client):
        kor, eng = vname(v)
        if q in kor or q.lower() in eng.lower():
            out.append(v)
    return out


def cmd_list(client, queries):
    vs = []
    if queries:
        seen = set()
        for q in queries:
            for v in search_voices(client, q):
                if v.voice_id not in seen:
                    seen.add(v.voice_id)
                    vs.append(v)
    else:
        vs = all_voices(client)

    if not vs:
        print(f"검색 결과 없음: {' '.join(queries)}")
        return
    print(f"── 목소리 {len(vs)}개 ──")
    for v in vs:
        kor, eng = vname(v)
        emo = vemotions(v)
        label = f"{kor} ({eng})" if kor else eng
        tag = f"{v.gender or '?'}/{v.age or '?'}"
        print(f"\n  {label}   [{tag}]")
        print(f"     {v.voice_id}")
        print(f"     감정 {len(emo)}종: {', '.join(sorted(emo)) if emo else '(ssfm-v30 미지원)'}")


def make_client():
    key = os.environ.get("TYPECAST_API_KEY", "").strip()
    if not key:
        sys.exit("❌ TYPECAST_API_KEY 를 설정하세요. "
                 "키 발급: https://studio.typecast.ai/developers/api")
    return Typecast(api_key=key,
                    source=TYPECAST_SOURCE,
                    generated_by=TYPECAST_GENERATED_BY)


def explain_error():
    print("""
  ⚠️  막히면 아래를 확인하세요
      · 403 → 구 Starter 키는 현재 SSFM API와 호환되지 않습니다 (새 키 발급)
      · 403 → 웹 구독과 API 플랜은 별개입니다
      · 403 → 키에 앞뒤 공백이 섞였거나 계정이 휴면 상태
      콘솔: https://studio.typecast.ai/developers/api""")


def cmd_check(client):
    try:
        sub = client.get_my_subscription()
    except Exception as e:
        print(f"❌ 조회 실패: {e}")
        explain_error()
        return
    print("── 구독 정보 ──")
    data = sub.model_dump() if hasattr(sub, "model_dump") else vars(sub)
    for k, v in data.items():
        print(f"   {k}: {v}")


def load_profile(client, role):
    """목소리가 지원하는 모델과 감정을 조회한다."""
    vid = VOICES[role]
    v = client.voice_v3(vid)

    chosen, emotions = None, []
    for m in v.models:
        ver = getattr(m.version, "value", str(m.version))
        if ver == PREFERRED_MODEL:
            chosen, emotions = ver, list(m.emotions or [])
            break
    if chosen is None and v.models:          # 선호 모델이 없으면 첫 모델
        m = v.models[0]
        chosen = getattr(m.version, "value", str(m.version))
        emotions = list(m.emotions or [])
    if chosen is None:
        sys.exit(f"❌ {LABEL[role]} 목소리가 지원하는 모델이 없습니다")

    PROFILE[role] = {"model": TTSModel(chosen), "emotions": set(emotions)}
    print(f"   모델 {chosen} / 감정 {len(emotions)}종: {', '.join(sorted(emotions))}")


def choose_one(client, role):
    """이름으로 검색하거나 추천을 받아 고른다."""
    print(f"\n── {LABEL[role]} 목소리 고르기 ──")
    print("   쓰시던 목소리 이름을 넣으면 검색하고,")
    print("   그냥 Enter 를 치면 어울리는 목소리를 추천합니다.")

    while True:
        q = input("\n   이름 (예: 문정, 서윤) 또는 Enter: ").strip()
        cands = []           # [(표시이름, voice_id)]
        if q:
            found = search_voices(client, q)
            if not found:
                print(f"   '{q}' 결과 없음. 다시 입력하거나 Enter 로 추천받으세요.")
                continue
            for v in found[:15]:
                kor, eng = vname(v)
                cands.append((f"{kor} ({eng})" if kor else eng, v.voice_id))
        else:
            try:
                for v in client.recommend_voices(VOICE_QUERIES[role], count=5):
                    cands.append((f"{v.voice_name}  적합도 {v.score:.3f}", v.voice_id))
            except Exception as e:
                print(f"   추천 실패: {e}")
                explain_error()
                sys.exit(1)
            if not cands:
                print("   추천 결과가 없습니다. 이름으로 검색해 보세요.")
                continue

        for i, (name, _) in enumerate(cands, 1):
            print(f"   {i}. {name}")
        s = input(f"\n   번호 (1-{len(cands)}) 또는 r 로 다시 검색: ").strip()
        if s.lower() == "r":
            continue
        if s.isdigit() and 1 <= int(s) <= len(cands):
            name, vid = cands[int(s) - 1]
            VOICES[role] = vid
            print(f"   → {name.split('  적합도')[0]} 선택")
            return
        print("   번호를 다시 입력하세요.")


def pick_voices(client):
    saved = {}
    if VOICE_FILE.exists():
        try:
            saved = json.loads(VOICE_FILE.read_text(encoding="utf-8"))
        except Exception:
            saved = {}

    for role in ("narr", "cat"):
        if not VOICES.get(role) and saved.get(role):
            VOICES[role] = saved[role]
            print(f"\n── {LABEL[role]}: 지난번 선택 재사용 ({saved.get(role + '_name', VOICES[role])})")
            print("     바꾸려면 voices.json 을 지우고 다시 실행하세요.")
        elif VOICES.get(role):
            print(f"\n── {LABEL[role]}: 지정됨 ({VOICES[role]})")
        else:
            choose_one(client, role)

        try:
            load_profile(client, role)
        except Exception as e:
            print(f"   목소리 정보 조회 실패: {e}")
            explain_error()
            sys.exit(1)

    try:
        VOICE_FILE.write_text(
            json.dumps(VOICES, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def resolve_emotion(role, prefs):
    """그 목소리가 지원하는 첫 감정을 고른다."""
    supported = PROFILE[role]["emotions"]
    for e in prefs:
        if e in supported:
            return e, (e != prefs[0])
    return ("normal", True) if "normal" in supported else (sorted(supported)[0], True)


def synth(client, text, role, emotion, intensity, tempo):
    req = TTSRequestWithTimestamps(
        voice_id=VOICES[role],
        text=text,
        model=PROFILE[role]["model"],
        language=LANG,
        prompt={"emotion_preset": emotion, "emotion_intensity": intensity},
        output=Output(
            audio_format="wav",
            audio_tempo=tempo,
            remove_silence_ms=0,   # 앞뒤 무음 제거 → 시작점 오차 제거
            target_lufs=-16.0,     # 대사 음량 통일
        ),
    )
    res = client.text_to_speech_with_timestamps(req, granularity="word")
    return base64.b64decode(res.audio), res.audio_duration, (res.words or [])


def fit_line(client, lid, role, slot, emotion, intensity, text):
    tempo, path = 1.0, OUTDIR / f"{lid:02d}_{role}.wav"
    dur, words = 0.0, []
    for attempt in range(1, 4):
        audio, dur, words = synth(client, text, role, emotion, intensity, tempo)
        path.write_bytes(audio)
        over = dur - slot
        print(f"  [{lid}] 시도{attempt} tempo={tempo:.3f} → {dur:.2f}s / 슬롯 {slot:.2f}s", end="")
        if over <= TOL:
            print("  ✅")
            return path, dur, words
        new_tempo = min(TEMPO_MAX, max(TEMPO_MIN, tempo * (dur / (slot - TOL / 2))))
        if abs(new_tempo - tempo) < 0.005:
            print(f"  ⚠️  {over:.2f}s 초과 — 대사를 줄이거나 슬롯을 넓히세요")
            return path, dur, words
        print(f"  → 재생성 (tempo {new_tempo:.3f})")
        tempo = new_tempo
    print(f"  ⚠️  [{lid}] 3회 후에도 {dur:.2f}s — 대사 단축 권장")
    return path, dur, words


def build_srt(entries, srt_path, max_chars=18):
    def ts(t):
        h, r = divmod(max(t, 0), 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"

    cues = []
    for start, dur, text, words in entries:
        if not words:
            cues.append((start, start + dur, text))
            continue
        buf, b0, b1 = "", None, None
        for w in words:
            cand = (buf + " " + w.text).strip()
            if buf and len(cand) > max_chars:
                cues.append((start + b0, start + b1, buf))
                buf, b0, b1 = w.text, w.start, w.end
            else:
                buf = cand
                b0 = w.start if b0 is None else b0
                b1 = w.end
        if buf:
            cues.append((start + b0, start + b1, buf))

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, (a, b, t) in enumerate(cues, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n")
    return len(cues)


def mux(video, items, out):
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video)]
    for p, _ in items:
        cmd += ["-i", str(p)]
    parts, labels = [], []
    for i, (_, start) in enumerate(items, start=1):
        ms = int(round(start * 1000))
        parts.append(f"[{i}:a]adelay={ms}|{ms},aresample=48000[a{i}]")
        labels.append(f"[a{i}]")
    parts.append("".join(labels) +
                 f"amix=inputs={len(items)}:normalize=0:dropout_transition=0,"
                 f"alimiter=limit=0.95[aout]")
    cmd += ["-filter_complex", ";".join(parts),
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(out)]
    subprocess.run(cmd, check=True)


def check_timeline():
    print("── 타임라인 점검 ──")
    ok = True
    for lid, who, *_ in LINES:
        if who not in VOICES:
            sys.exit(f"  ❌ {lid}번 화자 '{who}' 미정의")
    for a, b in zip(LINES, LINES[1:]):
        end = a[2] + a[3]
        if end > b[2] + 0.01:
            print(f"  ⚠️  {a[0]}번({end:.2f}s 종료) ↔ {b[0]}번({b[2]:.2f}s 시작) 겹침")
            ok = False
    print(f"  대사 {len(LINES)}개, 마지막 종료 "
          f"{LINES[-1][2] + LINES[-1][3]:.2f}s{'  ✅' if ok else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video")
    ap.add_argument("--out", default="완성본.mp4")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--voices-only", action="store_true")
    ap.add_argument("--list", nargs="*", metavar="이름",
                    help="목소리 검색 (예: --list 문정 서윤). 비우면 전체 목록")
    ap.add_argument("--reset-voices", action="store_true",
                    help="저장된 목소리 선택을 지우고 다시 고르기")
    args = ap.parse_args()

    if args.check:
        return cmd_check(make_client())
    if args.list is not None:
        try:
            return cmd_list(make_client(), args.list)
        except Exception as e:
            print(f"❌ 목록 조회 실패: {e}")
            return explain_error()
    if args.reset_voices and VOICE_FILE.exists():
        VOICE_FILE.unlink()
        print("저장된 목소리 선택을 지웠습니다.")

    check_timeline()
    if args.dry_run:
        return
    if not args.video and not args.voices_only:
        sys.exit("❌ --video 로 무음 편집본을 지정하거나 --voices-only 를 쓰세요")

    OUTDIR.mkdir(exist_ok=True)
    client = make_client()
    pick_voices(client)

    # 목소리가 지원하는 감정으로 맞춘다
    print("\n── 감정 배정 ──")
    plan = []
    for lid, role, start, slot, prefs, inten, text in LINES:
        emo, swapped = resolve_emotion(role, prefs)
        mark = f"  (← {prefs[0]} 미지원)" if swapped else ""
        print(f"   {lid}. {LABEL[role]:<5} {emo}{mark}")
        plan.append((lid, role, start, slot, emo, inten, text))

    print("\n── 음성 생성 ──")
    items, srt_entries, meta = [], [], []
    try:
        for lid, role, start, slot, emo, inten, text in plan:
            path, dur, words = fit_line(client, lid, role, slot, emo, inten, text)
            items.append((path, start))
            srt_entries.append((start, dur, text, words))
            meta.append({"id": lid, "speaker": role, "voice_id": VOICES[role],
                         "emotion": emo, "start": start, "slot": slot,
                         "duration": round(dur, 3), "text": text})
    except Exception as e:
        print(f"\n❌ 생성 실패: {e}")
        explain_error()
        sys.exit(1)

    n = build_srt(srt_entries, "자막.srt")
    json.dump(meta, open("타임라인.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    if args.voices_only:
        print(f"\n✅ 음성 생성 완료")
        print(f"   {OUTDIR}/ 음성 {len(items)}개")
        print(f"   자막.srt ({n}덩어리) / 타임라인.json")
        print('\n   이제 Claude 에게 "음성 다 뽑았어" 라고 알려주세요.')
        return

    print("\n── 영상 합성 ──")
    mux(args.video, items, args.out)
    print(f"\n✅ 완료: {args.out}")
    print(f"   자막.srt ({n}덩어리) / 타임라인.json / {OUTDIR}/ 음성 {len(items)}개")


if __name__ == "__main__":
    main()
