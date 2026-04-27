# Agent Instructions

This repository is a serverless Slack notifier template for the Startup Campus cafeteria menu.

When installing into another repository:

- Preserve `.github/workflows/weekly-menu.yml`, `scripts/post_menu.py`, and `requirements.txt`.
- Never hardcode `SLACK_WEBHOOK_URL`.
- Ask the user to create a GitHub Actions secret named `SLACK_WEBHOOK_URL`.
- Prefer `python scripts/post_menu.py --dry-run` for verification.
- Keep changes small and avoid adding OCR, SLM, databases, or a web server unless the user explicitly asks.

Design intent:

- GitHub Actions is the scheduler.
- Slack Incoming Webhook is the delivery mechanism.
- Rule tables in `scripts/post_menu.py` declare how posts and attachments are selected.
- Missing or ambiguous results should send source links, not stale menu images.
