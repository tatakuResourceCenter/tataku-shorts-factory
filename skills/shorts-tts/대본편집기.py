#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
쇼츠 대본 편집기 — 타입캐스트 음성을 눈으로 보며 만들고 고친다.

  · 대사 텍스트 / 시작 시각 / 길이 / 감정 / 강도를 표에서 직접 수정
  · 목소리는 한글 이름으로 검색해 선택, 그 목소리가 지원하는 감정만 보여줌
  · 줄 단위 생성 + 바로 듣기, 전체 생성, 영상 합성까지
  · 대본은 대본.json 에 저장되어 다음에 그대로 불러옴

음성 생성 엔진은 shorts_tts.py 를 그대로 쓴다 (같은 폴더에 있어야 함).
"""

import os
import re
import sys
import json
import queue
import threading
import subprocess
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import shorts_tts as engine
except ImportError:
    print("shorts_tts.py 가 같은 폴더에 있어야 합니다.")
    sys.exit(1)

try:
    import winsound
    CAN_PLAY = True
except ImportError:
    CAN_PLAY = False

SCRIPT_FILE = Path("대본.json")
VIDEO_DEFAULT = "편집본_무음_16초.mp4"
FONT = ("맑은 고딕", 10)
FONT_B = ("맑은 고딕", 10, "bold")
FONT_T = ("맑은 고딕", 15, "bold")

DEFAULT_LINES = [
    {"speaker": "narr", "start": 0.20, "slot": 2.80, "emotion": "normal",
     "intensity": 1.0, "text": "집사 손, 압류당했습니다."},
    {"speaker": "cat", "start": 3.20, "slot": 1.30, "emotion": "tonedown",
     "intensity": 0.8, "text": "가만히 있어."},
    {"speaker": "cat", "start": 4.70, "slot": 0.60, "emotion": "toneup",
     "intensity": 1.0, "text": "어?"},
    {"speaker": "cat", "start": 5.40, "slot": 1.00, "emotion": "sad",
     "intensity": 0.7, "text": "어디 갔어."},
    {"speaker": "narr", "start": 6.50, "slot": 2.30, "emotion": "normal",
     "intensity": 1.0, "text": "이어진 무언의 압박."},
    {"speaker": "cat", "start": 8.90, "slot": 0.90, "emotion": "angry",
     "intensity": 1.0, "text": "내놔."},
    {"speaker": "narr", "start": 9.90, "slot": 1.70, "emotion": "happy",
     "intensity": 0.8, "text": "결국, 집사 백기."},
    {"speaker": "cat", "start": 11.70, "slot": 2.90, "emotion": "happy",
     "intensity": 0.8, "text": "진작 이렇게 나왔어야지."},
    {"speaker": "narr", "start": 14.80, "slot": 1.60, "emotion": "happy",
     "intensity": 1.0, "text": "손 반납 완료."},
]


class App:
    def __init__(self, root):
        self.root = root
        root.title("쇼츠 대본 편집기")
        root.geometry("1180x800")

        self.client = None
        self.lines = []
        self.rows = []
        self.log_q = queue.Queue()
        self.busy = False

        self._build()
        self.load_script()
        self.root.after(100, self._drain_log)
        self.root.after(300, self.connect)

    # ── 화면 구성 ──────────────────────────────────────────
    def _build(self):
        top = tk.Frame(self.root, padx=12, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="쇼츠 대본 편집기", font=FONT_T).pack(side="left")
        self.status = tk.Label(top, text="연결 중...", font=FONT, fg="#888")
        self.status.pack(side="left", padx=14)

        # 목소리
        vf = tk.LabelFrame(self.root, text=" 목소리 ", font=FONT_B, padx=10, pady=8)
        vf.pack(fill="x", padx=12, pady=(0, 8))
        self.vlabel = {}
        for col, (role, label) in enumerate([("narr", "내레이터"), ("cat", "고양이")]):
            f = tk.Frame(vf)
            f.grid(row=0, column=col, sticky="w", padx=(0, 30))
            tk.Label(f, text=label, font=FONT_B, width=7, anchor="w").pack(side="left")
            lb = tk.Label(f, text="(미선택)", font=FONT, fg="#0066cc", width=34, anchor="w")
            lb.pack(side="left")
            tk.Button(f, text="고르기", font=FONT,
                      command=lambda r=role: self.pick_voice(r)).pack(side="left")
            self.vlabel[role] = lb

        # 표 머리
        hf = tk.Frame(self.root, padx=12)
        hf.pack(fill="x")
        for text, w in [("#", 3), ("화자", 8), ("시작", 7), ("길이", 7),
                        ("감정", 12), ("강도", 6), ("대사", 44), ("결과", 10), ("", 14)]:
            tk.Label(hf, text=text, font=FONT_B, width=w, anchor="w").pack(side="left")

        # 표 본문 (스크롤)
        wrap = tk.Frame(self.root, padx=12)
        wrap.pack(fill="both", expand=True)
        cv = tk.Canvas(wrap, highlightthickness=0, height=330)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=cv.yview)
        self.table = tk.Frame(cv)
        self.table.bind("<Configure>",
                        lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=self.table, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(int(-e.delta/120), "units"))

        # 버튼
        bf = tk.Frame(self.root, padx=12, pady=8)
        bf.pack(fill="x")
        tk.Button(bf, text="＋ 줄 추가", font=FONT, command=self.add_line).pack(side="left")
        tk.Button(bf, text="저장", font=FONT, command=self.save_script).pack(side="left", padx=6)
        tk.Button(bf, text="타임라인 점검", font=FONT,
                  command=self.check_timeline).pack(side="left")
        self.btn_all = tk.Button(bf, text="전체 생성", font=FONT_B, bg="#0066cc",
                                 fg="white", padx=16, command=self.gen_all)
        self.btn_all.pack(side="right")
        self.btn_mux = tk.Button(bf, text="영상 합성", font=FONT, padx=10,
                                 command=self.do_mux)
        self.btn_mux.pack(side="right", padx=6)

        # 로그
        lf = tk.LabelFrame(self.root, text=" 진행 상황 ", font=FONT_B, padx=8, pady=4)
        lf.pack(fill="both", padx=12, pady=(0, 12))
        self.log = tk.Text(lf, height=8, font=("Consolas", 9), bg="#1e1e1e",
                           fg="#d4d4d4", wrap="word")
        self.log.pack(fill="both", expand=True)

    # ── 로그 ──────────────────────────────────────────────
    def say(self, msg):
        self.log_q.put(msg)

    def _drain_log(self):
        while not self.log_q.empty():
            self.log.insert("end", self.log_q.get() + "\n")
            self.log.see("end")
        self.root.after(100, self._drain_log)

    # ── 접속 ──────────────────────────────────────────────
    def connect(self):
        key = os.environ.get("TYPECAST_API_KEY", "").strip()
        if not key and Path("apikey.txt").exists():
            key = Path("apikey.txt").read_text(encoding="utf-8-sig").strip()
            os.environ["TYPECAST_API_KEY"] = key
        if not key:
            self.status.config(text="API 키 없음", fg="#cc0000")
            self.say("❌ apikey.txt 가 없거나 비어 있습니다.")
            return

        def work():
            try:
                self.client = engine.make_client()
                sub = self.client.get_my_subscription()
                d = sub.model_dump() if hasattr(sub, "model_dump") else vars(sub)
                cr = d.get("credits", {})
                left = cr.get("plan_credits", 0) - cr.get("used_credits", 0)
                self.root.after(0, lambda: self.status.config(
                    text=f"연결됨 · 남은 크레딧 {left:,}", fg="#009900"))
                self.say(f"✅ 연결 성공 — 남은 크레딧 {left:,}")
                self.restore_voices()
            except Exception as e:
                self.root.after(0, lambda: self.status.config(text="연결 실패", fg="#cc0000"))
                self.say(f"❌ 연결 실패: {e}")

        threading.Thread(target=work, daemon=True).start()

    def restore_voices(self):
        """voices.json 에 저장된 선택을 복원."""
        if not engine.VOICE_FILE.exists():
            return
        try:
            saved = json.loads(engine.VOICE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        for role in ("narr", "cat"):
            vid = saved.get(role)
            if not vid:
                continue
            try:
                engine.VOICES[role] = vid
                engine.load_profile(self.client, role)
                name = self._voice_name(vid)
                self.root.after(0, lambda r=role, n=name: self._set_voice_label(r, n))
            except Exception as e:
                self.say(f"⚠️ {engine.LABEL[role]} 목소리 복원 실패: {e}")

    def _voice_name(self, vid):
        for v in engine.all_voices(self.client):
            if v.voice_id == vid:
                kor, eng = engine.vname(v)
                return f"{kor} ({eng})" if kor else eng
        return vid

    def _set_voice_label(self, role, name):
        emo = sorted(engine.PROFILE.get(role, {}).get("emotions", []))
        self.vlabel[role].config(text=f"{name} · 감정 {len(emo)}종")
        self.refresh_emotions()

    # ── 목소리 고르기 ─────────────────────────────────────
    def pick_voice(self, role):
        if not self.client:
            messagebox.showwarning("잠깐", "아직 타입캐스트에 연결되지 않았습니다.")
            return

        win = tk.Toplevel(self.root)
        win.title(f"{engine.LABEL[role]} 목소리 고르기")
        win.geometry("560x520")
        win.transient(self.root)

        sf = tk.Frame(win, padx=12, pady=10)
        sf.pack(fill="x")
        tk.Label(sf, text="이름 검색", font=FONT_B).pack(side="left")
        ent = tk.Entry(sf, font=FONT, width=22)
        ent.pack(side="left", padx=6)
        ent.focus()

        tk.Label(win, text="쓰시던 목소리 이름(문정, 아찌 …)을 넣고 검색하거나, "
                           "빈 칸으로 검색하면 전체가 나옵니다.",
                 font=("맑은 고딕", 9), fg="#666", wraplength=520,
                 justify="left").pack(anchor="w", padx=12)

        lb = tk.Listbox(win, font=FONT, height=16)
        lb.pack(fill="both", expand=True, padx=12, pady=8)
        info = tk.Label(win, text="", font=("맑은 고딕", 9), fg="#444",
                        wraplength=520, justify="left", anchor="w")
        info.pack(fill="x", padx=12)

        found = []

        def do_search():
            lb.delete(0, "end")
            info.config(text="찾는 중...")
            q = ent.get().strip()

            def work():
                try:
                    vs = engine.search_voices(self.client, q) if q \
                        else engine.all_voices(self.client)
                except Exception as e:
                    self.root.after(0, lambda: info.config(text=f"검색 실패: {e}"))
                    return
                found.clear()
                found.extend(vs)
                def fill():
                    for v in vs:
                        kor, eng = engine.vname(v)
                        nm = f"{kor} ({eng})" if kor else eng
                        lb.insert("end", f"{nm}   [{v.gender or '?'}/{v.age or '?'}]")
                    info.config(text=f"{len(vs)}개 찾음. 하나를 고르면 지원 감정이 보입니다.")
                self.root.after(0, fill)

            threading.Thread(target=work, daemon=True).start()

        def on_select(_=None):
            if not lb.curselection():
                return
            v = found[lb.curselection()[0]]
            emo = engine.vemotions(v)
            info.config(text=f"감정 {len(emo)}종: {', '.join(sorted(emo)) or '(ssfm-v30 미지원)'}")

        def confirm():
            if not lb.curselection():
                messagebox.showinfo("안내", "목소리를 하나 고르세요.", parent=win)
                return
            v = found[lb.curselection()[0]]
            if not engine.vemotions(v):
                messagebox.showwarning("안내",
                    "이 목소리는 ssfm-v30 모델을 지원하지 않습니다.", parent=win)
                return
            engine.VOICES[role] = v.voice_id
            try:
                engine.load_profile(self.client, role)
            except Exception as e:
                messagebox.showerror("오류", str(e), parent=win)
                return
            kor, eng = engine.vname(v)
            self._set_voice_label(role, f"{kor} ({eng})" if kor else eng)
            engine.VOICE_FILE.write_text(
                json.dumps(engine.VOICES, ensure_ascii=False, indent=2), encoding="utf-8")
            self.say(f"🎙 {engine.LABEL[role]} → {kor or eng}")
            win.destroy()

        tk.Button(sf, text="검색", font=FONT, command=do_search).pack(side="left")
        ent.bind("<Return>", lambda e: do_search())
        lb.bind("<<ListboxSelect>>", on_select)
        lb.bind("<Double-Button-1>", lambda e: confirm())

        bf = tk.Frame(win, pady=10)
        bf.pack()
        tk.Button(bf, text="이 목소리로 결정", font=FONT_B, bg="#0066cc", fg="white",
                  padx=16, command=confirm).pack(side="left", padx=5)
        tk.Button(bf, text="닫기", font=FONT, command=win.destroy).pack(side="left")
        do_search()

    # ── 표 ────────────────────────────────────────────────
    def build_table(self):
        for w in self.table.winfo_children():
            w.destroy()
        self.rows = []
        for i, ln in enumerate(self.lines):
            self.rows.append(self._make_row(i, ln))
        self.refresh_emotions()

    def _make_row(self, i, ln):
        f = tk.Frame(self.table)
        f.pack(fill="x", pady=1)
        r = {}

        tk.Label(f, text=str(i + 1), font=FONT, width=3, anchor="w").pack(side="left")

        r["speaker"] = ttk.Combobox(f, values=["narr", "cat"], width=6,
                                    font=FONT, state="readonly")
        r["speaker"].set(ln["speaker"])
        r["speaker"].pack(side="left")
        r["speaker"].bind("<<ComboboxSelected>>",
                          lambda e, idx=i: self.on_speaker_change(idx))

        for key, w in [("start", 5), ("slot", 5)]:
            e = tk.Entry(f, font=FONT, width=w, justify="right")
            e.insert(0, f"{ln[key]:.2f}")
            e.pack(side="left", padx=(4, 6))
            r[key] = e

        r["emotion"] = ttk.Combobox(f, width=10, font=FONT, state="readonly")
        r["emotion"].pack(side="left", padx=(0, 4))

        e = tk.Entry(f, font=FONT, width=4, justify="right")
        e.insert(0, f"{ln['intensity']:.1f}")
        e.pack(side="left", padx=(4, 6))
        r["intensity"] = e

        e = tk.Entry(f, font=FONT, width=44)
        e.insert(0, ln["text"])
        e.pack(side="left", padx=(0, 4))
        r["text"] = e

        r["result"] = tk.Label(f, text="-", font=("Consolas", 9), width=10,
                               anchor="w", fg="#888")
        r["result"].pack(side="left")

        tk.Button(f, text="▶", font=FONT, width=2,
                  command=lambda idx=i: self.play(idx)).pack(side="left", padx=1)
        tk.Button(f, text="생성", font=FONT,
                  command=lambda idx=i: self.gen_one(idx)).pack(side="left", padx=1)
        tk.Button(f, text="✕", font=FONT, width=2, fg="#cc0000",
                  command=lambda idx=i: self.del_line(idx)).pack(side="left")
        return r

    def on_speaker_change(self, i):
        self.refresh_emotions()

    def refresh_emotions(self):
        """줄마다 그 화자의 목소리가 지원하는 감정만 보여준다."""
        for i, r in enumerate(self.rows):
            role = r["speaker"].get()
            emo = sorted(engine.PROFILE.get(role, {}).get("emotions", []))
            cur = r["emotion"].get() or self.lines[i].get("emotion", "normal")
            if not emo:
                r["emotion"]["values"] = [cur]
                r["emotion"].set(cur)
                continue
            r["emotion"]["values"] = emo
            if cur in emo:
                r["emotion"].set(cur)
            else:
                fallback = "normal" if "normal" in emo else emo[0]
                r["emotion"].set(fallback)
                if cur:
                    self.say(f"  {i+1}번: '{cur}' 미지원 → '{fallback}' 으로 변경")

    def collect(self):
        """화면 값을 읽어 self.lines 를 갱신. 숫자 오류는 알려준다."""
        out = []
        for i, r in enumerate(self.rows):
            try:
                start = float(r["start"].get())
                slot = float(r["slot"].get())
                inten = float(r["intensity"].get())
            except ValueError:
                messagebox.showerror("입력 오류",
                                     f"{i+1}번 줄의 숫자를 확인하세요.")
                return None
            text = r["text"].get().strip()
            if not text:
                messagebox.showerror("입력 오류", f"{i+1}번 줄 대사가 비었습니다.")
                return None
            out.append({"speaker": r["speaker"].get(), "start": start, "slot": slot,
                        "emotion": r["emotion"].get(), "intensity": inten,
                        "text": text,
                        "duration": self.lines[i].get("duration") if i < len(self.lines) else None})
        self.lines = out
        return out

    def add_line(self):
        if self.collect() is None:
            return
        last = self.lines[-1] if self.lines else {"start": 0, "slot": 1}
        self.lines.append({"speaker": "narr", "start": round(last["start"] + last["slot"] + 0.1, 2),
                           "slot": 1.5, "emotion": "normal", "intensity": 1.0,
                           "text": "새 대사", "duration": None})
        self.build_table()

    def del_line(self, i):
        if self.collect() is None:
            return
        if len(self.lines) <= 1:
            messagebox.showinfo("안내", "최소 한 줄은 있어야 합니다.")
            return
        del self.lines[i]
        self.build_table()

    def check_timeline(self):
        if self.collect() is None:
            return
        msgs, ok = [], True
        s = sorted(enumerate(self.lines), key=lambda x: x[1]["start"])
        for (ia, a), (ib, b) in zip(s, s[1:]):
            if a["start"] + a["slot"] > b["start"] + 0.01:
                msgs.append(f"{ia+1}번({a['start']+a['slot']:.2f}s 종료) ↔ "
                            f"{ib+1}번({b['start']:.2f}s 시작) 겹침")
                ok = False
        end = max(l["start"] + l["slot"] for l in self.lines)
        self.say("── 타임라인 점검 ──")
        for m in msgs:
            self.say("  ⚠️ " + m)
        self.say(f"  대사 {len(self.lines)}개, 마지막 종료 {end:.2f}s"
                 + ("  ✅ 겹침 없음" if ok else ""))

    # ── 생성 ──────────────────────────────────────────────
    def _ready(self):
        if self.busy:
            messagebox.showinfo("안내", "생성이 진행 중입니다.")
            return False
        if not self.client:
            messagebox.showwarning("잠깐", "타입캐스트에 연결되지 않았습니다.")
            return False
        for role in ("narr", "cat"):
            if role in {l["speaker"] for l in self.lines} and not engine.VOICES.get(role):
                messagebox.showwarning("잠깐",
                    f"{engine.LABEL[role]} 목소리를 먼저 고르세요.")
                return False
        return True

    def gen_one(self, i):
        if self.collect() is None or not self._ready():
            return
        self._run([i])

    def gen_all(self):
        if self.collect() is None or not self._ready():
            return
        self._run(list(range(len(self.lines))))

    def _run(self, idxs):
        self.busy = True
        self.btn_all.config(state="disabled", text="생성 중...")
        engine.OUTDIR.mkdir(exist_ok=True)

        def work():
            done = 0
            for i in idxs:
                ln = self.lines[i]
                role = ln["speaker"]
                self.root.after(0, lambda r=self.rows[i]: r["result"].config(
                    text="생성 중", fg="#0066cc"))
                try:
                    path, dur, words = engine.fit_line(
                        self.client, i + 1, role, ln["slot"],
                        ln["emotion"], ln["intensity"], ln["text"])
                    ln["duration"] = dur
                    ln["words"] = [{"text": w.text, "start": w.start, "end": w.end}
                                   for w in words]
                    fit = dur <= ln["slot"] + engine.TOL
                    self.say(f"  [{i+1}] {dur:.2f}s / 슬롯 {ln['slot']:.2f}s "
                             + ("✅" if fit else "⚠️ 초과"))
                    self.root.after(0, lambda r=self.rows[i], d=dur, f=fit:
                                    r["result"].config(
                                        text=f"{d:.2f}s " + ("✓" if f else "✗"),
                                        fg="#009900" if f else "#cc6600"))
                    done += 1
                except Exception as e:
                    self.say(f"  ❌ [{i+1}] 실패: {e}")
                    self.root.after(0, lambda r=self.rows[i]: r["result"].config(
                        text="실패", fg="#cc0000"))
            self.save_script()
            self.write_outputs()
            self.say(f"── {done}/{len(idxs)}개 생성 완료 ──")
            self.root.after(0, lambda: self.btn_all.config(
                state="normal", text="전체 생성"))
            self.busy = False

        threading.Thread(target=work, daemon=True).start()

    def write_outputs(self):
        """타임라인.json 과 자막.srt 를 남긴다 (합성에 쓰임)."""
        meta, srt = [], []
        for i, ln in enumerate(self.lines):
            if not ln.get("duration"):
                continue
            meta.append({"id": i + 1, "speaker": ln["speaker"],
                         "voice_id": engine.VOICES.get(ln["speaker"], ""),
                         "emotion": ln["emotion"], "start": ln["start"],
                         "slot": ln["slot"], "duration": round(ln["duration"], 3),
                         "text": ln["text"]})
            W = type("W", (), {})
            ws = []
            for w in ln.get("words", []):
                o = W(); o.text, o.start, o.end = w["text"], w["start"], w["end"]
                ws.append(o)
            srt.append((ln["start"], ln["duration"], ln["text"], ws))
        if meta:
            json.dump(meta, open("타임라인.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            engine.build_srt(srt, "자막.srt")
            self.say("  타임라인.json / 자막.srt 갱신")

    def play(self, i):
        p = engine.OUTDIR / f"{i+1:02d}_{self.lines[i]['speaker']}.wav"
        if not p.exists():
            messagebox.showinfo("안내", "아직 생성되지 않았습니다. '생성'을 먼저 누르세요.")
            return
        if CAN_PLAY:
            winsound.PlaySound(str(p), winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            subprocess.Popen(["start", "", str(p)], shell=True)

    # ── 합성 ──────────────────────────────────────────────
    def do_mux(self):
        if self.collect() is None:
            return
        ready = [(i, l) for i, l in enumerate(self.lines) if l.get("duration")]
        if not ready:
            messagebox.showinfo("안내", "먼저 음성을 생성하세요.")
            return
        if subprocess.run("ffmpeg -version", shell=True,
                          capture_output=True).returncode != 0:
            messagebox.showwarning(
                "ffmpeg 없음",
                "이 컴퓨터에 ffmpeg 이 없어 합성을 못 합니다.\n\n"
                "음성과 타임라인.json 은 만들어졌으니\n"
                "Claude 에게 '음성 다 뽑았어' 라고 하시면 대신 합성해 드립니다.")
            return

        video = VIDEO_DEFAULT if Path(VIDEO_DEFAULT).exists() else filedialog.askopenfilename(
            title="영상 고르기", filetypes=[("영상", "*.mp4")])
        if not video:
            return
        out = filedialog.asksaveasfilename(
            title="저장할 이름", defaultextension=".mp4",
            initialfile="완성본.mp4", filetypes=[("영상", "*.mp4")])
        if not out:
            return

        def work():
            try:
                items = [(engine.OUTDIR / f"{i+1:02d}_{l['speaker']}.wav", l["start"])
                         for i, l in ready]
                engine.mux(video, items, out)
                self.say(f"✅ 합성 완료: {out}")
                self.root.after(0, lambda: messagebox.showinfo("완료", f"저장했습니다.\n{out}"))
            except Exception as e:
                self.say(f"❌ 합성 실패: {e}")
        threading.Thread(target=work, daemon=True).start()

    # ── 대본 저장/불러오기 ────────────────────────────────
    def save_script(self):
        if self.rows and self.collect() is None:
            return
        try:
            SCRIPT_FILE.write_text(
                json.dumps(self.lines, ensure_ascii=False, indent=2), encoding="utf-8")
            self.say(f"  대본.json 저장 ({len(self.lines)}줄)")
        except Exception as e:
            self.say(f"  저장 실패: {e}")

    def load_script(self):
        if SCRIPT_FILE.exists():
            try:
                self.lines = json.loads(SCRIPT_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.lines = [dict(l) for l in DEFAULT_LINES]
        else:
            self.lines = [dict(l) for l in DEFAULT_LINES]
        self.build_table()


def main():
    root = tk.Tk()
    try:
        App(root)
    except Exception:
        import traceback
        tb = traceback.format_exc()
        Path("오류기록.txt").write_text(tb, encoding="utf-8")
        messagebox.showerror(
            "시작 실패",
            "편집기를 여는 중 문제가 생겼습니다.\n\n"
            "같은 폴더에 오류기록.txt 를 남겼습니다.\n"
            "그 내용을 Claude 에게 보여주시면 고쳐드립니다.\n\n"
            + tb[-500:])
        return
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        Path("오류기록.txt").write_text(traceback.format_exc(), encoding="utf-8")
        print(traceback.format_exc())
        input("\n오류가 났습니다. 오류기록.txt 를 Claude 에게 보여주세요. Enter 로 닫기...")
