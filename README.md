# QK NOTES

Telegram voice-note bot + Mini App planner. Full specification:
`sgx_planner_prompt.md` (in the Downloads folder next to this repo) — its
"Порядок реалізації" defines the implementation order tracked below.

## Implementation status — steps 1–8 of the specification are done

1. **Step 1 (done)** — Base voice intake: voice message → Groq Whisper
   transcription → classification → save → confirmation.
2. **Step 2 (done)** — `users` table + auto-registration middleware,
   `is_admin` from `ADMIN_USER_ID`, blocked users ignored.
3. **Step 3 (done)** — Full schema: `plans`, `meetings`, `reminders`,
   `notes` (subsections `note`/`idea`), `usage_logs`, `quick_action_tokens`.
   Classifier returns `{type, subsection, title, datetime, summary}` and the
   pipeline routes each record into its table (`bot/voice.py`).
   Inline "fix category" buttons move a record between tables.
4. **Step 4 (done)** — FastAPI backend (`api/`): Telegram `initData`
   HMAC-SHA256 validation (`api/auth.py`), CRUD routers for all record
   tables, settings, quick-action webhook, admin routes. Single entry point
   `run.py` runs bot polling + APScheduler + uvicorn together.
5. **Step 5 (done)** — Mini App (`webapp/`): home screen (day/date/greeting,
   quick-action cards, nearest items), 4 sections with subsection tabs,
   round "+" FAB, long-press to edit, delete; theme follows
   `Telegram.WebApp` with dark default and manual override; opened via the
   `/start` WebApp button.
6. **Step 6 (done)** — APScheduler jobs (`scheduler.py`): daily 08:00 digest
   (voice reply to the digest adds plans/meetings for today), reminder
   notifications every minute, 3-month cleanup at 03:30.
7. **Step 7 (done)** — Localization: all bot strings in `locales/*.json`
   (en, uk, ru, pl, es) via `locales/i18n.py`; Settings screen in the Mini
   App (language switcher, theme, account block).
8. **Step 8 (done)** — Quick Actions: `/api/quick-action/token` generates a
   per-user URL+token (`quick_action_tokens`), `/api/quick-action` accepts
   voice/text from iOS Shortcuts and runs the same pipeline; Settings shows
   the URL with copy/renew; `/actionbutton` and `/backtap` give setup guides.
9. **Step 9 (done)** — Admin: Mini App "Admin" tab (admin-only) with user
   list, block/unblock, stats, Groq usage counters from `usage_logs`,
   broadcast, recent error log stream; all `/api/admin/*` endpoints return
   403 for non-admins.

## Run

```powershell
pip install -r requirements.txt
copy .env.example .env   # then fill in your tokens
python run.py            # bot polling + API on :8000 + scheduler
```

- Mini App URL: set `WEBAPP_URL` in `.env` (for production use an HTTPS URL
  and expose port 8000, e.g. via a tunnel/reverse proxy — Telegram requires
  HTTPS for Mini Apps).

## Important

- Never commit `.env` or publish your API keys.
- Classification model: `openai/gpt-oss-120b` (set in `.env` as
  `CLASSIFICATION_MODEL`) — the previously used `llama-3.3-70b-versatile`
  was decommissioned by Groq.
