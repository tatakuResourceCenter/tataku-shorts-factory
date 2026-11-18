# 타타쿠 쇼츠 제작 도구

유튜브 쇼츠를 만들면서 쌓아가는 도구와 기록.
영상에 타입캐스트 AI 음성을 **박자에 맞춰** 얹는 일을 자동화한다.

> 손으로 하면 음성 길이를 재고, 타임라인에 끌어다 놓고, 또 길어서 다시 뽑고를 반복해야 한다.
> 여기 있는 도구는 "이 대사는 2.8초 안에 들어가야 한다"만 적어두면 나머지를 알아서 맞춘다.

## 무엇이 들어있나

| 경로 | 설명 |
|---|---|
| `skills/shorts-tts/` | 음성 생성 엔진과 대본 편집기 |
| `docs/` | 타입캐스트 API 사용법, 쇼츠 편집 공식 |
| `tools/` | 윈도우용 실행 파일 |
| `CHANGELOG.md` | **발전 기록** — 날짜별로 새로 알아낸 것 |

## 어떻게 동작하나

```
대본 (대사 + 시작 시각 + 허용 길이 + 감정)
   │
   ├─ 타입캐스트 API 로 한 줄씩 생성
   │     └─ 길이가 넘치면 audio_tempo 보정해서 재생성 (최대 3회)
   │
   ├─ 단어 타임스탬프로 자막(.srt) 생성
   │
   └─ ffmpeg adelay 로 지정한 초에 정확히 배치 → 영상 합성
```

핵심은 **음성을 억지로 늘리거나 줄이지 않는다**는 점이다.
`audio_tempo` 는 0.88~1.22 범위로만 건드리고, 그래도 안 들어가면
"대사를 줄이세요"라고 알려준다. 그 밖으로 나가면 사람 귀에 어색하게 들린다.

## 시작하기

```bash
pip install typecast-python
set TYPECAST_API_KEY=발급받은_키        # Windows
export TYPECAST_API_KEY=발급받은_키      # macOS / Linux
```

API 키는 [타입캐스트 개발자 콘솔](https://studio.typecast.ai/developers/api)에서 발급한다.
**웹 구독과 API 플랜은 별개**라서 웹만 결제했다면 API는 따로 열어야 한다.

### GUI 로 쓰기 (권장)

```bash
python skills/shorts-tts/대본편집기.py
```

대사·감정·타이밍을 표에서 고치고, 줄 단위로 생성해 바로 들어볼 수 있다.
그 목소리가 지원하는 감정만 드롭다운에 뜨므로 틀릴 수가 없다.

### 명령줄로 쓰기

```bash
python skills/shorts-tts/shorts_tts.py --check            # 플랜·크레딧 확인
python skills/shorts-tts/shorts_tts.py --list 문정 아찌     # 목소리를 한글 이름으로 검색
python skills/shorts-tts/shorts_tts.py --dry-run          # 타임라인 겹침 점검
python skills/shorts-tts/shorts_tts.py --voices-only      # 음성·자막만 (ffmpeg 불필요)
python skills/shorts-tts/shorts_tts.py --video 영상.mp4 --out 완성본.mp4
```

## 주의

- `apikey.txt` 는 `.gitignore` 에 들어있다. **API 키를 커밋하지 말 것.**
- 남의 영상을 쓸 때는 원작자 허락을 받고 출처를 남긴다.
- 원본에 깔린 음악은 저작권 문제가 되므로 음소거하고 안전한 BGM 을 새로 깐다.

## 라이선스

개인 채널 운영용. 자유롭게 참고해도 좋다.
