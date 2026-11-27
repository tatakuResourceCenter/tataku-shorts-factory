# 🧱 Roblox Studio + Blender ↔ Claude MCP 연결 키트

로블록스 스튜디오와 블렌더를 **Claude(클로드)** 에 연결해서, 말로만 시켜도 집을 짓고 캐릭터를 세우고 카메라를 움직이게 만드는 키트예요.
타타꾸패밀리 「AI로 로블록스 드라마 만들기 DAY 1」 영상에서 소개한 그 방법입니다.

## ⚡ 방법 1 — 붙여넣기만 하면 끝 (추천)
1. [`PASTE_PROMPT_붙여넣기.txt`](PASTE_PROMPT_붙여넣기.txt) 내용을 **전부 복사**
2. Claude 데스크톱 앱 또는 Claude Code에 **붙여넣기**
3. 클로드가 알아서 확인하고 연결해 줘요. 손으로 해야 하는 클릭만 한 줄씩 알려 줘요.

## 🧩 방법 2 — 스킬로 설치 (계속 쓰고 싶을 때)
[`roblox-blender-mcp-setup`](roblox-blender-mcp-setup/) 폴더를 통째로 넣으세요.
- **Claude Code**: `~/.claude/skills/` (Windows: `C:\Users\<이름>\.claude\skills\`) 안에 복사
- **Claude 앱**: 폴더를 zip으로 묶어 설정 → 스킬에서 업로드

그다음 클로드에게 **"로블록스 연결해줘"** 라고만 말하면 돼요.

## 🖱️ 스튜디오에서 직접 하는 3단계
1. 로블록스 스튜디오 최신 버전 → **Assistant** 창
2. 오른쪽 위 **…** → **Manage MCP Servers** → **Enable Studio as MCP server** 켜기
3. **Quick connect** 에서 **Claude** 켜기

## 💡 첫날 겪은 문제 꿀팁
| 증상 | 해결 |
|---|---|
| 영상이 **하늘만** 나와요 | `Workspace.StreamingEnabled` 를 **끄기** |
| 카메라가 **벽 속**으로 들어가요 | 카메라 → 얼굴 사이에 막힌 게 없는지 레이캐스트로 검사 |

## 준비물
- 로블록스 스튜디오 (최신)
- Claude 데스크톱 앱 또는 Claude Code
- (선택) 블렌더 + [Blender MCP](https://github.com/ahujasid/blender-mcp)

## ⚠️ 주의
MCP로 연결하면 클로드가 열려 있는 로블록스 플레이스와 블렌더 파일을 **읽고 고칠 수 있어요.** 중요한 파일은 먼저 백업하세요.

---
출처: Roblox 공식 문서 *Connect to the Roblox Studio MCP server*, GitHub `ahujasid/blender-mcp` (2026-11 기준)
만든 사람: 타타꾸패밀리 · YouTube @tata-ku
