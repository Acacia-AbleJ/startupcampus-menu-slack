# Startup Campus Menu Slack Notifier

판교테크노밸리 공지사항에서 스타트업캠퍼스 구내식당 주간 식단표 첨부를 찾아 Slack 채널에 올리는 GitHub Actions 자동화입니다.

서버, OCR, Slack slash command가 없습니다. 매주 한 번 GitHub Actions가 실행되고 Slack Incoming Webhook으로 메시지를 보냅니다.

## 동작 방식

```text
매주 월요일 10:30 KST
→ 판교테크노밸리 공지사항 목록 조회
→ 이번 주 구내식당 주간메뉴표 게시글 선택
→ 스타트업캠퍼스 첨부 선택
→ Slack Incoming Webhook으로 이미지/파일 링크 전송
```

첨부가 PNG/JPG/GIF이면 Slack 이미지 블록으로 표시합니다. PDF이면 원본 파일 링크를 보냅니다.

## 설치

1. 이 저장소를 `Use this template`로 복사하거나 필요한 파일을 기존 저장소에 복사합니다.
2. Slack에서 식단표를 받을 채널용 Incoming Webhook을 만듭니다.
3. GitHub 저장소의 `Settings → Secrets and variables → Actions`에서 secret을 추가합니다.
   - 이름: `SLACK_WEBHOOK_URL`
   - 값: Slack Incoming Webhook URL
4. `Actions` 탭에서 `Weekly Startup Campus Menu`를 수동 실행해 테스트합니다.

Incoming Webhook은 생성할 때 선택한 Slack 채널로 메시지를 보냅니다. 이 저장소 코드에는 채널명이 들어가지 않습니다.

## Agent Install

Use this section when Codex, Claude Code, OpenCode, or another coding agent installs this notifier into a user's repository.

Tasks:

1. Copy `.github/workflows/weekly-menu.yml`.
2. Copy `scripts/post_menu.py`.
3. Copy `requirements.txt`, or merge the dependencies into the existing dependency file.
4. Do not hardcode Slack webhook URLs.
5. Tell the user to add a GitHub Actions secret named `SLACK_WEBHOOK_URL`.
6. Run `python scripts/post_menu.py --dry-run` if network access is available.
7. Keep the schedule at Monday 10:30 KST unless the user asks otherwise.

## 설정값

필요하면 GitHub Actions 환경 변수로 조정할 수 있습니다.

| 이름 | 기본값 | 설명 |
| --- | --- | --- |
| `SLACK_WEBHOOK_URL` | 없음 | Slack Incoming Webhook URL. Secret으로 저장해야 합니다. |
| `MENU_BOARD_URL` | 판교테크노밸리 공지사항 | 식단표 공지사항 목록 URL |
| `MENU_TIMEZONE` | `Asia/Seoul` | 이번 주 계산에 사용할 시간대 |
| `POST_LOOKBACK_DAYS` | `0` | 이번 주 월요일보다 며칠 전 게시글까지 허용할지 |
| `POST_MIN_SEMANTIC_SCORE` | `50` | 게시글 제목 의미 점수 최소값 |
| `POST_MIN_TOTAL_SCORE` | `120` | 게시글 최종 점수 최소값 |
| `ATTACHMENT_MIN_SCORE` | `80` | 스타트업캠퍼스 첨부 점수 최소값 |
| `BOT_USER_AGENT` | 내장값 | 사이트 요청에 사용할 User-Agent |

## 로컬 테스트

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/post_menu.py --dry-run
```

특정 날짜 기준으로 테스트하려면:

```bash
python scripts/post_menu.py --dry-run --date 2026-04-27
```

실제 Slack 전송:

```bash
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." python scripts/post_menu.py
```

## 선택 로직

이 프로젝트는 SLM/OCR 없이 파일명과 게시글 제목을 점수화합니다. 규칙은 `scripts/post_menu.py`의 `POST_TERMS`, `ATTACHMENT_TERMS`에 선언돼 있습니다.

예를 들어 첨부파일 후보 중:

- `스타트업캠퍼스`, `구내식당`, `식단표`는 가점
- `글로벌`, `알앤디`, `경기창조`, `창조경제`는 감점

점수가 낮으면 이미지를 억지로 보내지 않고, Slack에 공지사항 목록 또는 게시글 링크를 보내 직접 확인하게 합니다.

## GitHub Actions 스케줄

기본 workflow는 월요일 10:30 KST에 실행됩니다.

```yaml
on:
  schedule:
    - cron: "30 10 * * 1"
      timezone: "Asia/Seoul"
```

만약 사용하는 GitHub 환경에서 `timezone`을 지원하지 않으면 UTC 기준으로 아래처럼 바꾸면 됩니다.

```yaml
on:
  schedule:
    - cron: "30 1 * * 1"
```

## 보안

- Slack Webhook URL은 secret에만 저장합니다.
- Public 저장소에 Webhook URL을 커밋하지 않습니다.
- Actions 로그에 Webhook URL을 출력하지 않습니다.
- 실패 시에도 과거 식단표 이미지를 fallback으로 보여주지 않습니다.
