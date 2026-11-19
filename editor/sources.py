#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
클립 수첩 — 링크에서 출처(작성자)를 찾아 기록하고, 받은 영상과 연결한다.

  · 유튜브 / 틱톡: 공식 oEmbed (키 없이 공개 정보만)
  · 인스타그램: 공식 oEmbed 가 막혀 있어 공개 페이지의 og 태그로 시도, 실패하면 직접 입력
  · 윈도우 클립보드 감시: 지원 링크를 복사하면 자동으로 수첩에 추가
  · 다운로드 폴더에서 링크를 기록한 뒤 새로 생긴 영상을 찾아 연결 후보로 제시
"""

import os
import re
import json
import time
import html
import shutil
import threading
import urllib.parse
import urllib.request
from pathlib import Path

UA_BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
UA_CRAWLER = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
PLATFORM_LABEL = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram"}


# ── 링크 판별 ───────────────────────────────────────────
def platform_of(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    if host.endswith("youtube.com") or host.endswith("youtu.be"):
        return "youtube"
    if host.endswith("tiktok.com"):
        return "tiktok"
    if host.endswith("instagram.com"):
        return "instagram"
    return None


def extract_links(text):
    """복사한 글에서 지원하는 영상 링크만 뽑는다."""
    out = []
    for u in URL_RE.findall(text or ""):
        u = u.rstrip(").,]}>")
        if platform_of(u) and looks_like_video(u):
            out.append(u)
    return out


def looks_like_video(url):
    p = urllib.parse.urlparse(url)
    path = p.path.lower()
    pf = platform_of(url)
    if pf == "youtube":
        return "/shorts/" in path or path.startswith("/watch") or p.netloc.lower().endswith("youtu.be")
    if pf == "tiktok":
        return "/video/" in path or p.netloc.lower().startswith(("vm.", "vt.")) or "/t/" in path
    if pf == "instagram":
        return any(k in path for k in ("/reel/", "/reels/", "/p/", "/tv/"))
    return False


def clean_url(url):
    """추적용 파라미터를 떼고 비교하기 쉽게 정리."""
    p = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(p.query)
    keep = {k: v for k, v in q.items() if k in ("v",)}
    return urllib.parse.urlunparse((p.scheme, p.netloc, p.path.rstrip("/"), "",
                                    urllib.parse.urlencode(keep, doseq=True), ""))


def handle_from_url(url):
    """주소 안에 아이디가 들어 있으면 네트워크 없이 바로 쓴다."""
    p = urllib.parse.urlparse(url)
    parts = [s for s in p.path.split("/") if s]
    pf = platform_of(url)
    if pf == "tiktok" and parts and parts[0].startswith("@"):
        return parts[0][1:]
    if pf == "instagram" and len(parts) >= 3 and parts[1] in ("reel", "reels", "p", "tv"):
        return parts[0]
    if pf == "youtube" and parts and parts[0].startswith("@"):
        return parts[0][1:]
    return ""


# ── 네트워크 ────────────────────────────────────────────
def http_get(url, ua=UA_BROWSER, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "ko,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.geturl(), r.read(600_000).decode("utf-8", "replace")


def oembed(endpoint, url):
    _, body = http_get(f"{endpoint}?url={urllib.parse.quote(url, safe='')}&format=json")
    return json.loads(body)


def meta(html_text, prop):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']*)' % re.escape(prop),
                  html_text, re.I)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']%s["\']' % re.escape(prop),
                      html_text, re.I)
    return html.unescape(m.group(1)) if m else ""


def lookup(url):
    """링크 하나의 출처 정보. 실패해도 예외 대신 status 로 알려준다."""
    pf = platform_of(url)
    info = {"platform": pf, "handle": handle_from_url(url), "name": "", "title": "", "hint": "",
            "thumb": "", "author_url": "", "status": "need", "note": ""}
    try:
        if pf == "youtube":
            d = oembed("https://www.youtube.com/oembed", url)
            info.update(name=d.get("author_name", ""), title=d.get("title", ""),
                        thumb=d.get("thumbnail_url", ""), author_url=d.get("author_url", ""))
            m = re.search(r"youtube\.com/@([^/?#]+)", info["author_url"])
            if m:
                info["handle"] = urllib.parse.unquote(m.group(1))
        elif pf == "tiktok":
            final = url
            if not handle_from_url(url):            # vm.tiktok.com 같은 짧은 주소는 먼저 풀기
                final, _ = http_get(url)
                info["handle"] = handle_from_url(final) or info["handle"]
            d = oembed("https://www.tiktok.com/oembed", final)
            info.update(name=d.get("author_name", ""), title=d.get("title", ""),
                        thumb=d.get("thumbnail_url", ""), author_url=d.get("author_url", ""))
            info["handle"] = d.get("author_unique_id") or info["handle"]
        elif pf == "instagram":
            _, page = http_get(url, ua=UA_CRAWLER)
            title, desc = meta(page, "og:title"), meta(page, "og:description")
            info["thumb"] = meta(page, "og:image")
            info["title"] = title
            if not info["handle"]:
                for pat in (r"\(@([A-Za-z0-9._]{1,30})\)", r"@([A-Za-z0-9._]{1,30})",
                            r"-\s+([A-Za-z0-9._]{1,30})\s+(?:on|님)",
                            r"^([A-Za-z0-9._]{1,30})\s+on Instagram"):
                    m = re.search(pat, title) or re.search(pat, desc)
                    if m:
                        info["handle"] = m.group(1)
                        break
            m = re.match(r"^(.+?)\s*\(@", title)
            info["name"] = m.group(1).strip() if m else ""
            h, n = who_from_title(title)              # 프로필 이름일 수 있어서 확정하지 않고 힌트로만
            info["hint"] = h or n
    except Exception as e:
        info["note"] = f"자동 확인 실패: {type(e).__name__}"
    info["status"] = "ok" if info["handle"] or info["name"] else "need"
    return info


SITE_HINTS = {
    "tiktok": ("snaptik", "ssstik", "tiktok", "musicaldown", "tikmate", "snaptik.app"),
    "instagram": ("saveclip", "snapinsta", "instagram", "igram", "fastdl", "insta"),
    "youtube": ("youtube", "4k video", "4kvideo", "y2mate", "savefrom"),
}


def video_id(url):
    """링크 속 영상 번호 (파일 이름과 맞춰 보는 용도)."""
    p = urllib.parse.urlparse(url)
    pf = platform_of(url)
    path = p.path
    if pf == "youtube":
        if p.netloc.lower().endswith("youtu.be"):
            return path.strip("/").split("/")[0]
        m = re.search(r"/shorts/([\w-]{6,})", path)
        if m:
            return m.group(1)
        return (urllib.parse.parse_qs(p.query).get("v") or [""])[0]
    if pf == "tiktok":
        m = re.search(r"/video/(\d{8,})", path)
        return m.group(1) if m else ""
    if pf == "instagram":
        m = re.search(r"/(?:reel|reels|p|tv)/([\w-]{5,})", path)
        return m.group(1) if m else ""
    return ""


def _norm(s):
    return re.sub(r"[\W_]+", "", (s or "").lower())


def match_score(entry, filename):
    """이 파일이 이 링크의 영상일 가능성. None 이면 후보에서 제외."""
    name = filename.lower()
    score = 0
    vid = video_id(entry["url"])
    if vid and vid.lower() in name:
        score += 100
    hint = next((pf for pf, keys in SITE_HINTS.items() if any(k in name for k in keys)), None)
    if hint:
        if hint != entry["platform"] and score < 100:
            return None
        if hint == entry["platform"]:
            score += 40
    if entry["platform"] == "youtube" and entry.get("title"):
        t, f = _norm(entry["title"]), _norm(Path(filename).stem)
        if t and f and (t[:12] in f or f[:12] in t):
            score += 30
    return score


def credit_text(entry):
    """화면 오른쪽 아래에 얹을 짧은 출처."""
    h = entry.get("handle") or ""
    return f"@{h}" if h else (entry.get("name") or "")


def who_from_title(title):
    """'Instagram의 Daisy_Lanjai_Ollie님 : "…"' 처럼 제목에 적힌 '의 ○○님' 사이 글자를 꺼낸다.
    영문·숫자·_·. 로만 되어 있으면 아이디(handle), 한글·이모지가 섞이면 이름(name)으로 돌려준다."""
    t = (title or "").strip()
    m = (re.match(r"^\s*(?:Instagram|인스타그램|TikTok|틱톡)\s*의\s*(.+?)\s*님\s*[:：]", t)
         or re.match(r"^\s*(?:Instagram|인스타그램|TikTok|틱톡)\s*의\s*(.+?)\s*님", t)
         or re.match(r"^\s*(.+?)\s+on\s+(?:Instagram|TikTok)\s*[:：]", t))
    if not m:
        return "", ""
    who = m.group(1).strip().lstrip("@")
    if re.fullmatch(r"[A-Za-z0-9._]{1,30}", who):
        return who, ""
    return "", who


# ── 수첩 ────────────────────────────────────────────────
class Notebook:
    def __init__(self, path, clips_dir, log=print):
        self.path = Path(path)
        self.clips = Path(clips_dir)
        self.log = log
        self.lock = threading.Lock()
        self.entries = self._load()
        fixed = 0
        for e in self.entries:
            h, n = who_from_title(e.get("title"))
            e.setdefault("hint", h or n)
            # 지난 버전이 제목의 '의 ○○님'을 아이디로 확정해 버린 것 → 직접 확인하도록 되돌림
            if not e.get("manual") and (h or n) and (e.get("handle"), e.get("name")) == (h, n):
                e["handle"], e["name"], e["status"] = "", "", "need"
                fixed += 1
        if fixed:
            self.save()
        self.watching = os.name == "nt"
        self._seq = None

    def _load(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def save(self):
        with self.lock:
            self.path.write_text(json.dumps(self.entries, ensure_ascii=False, indent=2), encoding="utf-8")

    def find(self, eid):
        return next((e for e in self.entries if e["id"] == eid), None)

    def add(self, url, via="붙여넣기"):
        url = url.strip()
        if not platform_of(url) or not looks_like_video(url):
            raise ValueError("인스타그램 · 틱톡 · 유튜브 영상 링크만 넣을 수 있어요")
        key = clean_url(url)
        for e in self.entries:
            if clean_url(e["url"]) == key:
                return e, False
        e = {"id": f"s{int(time.time()*1000)}", "url": url, "platform": platform_of(url),
             "handle": handle_from_url(url), "name": "", "title": "", "thumb": "", "author_url": "",
             "status": "checking", "note": "", "added": time.time(), "file": "", "via": via}
        with self.lock:
            self.entries.insert(0, e)
        self.save()
        self.log(f"🔗 {PLATFORM_LABEL[e['platform']]} 링크 기록 ({via})")
        threading.Thread(target=self._resolve, args=(e["id"],), daemon=True).start()
        return e, True

    def _resolve(self, eid):
        e = self.find(eid)
        if not e:
            return
        info = lookup(e["url"])
        with self.lock:
            for k, v in info.items():
                if e.get("manual") and k in ("handle", "name", "status"):
                    continue                           # 직접 넣은 아이디는 덮어쓰지 않음
                if v or k in ("status", "note"):
                    e[k] = v
        self.save()
        who = credit_text(e) or "작성자 미확인"
        self.log(f"   → {who}" + (f" ({e['note']})" if e.get("note") else ""))

    def update(self, eid, **kw):
        e = self.find(eid)
        if not e:
            raise ValueError("없는 항목이에요")
        if "handle" in kw:
            v = (kw.get("handle") or "").strip()
            m = re.search(r"(?:instagram\.com|tiktok\.com|youtube\.com)/@?([A-Za-z0-9._-]{1,40})", v)
            if m and m.group(1).lower() not in ("reel", "reels", "p", "tv", "watch", "shorts", "video"):
                v = m.group(1)
            v = v.strip().lstrip("@").strip("/")
            if re.fullmatch(r"[A-Za-z0-9._-]{1,40}", v):
                e["handle"], e["name"] = v, ""
            else:
                e["handle"], e["name"] = "", v
            e["manual"] = bool(v)
        e["status"] = "ok" if e.get("handle") or e.get("name") else "need"
        self.save()
        return e

    def delete(self, eid):
        with self.lock:
            self.entries = [e for e in self.entries if e["id"] != eid]
        self.save()

    def recheck(self, eid):
        e = self.find(eid)
        if e:
            e["status"] = "checking"
            threading.Thread(target=self._resolve, args=(eid,), daemon=True).start()

    # ── 받은 영상 찾기 ──
    def scan_dirs(self):
        home = Path.home()
        dirs = [home / "Downloads", home / "Videos", home / "Desktop"]
        vid = home / "Videos"
        if vid.exists():
            dirs += [p for p in vid.iterdir() if p.is_dir()]
        return [d for d in dirs if d.exists()]

    def new_videos(self):
        used = {e.get("file") for e in self.entries}
        out = []
        for d in self.scan_dirs():
            try:
                for p in d.iterdir():
                    if p.is_file() and p.suffix.lower() in VIDEO_EXT and p.name not in used:
                        out.append((p.stat().st_mtime, p))
            except OSError:
                continue
        return out

    def candidates(self):
        """
        링크를 기록한 뒤 새로 생긴 영상과 짝짓는다. 받은 순서만 믿지 않고 파일 이름 힌트를 쓴다.
          · 파일 이름에 그 영상 번호가 있으면 확실 (+100)
          · 다운로드 사이트 이름이 플랫폼과 맞으면 +40, 다른 플랫폼이면 후보에서 뺌
          · 유튜브는 4K Video Downloader 가 제목을 파일 이름으로 써서 제목 겹침으로 +30
        """
        vids = self.new_videos()
        now = time.time()
        pairs = []
        for e in self.entries:
            if e.get("file"):
                continue
            for t, p in vids:
                if t < e["added"] - 5:
                    continue
                sc = match_score(e, p.name)
                if sc is None:
                    continue
                pairs.append((sc, -(t - e["added"]), e["id"], t, p))
        pairs.sort(key=lambda x: (x[0], x[1]), reverse=True)

        best, used_e, used_p = {}, set(), set()
        for sc, _, eid, t, p in pairs:                 # 점수 높은 짝부터 하나씩 확정
            if eid in used_e or str(p) in used_p:
                continue
            best[eid] = (t, p)
            used_e.add(eid)
            used_p.add(str(p))

        res = {}
        for e in self.entries:
            if e["id"] not in best:
                continue
            t0, p0 = best[e["id"]]
            same = self.clips / p0.name                # 이미 clips 폴더에 같은 파일을 넣어 뒀으면 바로 연결
            try:
                if same.exists() and same.stat().st_size == p0.stat().st_size:
                    e["file"] = p0.name
                    self.save()
                    self.log(f"📎 {p0.name} ← {credit_text(e) or e['url']} (clips 폴더에 있던 파일과 연결)")
                    continue
            except OSError:
                pass
            alts = [(t, p) for sc, _, eid, t, p in pairs if eid == e["id"] and p != p0]
            res[e["id"]] = [{"path": str(p), "name": p.name, "ago": int(now - t), "size": p.stat().st_size}
                            for t, p in [(t0, p0)] + alts[:2]]
        return res

    def import_file(self, eid, path):
        e = self.find(eid)
        if not e:
            raise ValueError("없는 항목이에요")
        src = Path(path).resolve()
        allowed = [d.resolve() for d in self.scan_dirs()]
        if src.suffix.lower() not in VIDEO_EXT or not src.exists() or \
                not any(a == src.parent or a in src.parents for a in allowed):
            raise ValueError("다운로드 폴더의 영상만 가져올 수 있어요")
        base = re.sub(r"[^\w.-]+", "_", f"{e['platform']}_{e.get('handle') or e['id']}").strip("_")
        dst = self.clips / f"{base}{src.suffix.lower()}"
        n = 2
        while dst.exists():
            dst = self.clips / f"{base}_{n}{src.suffix.lower()}"
            n += 1
        shutil.move(str(src), str(dst))
        e["file"] = dst.name
        self.save()
        self.log(f"📎 {dst.name} ← {credit_text(e) or e['url']}")
        return e

    def attach_existing(self, eid, clip_name):
        e = self.find(eid)
        if not e:
            raise ValueError("없는 항목이에요")
        if not (self.clips / Path(clip_name).name).exists():
            raise ValueError("clips 폴더에 없는 파일이에요")
        name = Path(clip_name).name
        for o in self.entries:
            if o is not e and o.get("file") == name:
                o["file"] = ""
        e["file"] = name
        self.save()
        return e

    def by_file(self):
        return {e["file"]: e for e in self.entries if e.get("file")}

    # ── 클립보드 감시 (윈도우) ──
    def start_clipboard_watch(self):
        if os.name != "nt":
            return
        threading.Thread(target=self._watch, daemon=True).start()

    def _watch(self):
        import ctypes
        from ctypes import wintypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        CF_UNICODETEXT = 13

        def read():
            for _ in range(3):
                if user32.OpenClipboard(None):
                    break
                time.sleep(0.05)
            else:
                return ""
            try:
                h = user32.GetClipboardData(CF_UNICODETEXT)
                if not h:
                    return ""
                p = kernel32.GlobalLock(h)
                if not p:
                    return ""
                try:
                    return ctypes.wstring_at(p)[:4000]
                finally:
                    kernel32.GlobalUnlock(h)
            finally:
                user32.CloseClipboard()

        self._seq = user32.GetClipboardSequenceNumber()   # 켜기 전에 복사해 둔 건 건너뜀
        while True:
            time.sleep(0.8)
            try:
                seq = user32.GetClipboardSequenceNumber()
                if seq == self._seq:
                    continue
                self._seq = seq
                if not self.watching:
                    continue
                for link in extract_links(read()):
                    self.add(link, via="복사 감지")
            except Exception:
                continue
