#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


DEFAULT_BOARD_URL = (
    "https://www.pangyotechnovalley.org/base/board/list"
    "?boardManagementNo=18&menuLevel=2&menuNo=55&page=1"
    "&searchCategory=&searchType=&searchWord="
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; StartupCampusMenuBot/1.0; "
    "+https://github.com/your-org/startupcampus-menu-slack)"
)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif")
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS + (".pdf",)


@dataclass(frozen=True)
class Config:
    board_url: str
    slack_webhook_url: str | None
    user_agent: str
    today: date
    timezone: str
    post_lookback_days: int
    post_min_semantic_score: int
    post_min_total_score: int
    attachment_min_score: int
    dry_run: bool


@dataclass(frozen=True)
class WeightedTerm:
    text: str
    weight: int


@dataclass(frozen=True)
class PostCandidate:
    title: str
    url: str
    published_on: date | None
    score: int = 0
    semantic_score: int = 0


@dataclass(frozen=True)
class AttachmentCandidate:
    name: str
    url: str
    score: int = 0


@dataclass(frozen=True)
class MenuResult:
    post: PostCandidate
    attachment: AttachmentCandidate
    board_url: str


@dataclass(frozen=True)
class MenuError(Exception):
    message: str
    board_url: str
    post_url: str | None = None
    debug: dict | None = None

    def __str__(self) -> str:
        return self.message


POST_TERMS = (
    WeightedTerm("구내식당", 45),
    WeightedTerm("주간메뉴표", 80),
    WeightedTerm("주간메뉴", 60),
    WeightedTerm("식단표", 55),
    WeightedTerm("메뉴표", 55),
    WeightedTerm("식단", 25),
    WeightedTerm("메뉴", 15),
    WeightedTerm("판교테크노밸리", 5),
    WeightedTerm("파노라마", -120),
    WeightedTerm("vr", -120),
    WeightedTerm("대관", -80),
)

ATTACHMENT_TERMS = (
    WeightedTerm("스타트업캠퍼스", 120),
    WeightedTerm("스타트업", 45),
    WeightedTerm("캠퍼스", 45),
    WeightedTerm("startupcampus", 120),
    WeightedTerm("startup", 45),
    WeightedTerm("campus", 45),
    WeightedTerm("구내식당", 25),
    WeightedTerm("주간메뉴표", 35),
    WeightedTerm("주간메뉴", 30),
    WeightedTerm("식단표", 35),
    WeightedTerm("메뉴표", 35),
    WeightedTerm("식단", 20),
    WeightedTerm("메뉴", 15),
    WeightedTerm("글로벌", -120),
    WeightedTerm("알앤디", -120),
    WeightedTerm("글로벌알앤디", -160),
    WeightedTerm("global", -120),
    WeightedTerm("rnd", -120),
    WeightedTerm("rd센터", -80),
    WeightedTerm("경기창조", -120),
    WeightedTerm("창조경제", -120),
    WeightedTerm("혁신센터", -80),
)


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[\s_\-./()（）\[\]{}&]+", "", value)


def score_terms(text: str, terms: Iterable[WeightedTerm]) -> int:
    normalized = normalize(text)
    return sum(term.weight for term in terms if normalize(term.text) in normalized)


def week_bounds(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)


def parse_korean_date(text: str) -> date | None:
    match = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", text)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    return date(year, month, day)


def dated_score(published_on: date | None, today: date, lookback_days: int) -> int:
    if published_on is None:
        return -20

    week_start, week_end = week_bounds(today)
    earliest = week_start - timedelta(days=lookback_days)

    if earliest <= published_on <= week_end:
        return 100
    if published_on < earliest:
        return -200
    return -50


def collect_post_candidates(html: str, board_url: str) -> list[PostCandidate]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[PostCandidate] = []
    seen_urls: set[str] = set()

    for row in soup.select("table.board_list tbody tr"):
        link = row.select_one("td.tit a[href]")
        if not link:
            continue

        url = urljoin(board_url, link["href"])
        if url in seen_urls:
            continue

        title = link.get("title") or link.get_text(" ", strip=True)
        published_on = parse_korean_date(row.select_one(".date").get_text(" ", strip=True)) if row.select_one(".date") else None

        seen_urls.add(url)
        candidates.append(PostCandidate(title=clean_space(title), url=url, published_on=published_on))

    return candidates


def score_post_candidate(candidate: PostCandidate, config: Config) -> PostCandidate:
    semantic = score_terms(candidate.title, POST_TERMS)
    total = semantic + dated_score(candidate.published_on, config.today, config.post_lookback_days)
    return PostCandidate(
        title=candidate.title,
        url=candidate.url,
        published_on=candidate.published_on,
        score=total,
        semantic_score=semantic,
    )


def choose_post(candidates: list[PostCandidate], config: Config) -> PostCandidate:
    scored = sorted(
        (score_post_candidate(candidate, config) for candidate in candidates),
        key=lambda candidate: (candidate.score, candidate.published_on or date.min),
        reverse=True,
    )

    if not scored:
        raise MenuError(
            message="이번 주 식단표 게시글을 찾지 못했습니다.",
            board_url=config.board_url,
            debug={"reason": "no_list_candidates"},
        )

    best = scored[0]
    if (
        best.semantic_score < config.post_min_semantic_score
        or best.score < config.post_min_total_score
    ):
        raise MenuError(
            message="이번 주 식단표 게시글을 자동으로 확정하지 못했습니다.",
            board_url=config.board_url,
            debug={"reason": "low_post_score", "candidates": serialize_posts(scored[:5])},
        )

    return best


def collect_attachment_candidates(html: str, detail_url: str) -> list[AttachmentCandidate]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = (
        ".basic-view__file__file-list li a[href]",
        "a[download][href]",
        "a[href*='download'][href]",
    )
    candidates: list[AttachmentCandidate] = []
    seen_urls: set[str] = set()

    for link in soup.select(",".join(selectors)):
        href = link.get("href", "")
        if not href:
            continue

        url = urljoin(detail_url, href)
        if url in seen_urls:
            continue

        name = link.get("title") or link.get_text(" ", strip=True) or href
        seen_urls.add(url)
        candidates.append(AttachmentCandidate(name=clean_space(name), url=url))

    return candidates


def score_attachment_candidate(candidate: AttachmentCandidate) -> AttachmentCandidate:
    score = score_terms(candidate.name, ATTACHMENT_TERMS)
    if file_extension(candidate.name) in SUPPORTED_EXTENSIONS:
        score += 8
    return AttachmentCandidate(name=candidate.name, url=candidate.url, score=score)


def choose_attachment(
    candidates: list[AttachmentCandidate],
    config: Config,
    post: PostCandidate,
) -> AttachmentCandidate:
    scored = sorted(
        (score_attachment_candidate(candidate) for candidate in candidates),
        key=lambda candidate: candidate.score,
        reverse=True,
    )

    if not scored:
        raise MenuError(
            message="식단표 게시글은 찾았지만 첨부파일을 찾지 못했습니다.",
            board_url=config.board_url,
            post_url=post.url,
            debug={"reason": "no_attachment_candidates"},
        )

    best = scored[0]
    if best.score < config.attachment_min_score:
        raise MenuError(
            message="스타트업캠퍼스 식단표 첨부를 자동으로 확정하지 못했습니다.",
            board_url=config.board_url,
            post_url=post.url,
            debug={"reason": "low_attachment_score", "candidates": serialize_attachments(scored[:5])},
        )

    return best


def discover_menu(config: Config) -> MenuResult:
    session = requests.Session()
    session.headers.update({"User-Agent": config.user_agent})

    list_html = fetch_text(session, config.board_url)
    post = choose_post(collect_post_candidates(list_html, config.board_url), config)

    detail_html = fetch_text(session, post.url)
    attachment = choose_attachment(collect_attachment_candidates(detail_html, post.url), config, post)

    return MenuResult(post=post, attachment=attachment, board_url=config.board_url)


def fetch_text(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=20)
    response.raise_for_status()
    if response.encoding is None:
        response.encoding = response.apparent_encoding
    return response.text


def build_success_payload(result: MenuResult) -> dict:
    title = f"이번 주 스타트업캠퍼스 구내식당 식단표"
    post_date = result.post.published_on.isoformat() if result.post.published_on else "등록일 확인 불가"
    extension = file_extension(result.attachment.name)

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{escape_slack(title)}*\n"
                    f"{escape_slack(result.attachment.name)}\n"
                    f"게시일: {escape_slack(post_date)}"
                ),
            },
        },
        actions_block(
            (
                ("원본 파일 보기", result.attachment.url),
                ("게시글 보기", result.post.url),
                ("공지사항 목록", result.board_url),
            )
        ),
    ]

    if extension in IMAGE_EXTENSIONS:
        blocks.append(
            {
                "type": "image",
                "image_url": result.attachment.url,
                "alt_text": "스타트업캠퍼스 구내식당 식단표",
            }
        )
    else:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "이미지 미리보기를 지원하지 않는 파일입니다. 원본 파일을 열어 확인해주세요.",
                },
            }
        )

    return {"text": title, "blocks": blocks}


def build_failure_payload(error: MenuError) -> dict:
    links = [("공지사항 목록", error.board_url)]
    if error.post_url:
        links.insert(0, ("게시글 보기", error.post_url))

    return {
        "text": error.message,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{escape_slack(error.message)}*\n공지사항에서 직접 확인해주세요.",
                },
            },
            actions_block(tuple(links)),
        ],
    }


def actions_block(links: tuple[tuple[str, str], ...]) -> dict:
    return {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": label, "emoji": True},
                "url": url,
            }
            for label, url in links
        ],
    }


def post_to_slack(webhook_url: str, payload: dict) -> None:
    response = requests.post(webhook_url, json=payload, timeout=20)
    response.raise_for_status()


def clean_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def file_extension(name: str) -> str:
    match = re.search(r"(\.[A-Za-z0-9]+)$", name.strip())
    return match.group(1).casefold() if match else ""


def escape_slack(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def serialize_posts(candidates: Iterable[PostCandidate]) -> list[dict]:
    return [
        {
            "title": candidate.title,
            "url": candidate.url,
            "published_on": candidate.published_on.isoformat() if candidate.published_on else None,
            "score": candidate.score,
            "semantic_score": candidate.semantic_score,
        }
        for candidate in candidates
    ]


def serialize_attachments(candidates: Iterable[AttachmentCandidate]) -> list[dict]:
    return [
        {"name": candidate.name, "url": candidate.url, "score": candidate.score}
        for candidate in candidates
    ]


def serialize_result(result: MenuResult) -> dict:
    return {
        "post": serialize_posts([result.post])[0],
        "attachment": serialize_attachments([result.attachment])[0],
        "board_url": result.board_url,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Post Startup Campus cafeteria menu to Slack.")
    parser.add_argument("--dry-run", action="store_true", help="Print the Slack payload instead of posting it.")
    parser.add_argument("--date", help="Override today's date in YYYY-MM-DD for testing.")
    return parser.parse_args(argv)


def load_config(argv: list[str]) -> Config:
    args = parse_args(argv)
    timezone = os.getenv("MENU_TIMEZONE", "Asia/Seoul")
    today = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else datetime.now(ZoneInfo(timezone)).date()

    return Config(
        board_url=os.getenv("MENU_BOARD_URL", DEFAULT_BOARD_URL),
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
        user_agent=os.getenv("BOT_USER_AGENT", DEFAULT_USER_AGENT),
        today=today,
        timezone=timezone,
        post_lookback_days=int(os.getenv("POST_LOOKBACK_DAYS", "0")),
        post_min_semantic_score=int(os.getenv("POST_MIN_SEMANTIC_SCORE", "50")),
        post_min_total_score=int(os.getenv("POST_MIN_TOTAL_SCORE", "120")),
        attachment_min_score=int(os.getenv("ATTACHMENT_MIN_SCORE", "80")),
        dry_run=args.dry_run,
    )


def emit(config: Config, payload: dict) -> None:
    if config.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if not config.slack_webhook_url:
        raise RuntimeError("SLACK_WEBHOOK_URL is required unless --dry-run is used.")

    post_to_slack(config.slack_webhook_url, payload)


def main(argv: list[str]) -> int:
    config = load_config(argv)

    try:
        result = discover_menu(config)
        payload = build_success_payload(result)
        if config.dry_run:
            payload["_debug"] = serialize_result(result)
        emit(config, payload)
        return 0
    except MenuError as error:
        payload = build_failure_payload(error)
        if config.dry_run and error.debug:
            payload["_debug"] = error.debug
        emit(config, payload)
        return 1
    except requests.RequestException as error:
        menu_error = MenuError(
            message="판교테크노밸리 공지사항에 접근하지 못했습니다.",
            board_url=config.board_url,
            debug={"reason": "request_failed", "error": str(error)},
        )
        payload = build_failure_payload(menu_error)
        if config.dry_run:
            payload["_debug"] = menu_error.debug
        emit(config, payload)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
