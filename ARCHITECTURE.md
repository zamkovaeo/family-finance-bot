# Architecture

## Runtime

The MVP is a single FastAPI service. On startup it launches:

- HTTP API for external integrations and future admin panels.
- Telegram bot polling worker.
- Lightweight scheduled notification loop for weekly and monthly reports.

For production growth, split these into separate processes:

- `api`: FastAPI only.
- `bot-worker`: Telegram polling or webhook processing.
- `scheduler`: reports, reminders, backups.

## Core modules

- `app/bot`: Telegram UX, keyboards, user input states, voice messages.
- `app/api`: JSON endpoints from the PRD.
- `app/models`: SQLAlchemy database entities.
- `app/services/finance_service.py`: transactions, budgets, goals, limit alerts.
- `app/services/analytics_service.py`: summaries and chart generation.
- `app/services/reporting_service.py`: text reports.
- `app/services/llm_service.py`: categorization and Speech-to-Text extension point.
- `app/services/notification_service.py`: scheduled weekly and month-end reports.

## Data model

Main entities:

- `Family`: shared budget workspace.
- `User`: Telegram user with `admin` or `member` role.
- `Category`: family-specific income and expense categories.
- `Budget`: monthly category limits.
- `Transaction`: income or expense, with personal/family flag and optional tag.
- `Tag`: project labels such as ремонт, отпуск, автомобиль.
- `Goal`: savings goals.
- `Report`: sent report log, also used to avoid duplicate scheduled messages.

## AI layer

The bot works without paid AI keys by using keyword categorization. When `OPENAI_API_KEY`
is configured, voice messages are transcribed through Speech-to-Text. LLM-based
categorization can be added inside `Categorizer.choose_category` without changing
Telegram handlers or API routes.

