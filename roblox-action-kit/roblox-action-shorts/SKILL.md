---
name: roblox-action-shorts
description: 로블록스 스튜디오(MCP 연결)에서 대사 없는 액션 쇼츠 장면을 자동으로 만든다. 경기장·캐릭터·슬로모 투사체 추적·폭발·정지+흑백·점수판 카드·카메라까지. "액션 쇼츠 만들어줘", "닌자 vs 총잡이 찍어줘", "전투 장면 만들어줘"라고 하면 사용한다.
---

# 로블록스 무대사 액션 쇼츠 만들기

사용자는 초보자다. 한국어로 짧게 말한다. 되묻는 건 최대 1번(주제만). 나머지는 기본값으로 바로 만든다.
**이 파일이 첨부만 되고 요청이 없어도 바로 시작한다.** 첫마디: "액션 쇼츠를 만들어 볼게요! 누구 vs 누구로 할까요? (그냥 Enter면 닌자 vs 총잡이)"

## 0. 연결 확인
- Roblox Studio MCP 도구(`list_roblox_studios`, `execute_luau`)가 있어야 한다. 없으면: "먼저 로블록스 스튜디오를 클로드에 연결해야 해요. 타타꾸패밀리 DAY 1 연결 키트를 쓰세요" 라고 안내하고 멈춘다.
- 웹 채팅처럼 도구가 없으면, 같은 폴더의 `PASTE_PROMPT_액션대본.txt` 방식(컷 리스트만 만들기)으로 바꿔서 도와준다.
- 시작 전에 한 줄 경고: "새 장면은 지도에서 멀리 떨어진 곳(6000, 50, 0)에 만들어서 원래 게임은 건드리지 않아요. 그래도 중요한 플레이스는 먼저 저장해 두세요."

## 1. 만드는 순서 (execute_luau 3~4번이면 끝)
1. **경기장 + 배우**: `build_arena.luau` 내용을 execute_luau(Edit)로 실행한다. 주제에 맞게 색만 바꾼다.
   - 팀은 **색으로 고정**: 주인공 밝은 색(청록), 악당 검정 + **빛나는 초록 눈**.
   - 사용자 아바타를 쓰고 싶다고 하면 `GetHumanoidDescriptionFromUserId`로 바꾼다.
2. **연출 엔진**: `ActionDirector.client.luau`를 StarterPlayer.StarterPlayerScripts에 LocalScript `ActionDirector`로 넣는다. `EDIT FROM HERE` 블록(ANIM, SLOW, SHOTS, EVENTS, END)만 주제에 맞게 고친다. 나머지 코드는 건드리지 않는다.
3. **(선택) 동작 만들기**: `generate_animation`으로 "backflip dodge", "throw kunai", "aim rifle" 같은 동작을 만들고 ANIM에 id를 넣은 뒤 EVENTS의 `pose`로 쓴다. 기본 id(idle/run/jump/fall)만으로도 장면은 돌아간다.
4. **점검**: ReplicatedStorage 속성 `LabStill`에 초(예: 3.9)를 넣고 Play → 그 시점에서 멈춘다. Server에서 값을 바꾸면 이어서 다음 시점으로 간다. 4~6장만 `screen_capture`로 본다. **끝나면 `LabStill`을 반드시 지운다**(안 지우면 영상이 멈춘다).
5. **넘기기**: "Ctrl+S로 저장하고 F5를 누르세요. 화면이 하얗게 번쩍인 뒤 장면이 시작돼요. OBS로 녹화하면 끝!" 세로 쇼츠는 녹화본을 9:16으로 자른다.

## 2. EVENTS 사전
| 이벤트 | 형식 | 효과 |
|---|---|---|
| card | `{t,"card","ROUND 1","0 : 0","NINJA WINS"}` | 파란 화면 점수판 카드(장 나누기) |
| uncard | `{t,"uncard"}` | 카드 끄기 |
| pose | `{t,"pose","Hero","idle"}` | ANIM 동작 재생 |
| aim | `{t,"aim","Villain",true/false}` | 오른팔을 앞으로 들어 조준 |
| move | `{t,"move","Hero",from,to,초,높이}` | 달리기(높이 0) / 점프 이동(높이>0). 좌표는 경기장 기준 |
| fire | `{t,"fire","Rocket","Villain","Hero",초,색}` | 투사체 발사. 이름에 Kunai/Arrow가 들어가면 작고 날렵하게, 아니면 로켓(불꽃) |
| explode | `{t,"explode",위치}` | 흰 섬광 → 불덩이 → 블록 조각 + 흔들림 |
| hit | `{t,"hit","Villain"}` | 빨간 X 히트마커 + 흔들림 |
| killfeed | `{t,"killfeed","NINJA","VILLAIN"}` / `{t,"killfeed"}` | 위쪽 처치 알림 바 (끄기는 이름 없이) |
| freeze | `{t,"freeze",초}` | 화면 정지 + 흑백 ("망했다" 순간) |
| knock | `{t,"knock","Villain",방향}` | 뒤로 날아가 쓰러짐 |

SHOTS: `{"at", t, 카메라위치, 보는곳(좌표 또는 배우이름), FOV, 밀기0~1, 롤각도}` / `{"follow", t, "Rocket", 오프셋, FOV}`(투사체 옆에 붙어 같이 날아감).
SLOW: `{시작, 끝, 배율}` 0.3이면 슬로모.

## 3. 연출 규칙 (인기 액션 쇼츠 123컷 분석 결과)
1. **사건 다음 컷은 무조건 반응 얼굴** 클로즈업(0.6~1.5초).
2. **원인 → 결과 순서 고정**: 조준(로우앵글) → 발사 → 투사체 추적(슬로모 0.2~0.35) → 명중(히트마커) → 정지+흑백 → 날아감 → 반응.
3. **강한 쪽은 서서 싸우지 않는다**: 점프로 피하고, 높은 곳(탑·난간)으로 올라가 내려다보며 공격한다.
4. **화려한 장면만 길게(3~6초), 나머지는 1~2초로 빠르게**. 같은 구도 2초 넘기지 않기.
5. **영웅 컷은 로우앵글 + 하늘(해)**, 악당 컷은 로우앵글 클로즈업 + 빛나는 눈.
6. **점수판 카드로 시작하고 끝낸다**: "ROUND 1 0:0" → … → "1:0 NINJA WINS". 시리즈면 다음 편을 같은 카드로 시작.
7. 카메라는 벽·상자 안에 넣지 않는다. 뒤통수 컷 금지 — 보는 사람 얼굴이 보이는 쪽에서 찍는다.

## 4. 문제 해결
- 영상이 하늘만 나와요 → `workspace.StreamingEnabled = false`.
- 팔이 안 올라가요 → 새 R15 리그는 AnimationConstraint라서 엔진이 자동으로 RigAttachment를 돌린다(aim 이벤트에 이미 들어 있음).
- 화면이 뿌옇게 흐려요 → 엔진이 DepthOfField를 꺼 준다. 다른 블러가 있으면 Lighting에서 끈다.
- 장면이 안 시작해요 → ReplicatedStorage 속성 `ActionScene`이 false인지, `LabStill`이 남아 있는지 확인.

만든 사람: 타타꾸패밀리 (YouTube @tata-ku)
