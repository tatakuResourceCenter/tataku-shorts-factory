# 타입캐스트 API 정리

2026-11-18 기준. 실제로 부딪히며 알아낸 것 위주.

## 설치와 인증

```bash
pip install typecast-python
```

```python
from typecast import Typecast

client = Typecast(
    api_key="...",
    source="api-page",          # 이 연동을 안내한 진입 경로
    generated_by="claude-code",  # 연동 코드를 작성한 에이전트
)
```

`source` 와 `generated_by` 는 타입캐스트가 요구하는 attribution 이다.
사용자명·이메일·프로젝트명·API 키·호스트는 넣지 않는다.

### 403 이 뜨는 이유

| 원인 | 해결 |
|---|---|
| 구 Starter 키 | 현재 SSFM API 와 호환되지 않는다. 콘솔에서 새로 발급 |
| **웹 구독만 있음** | 웹 플랜과 API 플랜은 별개다. API 플랜을 따로 열어야 한다 |
| 키에 공백 | 복사할 때 앞뒤 공백이 섞인 경우 |
| 계정 휴면 | 콘솔에서 상태 확인 |

## 목소리 찾기

목소리 이름은 **한글과 영문이 둘 다** 들어있다. 한글로 검색할 수 있다.

```python
for v in client.voices_v3():
    print(v.voice_name.kor, v.voice_name.eng, v.voice_id)
    # 문정 Moonjung tc_68f9c6a7...
```

자연어로 추천받을 수도 있다.

```python
client.recommend_voices("시크하고 나른한 저음의 한국어 목소리", count=5)
```

웹 스튜디오에서 쓰던 즐겨찾기 목소리도 대체로 API 목록에 있다.
다만 보장되지는 않으므로 이름으로 검색해 확인할 것.

## 감정은 목소리마다 다르다

**이게 제일 많이 걸린 함정이다.**

API 전체가 아는 감정은 20종이다.

```
normal, sad, happy, angry, regret, urgent, whisper, scream, shout,
trustful, soft, cold, sarcasm, inspire, cute, cheer, casual,
tonemid, toneup, tonedown
```

그런데 **목소리마다 지원하는 부분집합이 다르다.** 어떤 목소리는 7종만 된다.
전체 목록에 있다고 쓰면 이런 오류가 난다.

```json
{"error_code":"EMOTION_NOT_SUPPORTED",
 "message":"Voice 'tc_...' does not support emotion 'cold'.
            Supported emotions: ['normal','happy','sad','angry',
                                 'tonedown','toneup','whisper']"}
```

그러니 쓰기 전에 조회한다.

```python
v = client.voice_v3(voice_id)
for m in v.models:
    if m.version.value == "ssfm-v30":
        supported = set(m.emotions)
```

**대처법:** 감정을 하나로 못 박지 말고 선호 순서로 적어두고,
그 목소리가 지원하는 첫 번째를 고른다.

```python
["cold", "tonedown", "normal"]   # cold 안 되면 tonedown, 그것도 안 되면 normal
["sarcasm", "happy", "toneup"]
```

## 길이를 정확히 맞추기

`text_to_speech_with_timestamps` 가 오디오·실제 길이·단어 타이밍을 한 번에 준다.

```python
res = client.text_to_speech_with_timestamps(req, granularity="word")
audio = base64.b64decode(res.audio)   # base64 로 온다
dur   = res.audio_duration            # 초
words = res.words                     # .text / .start / .end
```

`audio_duration` 이 돌아오는 덕분에 **생성 → 측정 → 보정 → 재생성** 루프가 가능하다.

```python
if dur > slot:
    tempo = tempo * (dur / slot)      # 0.88 ~ 1.22 로 제한
```

### Output 설정에서 중요한 것

| 필드 | 쓰임 |
|---|---|
| `audio_tempo` | 속도. 음정은 변하지 않는다 |
| `remove_silence_ms` | **앞뒤 무음 제거.** 0 으로 두면 시작점 오차가 사라진다 |
| `target_lufs` | 음량 통일. -16 이 무난하다 |
| `audio_format` | `wav` 로 받아야 후처리가 편하다 |

`remove_silence_ms` 를 쓰지 않으면 TTS 앞에 붙은 무음 때문에
"0.2초에 배치"해도 실제 소리는 0.4초쯤 나온다.

## 체감 속도

한국어를 **5.6자/초** 로 잡고 슬롯을 설계했는데 실제로는 더 빨랐다.
9줄 중 8줄이 보정 없이 통과했고, 모두 슬롯보다 짧게 나왔다.

넘치는 것보다 짧은 쪽이 훨씬 낫다. 남는 시간은 여백으로 두면 된다.
슬롯은 예상보다 20~30% 넉넉히 잡는 편을 권한다.
