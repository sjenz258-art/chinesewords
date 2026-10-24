# 小小故事園 — Traditional Chinese Story & Reading App

A working **Phase 2** Python/Streamlit application for a parent and a seven-year-old reader. Manual entry and offline readings need no AI API calls. Optional AI pronunciation review runs only when explicitly requested. Optional OpenAI generation uses a configurable model. The interface uses Traditional Chinese.

## Run on your computer

Install Python 3.11 or 3.12. Open a terminal in this project folder, then run:

```sh
python -m venv .venv
```

Activate it on macOS/Linux with `source .venv/bin/activate`, or on Windows PowerShell with `.venv\Scripts\Activate.ps1`. Then:

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local address printed by Streamlit (usually http://localhost:8501). Keep the terminal open; Ctrl+C stops the app. On an iPhone connected to the same trusted Wi-Fi, use the Network URL shown by Streamlit if your firewall permits it. Your computer must remain running.

1. Open **漢字管理**. Paste characters into Mastered (confidently recognised), Learning (currently learning), or New (not introduced). Saving a duplicate moves its category. Try uploading `samples/characters.csv`.
2. Open **創作故事**, select learning targets, type/paste a title and story, or load the original sample. No API key is needed.
3. Edit freely. The analysis updates when leaving the input field. It excludes title and punctuation, reports missed targets, and distinguishes unique-character mastery from occurrence-weighted mastery. Length outside the selected ±20-character range triggers a warning; saving remains allowed for shorter practice passages.
4. Save, then open **閱讀書庫**. Adjust text size, show learning colours, favourite stories, or load a story back into the editor. To revise the same saved story, tick **更新目前已載入的故事**. Otherwise saving makes a new copy.
   To load the complete synthetic sample database from a terminal, run `python -m samples.load_samples` before starting the app (this intentionally updates categories for the sample characters).
5. Download a backup after each session from **備份與說明**.

## Optional OpenAI configuration

Copy `.env.example` to `.env` and add your own API key:

```dotenv
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4.1-mini
```

Restart the app. The example model supports Chinese writing and JSON responses; choose another model supporting Chat Completions and `response_format=json_object` by changing `OPENAI_MODEL`. The model is configuration, not fixed in the generation code. The API is billed separately from a ChatGPT subscription.

Alternatively, create `.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "your-key-here"
OPENAI_MODEL = "gpt-4.1-mini"
```

Never upload `.env` or `secrets.toml` to a repository. The interface has no key input or key display; SQLite and backups never store it. Provider errors are replaced with a safe message. AI mode sends mastered characters, selected targets, the draft and revision instruction to OpenAI. Manual mode does not send these anywhere.

For cost estimates, look up the **current rates for your exact model** at https://openai.com/api/pricing/ and configure numeric USD per million tokens:

```dotenv
OPENAI_INPUT_USD_PER_MILLION=0.40
OPENAI_OUTPUT_USD_PER_MILLION=1.60
```

These are illustrative rates, not a promise of current pricing. The app reports returned input/output token counts and estimates `(input_tokens × input_rate + output_tokens × output_rate) / 1,000,000`. Without both rates it reports that cost is unavailable. Cached-token discounts, retries, taxes and special billing are not accounted for; your provider dashboard is authoritative. A generation request may be billed even if it times out or produces invalid output. Each button click makes a request (SDK retries once on transient failures).

## Persistence, export and restore

SQLite lives at `data/reading.db`, overridable via `DATABASE_PATH`. The schema scopes characters and stories by `child_id` for future multiple-child support. This version uses a single synthetic profile. It never automatically promotes characters to Mastered.

- Character CSV: import/export in 漢字管理. UTF-8 CSV and `.xlsx` supported. Preferred columns: `character,category`; use exact category names Mastered, Learning, New. Chinese strings in one cell split into individual characters. Duplicates collapse; the last category wins.
- Character JSON: export/restore in 備份與說明. Restore validates all rows before replacing the character list; it does not change stories.
- Complete JSON backup (recommended on a phone): in 備份與說明, download **下載完整 JSON 備份（可在手機還原）**. To restore, upload that file under **還原完整 JSON 備份**, confirm replacement, and click **還原完整資料**. This replaces the single profile’s stories, favourites, characters, pinyin corrections and AI review records together. Invalid data leaves the current database unchanged. Keep a backup before replacement. JSON upload/restore is limited to 10 MB; larger libraries can use SQLite backup.
- Complete SQLite backup: download the SQLite backup (includes stories/favourites). It uses SQLite's backup API so WAL commits are included. To restore, stop the app, move the existing `data/reading.db`, `data/reading.db-wal`, and `data/reading.db-shm` out of the way if present, then copy the backup to `data/reading.db` and restart. Keep the old files until you have checked the restored library. Use only trusted backups produced by this application.

## Streamlit Community Cloud deployment

1. Put these source files in your own GitHub repository, excluding ignored secrets, private data and local databases. Repository: https://github.com/sjenz258-art/chinesewords. The code is stored here; a live Streamlit deployment must be connected separately.
2. Sign into https://share.streamlit.io/, choose **Create app**, select your repository and branch, and set the entry point to `app.py`. Choose Python 3.12 in advanced settings.
3. If using AI, add the TOML settings above through the app's **Secrets** setting. Do not put a key in the repository. Deploy.
4. Use Streamlit's access controls to restrict the app to your family. This app has no built-in authentication or per-user isolation: visitors to the same instance share its library. Do not make a personal-data instance public.
5. Download complete backups frequently. **Community Cloud local disk is not durable storage**: restarts, redeployments or hibernation may erase SQLite. Restore the complete JSON backup through the app from your phone if needed, or restore SQLite on a computer. For durable hosted use, a future version needs external database storage; do not rely on this version as your only record.

## Tests

```sh
python -m pytest -q
```

Tests cover Han character counting, punctuation/newlines, duplicate removal, unique and weighted familiarity, coverage, frequencies, length boundaries, SQLite persistence and backup, future child scoping, CSV/Excel import, optional API behaviour and sanitised errors, configurable model/cost calculation, HTML escaping, and real Streamlit manual-mode/save/edit/library flows. Phase 2 tests additionally cover polyphonic words, tone sandhi, punctuation alignment, correction persistence, native ruby modes, A4 dimensions, embedded fonts, measured pinyin alignment, long-story pagination, unsupported glyph errors, and the correction/PDF UI flow. OpenAI calls are mocked: no live paid API request is made in tests. Sample files contain synthetic information only.

## Current scope and limitations

Phase 1 foundation: character categories/import/export, optional AI and free manual modes, editable saved stories, deterministic analysis, mobile-oriented Chinese reading, favourites and backup. The animal sample is original, not a copyrighted adaptation. The app prompts AI for Hong Kong standard written Traditional Chinese and age-appropriate public-domain adaptations; a parent must check language, suitability and historical accuracy. It does not automatically certify Traditional Chinese, convert simplified text, guarantee all target characters, or enforce story length. Han counting includes Han Unicode extensions and compatibility ideographs; it does not distinguish simplified/traditional variants or count non-Han numerals as Chinese characters. Colour is accompanied by a legend and character-frequency table.

**Phase 2 implemented:** offline contextual Mandarin pinyin, phrase rules, ambiguity warnings, parent corrections, three reading modes, and three embedded-font A4 PDFs. See [PHASE2.md](PHASE2.md) for the parent guide, tone conventions, test evidence, and limitations. The practice PDF includes editable, explicitly labelled sentence-retelling templates; full learning activities remain in Phase 3.

**Phase 3 next:** vocabulary exercises, richer comprehension questions, story-read and character-recognition records, exposure tracking. **Phase 4:** spaced repetition recommendations, optional audio and multiple-child UI.

## Pinyin accuracy enhancement

The current release expands offline phrase rules and adds optional independent AI pronunciation checking. It shows a focused exception list, supports accepting/keeping readings, caches paid checks, and keeps PDF review status consistent with the reader. Read [PINYIN_ACCURACY.md](PINYIN_ACCURACY.md) for instructions, model/cost configuration, and the limits of automatic agreement. Manual reading and printing still require no API key.


## Review and reliability update

See [REVIEW.md](REVIEW.md) for the latest review findings, fixes, validation and remaining work. The update preserves exact story text when saving, improves contextual pinyin boundaries and sandhi, adds phone-friendly full restore, hardens imports/backups, and improves PDF whitespace/line breaking and mobile pronunciation pop-ups. Earlier downloadable ZIPs do not update automatically; deploy this release's files to receive the changes.

## Automated tests and deployment

A GitHub Actions workflow is included at `.github/workflows/tests.yml`. Follow [AUTOMATION.md](AUTOMATION.md) to set up pull-request tests, protect `main` where your GitHub plan supports it, and link Streamlit Community Cloud. Streamlit deploys changes to its watched branch immediately; the pull-request process ensures tests run before merging to that branch. The workflow uses mocked API calls and needs no API secrets.
