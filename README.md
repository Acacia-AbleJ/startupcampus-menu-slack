# Startup Campus Menu Slack Notifier

판교테크노밸리 공지사항에서 **스타트업캠퍼스 구내식당 주간 식단표**를 찾아 Slack 채널에 자동으로 올리는 GitHub Actions 템플릿입니다.

서버를 운영하지 않습니다. OCR이나 SLM도 쓰지 않습니다. 매주 한 번 GitHub Actions가 실행되고, Slack Incoming Webhook으로 식단표 이미지 또는 파일 링크를 보냅니다.

<img src="docs/startupcampus-menu-sample.png" alt="스타트업캠퍼스 구내식당 식단표 샘플" width="720">

## How It Works

```text
매주 월요일 10:30 KST
→ 판교테크노밸리 공지사항 목록 조회
→ 이번 주 구내식당 주간메뉴표 게시글 선택
→ 스타트업캠퍼스 첨부 선택
→ Slack 채널에 이미지/파일 링크 전송
```

첨부가 PNG/JPG/GIF이면 Slack에 이미지로 표시합니다. PDF이면 원본 파일 링크를 보냅니다.

## Install

### 1. 저장소 만들기

이 저장소를 `Use this template`로 복사하거나, 에이전트에게 이 README의 **Agent Install** 섹션대로 설치를 맡깁니다.

### 2. Slack Webhook 만들기

Slack에서 식단표를 받을 채널용 Incoming Webhook을 만듭니다.

Webhook을 만들 때 선택한 채널이 식단표를 받을 채널입니다. 코드에는 채널명을 넣지 않습니다.

### 3. GitHub Secret 등록

복사한 GitHub 저장소에서 아래 위치로 이동합니다.

```text
Settings → Secrets and variables → Actions → New repository secret
```

다음 secret을 추가합니다.

```text
Name: SLACK_WEBHOOK_URL
Value: https://hooks.slack.com/services/...
```

### 4. 테스트 실행

GitHub 저장소의 `Actions` 탭에서 `Weekly Startup Campus Menu`를 선택한 뒤 `Run workflow`를 실행합니다.

성공하면 Slack 채널에 식단표 메시지가 올라옵니다.

## Agent Install

Codex, Claude Code, OpenCode 같은 coding agent가 이 템플릿을 다른 저장소에 설치할 때는 아래 지침을 따르면 됩니다.

1. `.github/workflows/weekly-menu.yml`을 복사합니다.
2. `scripts/post_menu.py`를 복사합니다.
3. `requirements.txt`를 복사하거나 기존 dependency 파일에 병합합니다.
4. Slack Webhook URL을 코드에 하드코딩하지 않습니다.
5. 사용자에게 GitHub Actions secret `SLACK_WEBHOOK_URL`을 추가하라고 안내합니다.
6. 가능하면 `python scripts/post_menu.py --dry-run`으로 검증합니다.

## Local Test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/post_menu.py --dry-run
```

특정 날짜 기준으로 테스트:

```bash
python scripts/post_menu.py --dry-run --date 2026-04-27
```

실제 Slack 전송:

```bash
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." python scripts/post_menu.py
```

## Configuration

기본값으로 바로 사용할 수 있습니다. 필요할 때만 GitHub Actions 환경 변수로 조정하세요.

| Name | Default | Description |
| --- | --- | --- |
| `SLACK_WEBHOOK_URL` | required | Slack Incoming Webhook URL. GitHub Secret으로 저장합니다. |
| `MENU_BOARD_URL` | 판교테크노밸리 공지사항 | 식단표 공지사항 목록 URL |
| `MENU_TIMEZONE` | `Asia/Seoul` | 이번 주 계산에 사용할 시간대 |
| `POST_LOOKBACK_DAYS` | `0` | 이번 주 월요일보다 며칠 전 게시글까지 허용할지 |
| `POST_MIN_SEMANTIC_SCORE` | `50` | 게시글 제목 의미 점수 최소값 |
| `POST_MIN_TOTAL_SCORE` | `120` | 게시글 최종 점수 최소값 |
| `ATTACHMENT_MIN_SCORE` | `80` | 스타트업캠퍼스 첨부 점수 최소값 |
| `BOT_USER_AGENT` | built in | 사이트 요청에 사용할 User-Agent |

## Selection Rules

게시글과 첨부는 SLM 없이 점수 규칙으로 선택합니다. 규칙은 `scripts/post_menu.py`의 `POST_TERMS`, `ATTACHMENT_TERMS`에 선언돼 있습니다.

첨부파일 예시:

```text
스타트업캠퍼스, 구내식당, 식단표 → 가점
글로벌, 알앤디, 경기창조, 창조경제 → 감점
```

점수가 낮거나 애매하면 이미지를 억지로 보내지 않고, Slack에 공지사항 목록 또는 게시글 링크를 보냅니다.

## Schedule

기본 workflow는 월요일 10:30 KST에 실행됩니다.

```yaml
on:
  schedule:
    - cron: "30 10 * * 1"
      timezone: "Asia/Seoul"
```

사용 중인 GitHub 환경에서 `timezone`을 지원하지 않으면 UTC 기준으로 아래처럼 바꾸면 됩니다.

```yaml
on:
  schedule:
    - cron: "30 1 * * 1"
```

## Security

- Slack Webhook URL은 GitHub Secret에만 저장합니다.
- Public 저장소에 Webhook URL을 커밋하지 않습니다.
- Actions 로그에 Webhook URL을 출력하지 않습니다.
- 실패 시 과거 식단표 이미지를 fallback으로 보여주지 않습니다.
