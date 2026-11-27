---
name: roblox-blender-mcp-setup
description: 클로드를 로블록스 스튜디오(MCP)와 블렌더(MCP)에 자동으로 연결한다. "로블록스 연결해줘", "블렌더 연결해줘", "MCP 세팅해줘"라고 하면 사용한다. Windows와 Mac 모두 지원.
---

# 로블록스 스튜디오 + 블렌더 MCP 자동 연결

사용자는 초보자다. 명령어를 직접 치게 하지 말고, 셸을 쓸 수 있으면 내가 직접 실행한다. 사용자가 손으로 해야 하는 단계는 클릭 위치까지 한 줄씩 알려 준다. 모든 안내는 한국어로, 짧게.

## 0. 먼저 확인할 것
1. 운영체제를 확인한다(Windows / macOS).
2. 내가 어떤 클로드인지 확인한다.
   - **Claude Code**(터미널에서 명령 실행 가능) → 1-A, 2-A로 자동 설정.
   - **Claude 데스크톱 앱** → 설정 파일(claude_desktop_config.json)을 편집해서 연결(1-B, 2-B). 파일을 고칠 수 없으면 사용자에게 붙여 넣을 내용을 정확히 준다.
3. 경고를 한 줄 알린다: "MCP로 연결하면 클로드가 열려 있는 로블록스 플레이스와 블렌더 파일을 읽고 고칠 수 있어요. 중요한 파일은 먼저 백업하세요."

## 1. 로블록스 스튜디오 연결
로블록스 스튜디오에는 MCP 서버가 기본으로 들어 있다. 별도 설치 파일은 필요 없다.

### 사용자가 스튜디오에서 할 일 (클릭 3번)
1. 로블록스 스튜디오를 최신 버전으로 업데이트하고 플레이스를 하나 연다.
2. **Assistant**(어시스턴트) 창을 연다 → 오른쪽 위 **…** → **Manage MCP Servers**(MCP 서버 관리).
3. **Enable Studio as MCP server**(Studio를 MCP 서버로 사용)를 켠다.
4. (데스크톱 앱이면 가장 쉬움) 같은 화면의 **Quick connect**(빠른 연결) 목록에서 **Claude Desktop** 또는 **Claude Code**를 켠다. 목록에 없으면 클로드를 설치한 뒤 스튜디오를 다시 켠다.

### 1-A. Claude Code에서 자동 등록 (빠른 연결이 안 될 때)
- Windows:
  ```
  claude mcp add --transport stdio Roblox_Studio -- cmd.exe /c %LOCALAPPDATA%\Roblox\mcp.bat
  ```
  실행 전에 `%LOCALAPPDATA%\Roblox\mcp.bat` 파일이 있는지 먼저 확인한다. 없으면 스튜디오 업데이트 후 MCP 서버를 한 번 켜게 한다.
- macOS:
  ```
  claude mcp add --transport stdio Roblox_Studio -- /Applications/RobloxStudio.app/Contents/MacOS/StudioMCP
  ```

### 1-B. Claude 데스크톱 앱 설정 파일 (빠른 연결이 안 될 때)
- 파일 위치: Claude 앱 → 설정 → 개발자(Developer) → 설정 편집(Edit Config).
  - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
  - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **기존 내용을 지우지 말고** 먼저 `.bak`으로 백업한 뒤, `mcpServers` 안에 아래 항목만 추가한다(다른 서버가 있으면 쉼표로 구분).
  - Windows:
    ```json
    "Roblox_Studio": { "command": "cmd.exe", "args": ["/c", "%LOCALAPPDATA%\\Roblox\\mcp.bat"] }
    ```
  - macOS:
    ```json
    "Roblox_Studio": { "command": "/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP" }
    ```
- 저장 후 JSON 문법(쉼표, 괄호)을 검사하고, 클로드 앱을 **완전히 종료**(Windows는 트레이에서 종료)했다가 다시 켠다.

### 연결 확인
- 스튜디오: Assistant → … → Manage MCP Servers에 **초록 표시**(연결된 클라이언트 수)가 보이면 성공.
- 클로드: "열려 있는 로블록스 스튜디오 목록 보여줘"라고 해서 플레이스 이름이 나오면 성공.

## 2. 블렌더 연결 (Blender MCP, 오픈소스)
### 2-A. 자동 설치 (Claude Code 또는 셸 사용 가능할 때)
1. uv 설치 확인: `uv --version`. 없으면
   - Windows: `winget install --id=astral-sh.uv -e` (설치 후 새 터미널)
   - macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. 한 번에 설정: `uvx mcp-for-blender setup`
   (클로드 앱 설정과 블렌더 애드온을 함께 설치한다.)
3. Claude Code만 따로 등록할 때: `claude mcp add blender uvx mcp-for-blender`

### 2-B. 수동 설치 (자동이 실패할 때)
1. 애드온 설치: `uvx mcp-for-blender install-addon`
   또는 GitHub(ahujasid/blender-mcp)에서 `addon.py`를 받아 블렌더 → Edit → Preferences → Add-ons → Install → 체크박스 **Interface: Blender MCP** 켜기.
2. 클로드 데스크톱 설정 파일 `mcpServers`에 추가:
   ```json
   "blender": { "command": "uvx", "args": ["mcp-for-blender"] }
   ```
3. 블렌더 3D 화면에서 **N** → **MCP for Blender**(또는 BlenderMCP) 탭 → 서버가 꺼져 있으면 **Start MCP Server**.

### 연결 확인
- 클로드에게 "블렌더 장면 정보 알려줘"라고 해서 오브젝트 목록이 나오면 성공.
- 주의: 같은 블렌더 MCP 서버를 두 클라이언트(예: 클로드 앱과 Cursor)에서 동시에 켜지 않는다. 터미널에서 uvx 명령을 직접 계속 실행해 두지 않는다(클로드가 알아서 켠다).

## 3. 문제 해결
- 스튜디오와 클로드를 둘 다 완전히 껐다 켠다.
- 경로가 맞는지, 파일이 실제로 있는지 확인한다(`mcp.bat`, `StudioMCP`).
- JSON 쉼표·괄호 오류가 가장 흔하다. 백업 파일과 비교한다.
- 스튜디오 MCP 표시가 초록색이 아니면 Enable Studio as MCP server를 껐다 켠다.

## 4. 끝나면 사용자에게 보고
- 연결된 것(로블록스 / 블렌더), 확인 결과, 다음에 해 볼 첫 명령 예시 1개:
  "빈 바닥에 작은 집 하나랑 캐릭터 하나 세워줘."
