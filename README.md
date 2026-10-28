# Claude Code Usage Dashboard

Real usage stats computed from local Claude Code session logs (`~/.claude/projects`).

- `scripts/analyze.py` reads the logs and writes aggregate counts to `docs/stats.json` (no prompt or response text).
- `docs/index.html` renders the dashboard (GitHub Pages, `/docs`).

Regenerate: `python3 -I scripts/analyze.py docs/stats.json`
