# Agent Instructions

This repository is a serverless Slack notifier template for the Startup Campus cafeteria menu.

When installing into another repository:

- Preserve `.github/workflows/weekly-menu.yml`, `scripts/post_menu.py`, and `requirements.txt`.
- Never hardcode `SLACK_WEBHOOK_URL`.
- Ask the user to create a GitHub Actions secret named `SLACK_WEBHOOK_URL`.
- Prefer `python scripts/post_menu.py --dry-run` for verification.
- Keep changes small and preserve the GitHub Actions plus Slack Incoming Webhook shape unless the user asks for a different delivery model.

Design intent:

- GitHub Actions is the scheduler.
- Slack Incoming Webhook is the delivery mechanism.
- `.menu-state/startupcampus-menu.json` stores the last delivered attachment hash.
- The workflow checks on weekdays and posts only when the current menu is new or changed.
