from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from scripts.post_menu import (
    AttachmentCandidate,
    Config,
    PostCandidate,
    choose_attachment,
    choose_post,
    fetch_bytes,
    normalize,
    score_attachment_candidate,
    success_post_reason,
)


class PostMenuTest(unittest.TestCase):
    def test_normalize_compacts_korean_spacing(self) -> None:
        self.assertEqual(normalize("스타트업 캠퍼스_구내식당"), "스타트업캠퍼스구내식당")

    def test_attachment_scoring_prefers_startup_campus(self) -> None:
        candidates = [
            AttachmentCandidate("글로벌알앤디센터 구내식당 4월 다섯째주 식단표.pdf", "https://example.com/1"),
            AttachmentCandidate("경기창조경제혁신센터 구내식당 4월 다섯째주 식단표.pdf", "https://example.com/2"),
            AttachmentCandidate("스타트업캠퍼스 구내식당 4월 다섯째주 식단표.PNG", "https://example.com/3"),
        ]

        scored = [score_attachment_candidate(candidate) for candidate in candidates]

        self.assertEqual(max(scored, key=lambda candidate: candidate.score).url, "https://example.com/3")

    def test_choose_post_prefers_current_week_menu(self) -> None:
        config = make_config()
        candidates = [
            PostCandidate("대관시설별 360 파노라마 VR 영상안내", "https://example.com/old", date(2023, 1, 5)),
            PostCandidate(
                "판교테크노밸리 공공건물 구내식당 주간메뉴표(4월 5주차)",
                "https://example.com/menu",
                date(2026, 4, 27),
            ),
        ]

        self.assertEqual(choose_post(candidates, config).url, "https://example.com/menu")

    def test_choose_attachment_prefers_startup_campus(self) -> None:
        config = make_config()
        post = PostCandidate("구내식당 주간메뉴표", "https://example.com/menu", date(2026, 4, 27))
        candidates = [
            AttachmentCandidate("글로벌알앤디센터 구내식당 식단표.pdf", "https://example.com/1"),
            AttachmentCandidate("스타트업캠퍼스 구내식당 식단표.PNG", "https://example.com/2"),
        ]

        self.assertEqual(choose_attachment(candidates, config, post).url, "https://example.com/2")

    def test_success_post_reason_skips_unchanged_attachment(self) -> None:
        state = {
            "status": "success",
            "week_start": "2026-04-27",
            "attachment": {"sha256": "abc"},
        }

        self.assertIsNone(success_post_reason(state, state, force_post=False))

    def test_success_post_reason_detects_changed_attachment(self) -> None:
        previous = {
            "status": "success",
            "week_start": "2026-04-27",
            "attachment": {"sha256": "abc"},
        }
        current = {
            "status": "success",
            "week_start": "2026-04-27",
            "attachment": {"sha256": "def"},
        }

        self.assertEqual(success_post_reason(previous, current, force_post=False), "changed")

    def test_fetch_bytes_sends_referer_for_attachment_download(self) -> None:
        session = FakeSession()

        content = fetch_bytes(session, "https://example.com/download", referer="https://example.com/post")

        self.assertEqual(content, b"menu")
        self.assertEqual(session.last_kwargs["headers"]["Referer"], "https://example.com/post")


def make_config() -> Config:
    return Config(
        board_url="https://example.com/list",
        slack_webhook_url=None,
        user_agent="test",
        today=date(2026, 4, 27),
        timezone="Asia/Seoul",
        event_name="",
        post_start_hour=9,
        post_end_hour=18,
        post_lookback_days=0,
        post_min_semantic_score=50,
        post_min_total_score=120,
        attachment_min_score=80,
        state_path=Path(".menu-state/test.json"),
        force_post=False,
        notify_failures=True,
        dry_run=True,
    )


class FakeResponse:
    content = b"menu"

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self) -> None:
        self.last_url: str | None = None
        self.last_kwargs: dict = {}

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.last_url = url
        self.last_kwargs = kwargs
        return FakeResponse()


if __name__ == "__main__":
    unittest.main()
