# Project Rules

## Secrets

- Never ask the user to paste API keys, tokens, or passwords into chat if a local file option exists.
- Prefer storing secrets only in `.env` inside this project.
- Never commit `.env` or any secret-bearing file.
- If a secret is exposed in chat or logs, instruct the user to revoke and rotate it immediately.

## Environment

- LLM report settings must be read from local `.env`.
- Keep `.env.example` as a template with empty placeholder values only.

## Reporting

- Use `/Users/forestdragon/kakao_golf/REPORT_METRIC_WRITING_POLICY.md` as the fixed source of truth for report metric calculation labels, change wording, and per-line interpretation text.
- In report-facing output, every key metric must include both the numeric change and its plain-language meaning.
- Do not expose internal payload key names in final report prose.

## Safety Checks

- Before any git-related setup, confirm `.gitignore` excludes `.env`, `venv/`, `logs/`, `reports/`, and `data/`.
- When reviewing or changing config, avoid printing secret values back to the user.
