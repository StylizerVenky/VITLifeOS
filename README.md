# VIT Life OS — Streamlit edition

A café-inspired student planner that runs in your browser. The application is written in Python with Streamlit; a small inline style block adds button transitions and decorative animation. No separate frontend or JavaScript code is needed.

## Run on your WINDOWS

Extract the ZIP first. Open Terminal, type `cd ` (including a space), drag the extracted `VIT-Life-OS-Streamlit` folder into the Terminal window, and press Enter. Then run these commands one at a time:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Open **http://localhost:8501** if your browser does not open automatically. Keep Terminal running while you use the website. Press Control+C in Terminal to stop it. Use Python 3.10 or later.

Next time, open Terminal in this folder and run:

```sh
source .venv/bin/activate
python3 -m streamlit run app.py
```

Run the commands inside the project folder so Streamlit loads the included café theme. Use Streamlit's Settings → Theme menu if you prefer a different theme.

## Features

- **Home:** this month's actual spending, today's focused hours and pending deadlines.
- **Expenses:** purchases, searchable history, date filters and a monthly budget.
- **Courses:** editable subjects, credits, scores and personal grade targets.
- **Attendance:** classes attended/held, an editable attendance target, and classes needed or remaining absence buffer.
- **Deadlines:** assignments, CAT prep, lab records and club work. Edit the status to mark a task Done.
- **Focus timer:** 15/25/45/60-minute sessions, pause/resume, a progress bar and automatic focused-time logging on completion.
- **Time:** focused work, wandering, classes and rest.
- **Wishlist:** purchase ideas and advice against the remaining monthly budget.
- **Notes:** longer thoughts and quick reminders.

The sidebar stays available across pages. Buttons have eased hover transitions. The timer uses Streamlit fragments so timer ticks do not rerun the whole page. Reduced-motion browser preferences disable the decorative animation. Data changes use forms to avoid saving half-filled entries.

## Add, edit and remove logs

Choose a notebook from the sidebar. Use **Add / edit** to create an entry or select an existing one to change it. **History & remove logs** includes search, date filters, CSV export and deletion controls.

Expand **Remove logs / entries**, choose records, tick the confirmation box and press **Remove selected**. To remove every record in the notebook, expand **Clear this notebook**, type `CLEAR`, and confirm with the button. This includes records hidden by filters. Deletion cannot be undone. Other notebooks and accounts are unaffected.

## Existing data

**From the earlier desktop version:** close it and copy its complete `data` folder beside this new `app.py`. The previous SQLite file is read once to migrate accounts and records into CSV; the source file stays unchanged. Do not copy a database while the old app is running.

**From the original CSV version:** register with the same username used in your CSV `User` column. Use the matching notebook's **Import CSV** tab. Import the CSV files one at a time. The original `users.csv` passwords are not imported; create a new account. The app only imports rows with your matching username when a `User` column is present. Files without that column import into the currently signed-in account.

Dates must use `YYYY-MM-DD`; older note dates such as `Oct 27, 18:30` need a year and conversion first. The CSV tab shows required columns. Invalid files leave storage unchanged; exact duplicates are skipped. Existing course and attendance subjects must be edited instead of imported again.

Export saves the currently filtered rows, without credentials. Formula-like text receives an apostrophe prefix for safer spreadsheet opening; this prefix remains if reimported.

## Accounts, timer and storage

- Accounts are separate inside the app. Passwords use salted PBKDF2-HMAC-SHA256 and constant-time verification.
- CSV files store records in `data/records.csv` and accounts in `data/users.csv` beside `app.py`. These files are not encrypted. People who can read the server's files can read its contents. There is no password reset.
- Close the server before copying the complete `data` folder for a backup. An optional `VIT_LIFE_OS_DATA` environment variable changes the storage folder.
- A timer continues when switching app pages. Keep the same browser session and server open. Refreshing the browser, closing it, or restarting the server can discard an unfinished timer. Completion is checked while the session is active; the next tick after a sleeping tab wakes can save a completed session. Only completed sessions are logged. Signing out requires confirmation before discarding an unfinished timer.
- Streamlit shares app code across visitors, while session state is specific to each browser session. CSV reads and atomic file replacement are protected by a thread lock and, on macOS/Linux, an advisory file lock.
- This is a personal planner, not an online student chat or shared student board. No real user records or author attribution are bundled. Nothing has been pushed to GitHub or published.
- Course scores and grade targets do not predict official VIT relative grades or CGPA. Attendance thresholds are user-entered planning targets; verify official course requirements.

## If you host it later

This download is a source project, not an already published website. Use a host that supports a long-running Python/Streamlit server; static GitHub Pages cannot run it. Public hosting needs HTTPS, durable storage, operational backups and stronger authentication controls such as rate limiting. CSV data on ephemeral hosting can disappear when the service restarts or redeploys. This version is intended for a local project/demo and has not been production hardened.

## Features from the project presentation

| Feature | Implementation |
| --- | --- |
| CG Maxxing | Allocates available study minutes by credits × positive target-mark gap. Set personal target marks in Courses. |
| Money Maxxing | Analyses the last 30 days, highlights repeated spending and estimates a chosen reduction in possibly flexible expenses. |
| Time Maxxing | Analyses 7 days of wandering logs and allocates a recoverable share to priority subjects. Rest is excluded. |
| Purchase Maxxing | Seven-day wait, utility score, budget impact and affordability checks. Set the wish date in Wishlist. |
| What-If Lab | Daily savings over 30/180/365 days and additional study-time allocation. ₹40/day gives ₹7,200 over 180 days and ₹14,600 over 365 days. |
| Daily recommendations | Combines deadlines, subject priorities, spending, attendance, time and purchase waits on Home. |
| Core Python storage | Lists, dictionaries, CSV file handling and control flow. No database is used for ongoing storage. |

Streamlit replaces the presentation's earlier Flask UI plan, as requested. Recommendations are transparent planning heuristics, not guaranteed marks or CGPA improvements. Flexible spending flags require your judgment; essential food and travel are not automatically waste.

Older course imports default personal target marks to 90/100. Older wishes without dates start the seven-day wait on import/migration day. Review those values after upgrading.

## Validation

Run `python3 -m unittest discover -s tests -v` after installing requirements. The suite includes storage, migration, concurrency, calculation and Streamlit interaction checks. Browser animation smoothness still requires visual checking on your Mac.
