# 💥 로블록스 액션 쇼츠 키트 (DAY 2)

한 줄만 말하면 클로드가 로블록스 스튜디오에 **대사 없는 액션 장면**을 직접 만들어 줘요.
경기장 · 캐릭터 · 로켓 · 슬로모 추적 · 폭발 · 화면 정지+흑백 · 점수판 카드 · 카메라까지.
타타꾸패밀리 「AI로 로블록스 드라마 만들기 DAY 2」에서 소개한 키트예요.

## 📥 다운로드
👉 **[키트 한 번에 받기 (zip)](https://github.com/tatakuResourceCenter/tataku-shorts-factory/raw/main/roblox-action-kit/로블록스_액션쇼츠_키트.zip)**

> ❗ 실제로 장면을 만들려면 **로블록스 스튜디오가 클로드에 연결**돼 있어야 해요 → [DAY 1 연결 키트](../roblox-mcp-kit/)
> 연결이 어려우면 방법 2(붙여넣기)로 **컷 리스트(설계도)**를 먼저 받아 보세요.

## ⚡ 방법 1 — 스킬 설치 (자동으로 장면 만들기, 추천)
1. [`roblox-action-shorts.zip`](https://github.com/tatakuResourceCenter/tataku-shorts-factory/raw/main/roblox-action-kit/roblox-action-shorts.zip) 을 Claude **설정 → 기능(Capabilities) → 스킬 → 업로드** (Claude Code는 `~/.claude/skills/` 에 폴더째 복사)
2. 로블록스 스튜디오를 켜 두고 클로드에게: **"닌자 vs 총잡이 액션 쇼츠 만들어줘"**
3. 다 되면 **F5** → OBS로 녹화!

## 📝 방법 2 — 붙여넣기 (웹 채팅에서도 됨)
[`PASTE_PROMPT_액션대본.txt`](PASTE_PROMPT_액션대본.txt) 내용을 복사해서 클로드에 붙여넣기 → 주제만 쓰면 **대사 없이 이해되는 컷 리스트**가 나와요.

## 🎬 들어 있는 연출 (인기 액션 쇼츠 123컷 분석)
| 기법 | 하는 일 |
|---|---|
| 점수판 카드 | 파란 화면 + 빨간 숫자로 시작과 끝 |
| 투사체 추적 슬로모 | 로켓·쿠나이 옆에 카메라가 붙어 같이 날아가요 (0.3배) |
| 폭발 3단 | 흰 섬광 → 불덩이 → 블록 조각 + 화면 흔들림 |
| 정지 + 흑백 | 맞는 순간 화면을 멈추고 색을 빼요 |
| 색으로 팀 구분 | 악당은 검은 몸 + 빛나는 초록 눈 |
| 로우앵글 + 해 | 영웅이 탑으로 뛰어오르는 장면 |

## 파일
- `roblox-action-shorts/SKILL.md` — 스킬 설명서
- `roblox-action-shorts/build_arena.luau` — 경기장 + 배우 만들기
- `roblox-action-shorts/ActionDirector.client.luau` — 연출 엔진 (EDIT 블록만 고치면 새 장면)
- `PASTE_PROMPT_액션대본.txt` — 붙여넣기용 프롬프트

⚠️ 새 장면은 지도에서 멀리 떨어진 곳(6000, 50, 0)에 만들어져 원래 게임을 건드리지 않아요. 그래도 중요한 플레이스는 먼저 저장하세요.

만든 사람: 타타꾸패밀리 · YouTube @tata-ku
