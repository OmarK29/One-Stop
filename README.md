# One Stop

Track physical, mental and spiritual habits in one Google Sheet. **Guide me** walks you through a few questions and lands on the one thing worth doing next. You get XP, not streaks. Unideal things are logged for awareness and never cost XP.

The same code runs on your Mac and, hosted free, on your phone. Both read and write the same sheet.

## Pages

| Page | What it does |
|---|---|
| **Guide me** | One question at a time, then **one** action. That action is the most important item you haven't done yet, chosen from your answers. The buttons are **Did it**, **Another option** and **Not now**, and every walk is saved to *Checkins*. |
| **Today** | Tap an item to log it, grouped by block of the day. *Noticed* holds the unideal items. Undo removes your last tap. |
| **Progress** | Lifetime XP (always the biggest number), your level, XP by day for each domain, weekly goals, what you noticed this week, and recent check-ins. |
| **Edit** | Edit what you track, the Guide me tree (with a map and a tree check), and settings. |
| **Setup** | Mac only. Connect the sheet, get the phone setup block, or quit. |

## The sheet (you can edit it directly)

- **Items**: what you track.
  - **Domain** is Physical, Mental or Spiritual. **Kind** is Good or Unideal. **Period** is Daily or Weekly.
  - **Target** is how many times per period counts as done. **XP** is per log.
  - **Priority** is Floor, High, Normal or Low. **Floor** means non-negotiable.
  - **Block** is the group it appears under on Today.
  - **Tags** are free words such as `5min`, `reset` or `move`.
  - **Counters** applies to unideal items only. It lists the tags Guide me favours after you log one.
- **Questions**: one row per choice. Rows that share a **Node** make one question, and the walk starts at `start`. **Next** is another Node or an Action.
- **Actions**: **Picks from** is an ordered list of tags, domains, priorities or item names. Join two with `+` to require both, e.g. `Spiritual+low-energy`. Items already done this period are skipped. **Fallback** shows when nothing is left.
- **Log**, **Checkins**: written by the app.
- **Settings**: time zone, the hour the day starts (late-night logs count for the day before), the week's start day, and XP per level.

Rows you type into Items without an ID get one automatically.

## Setup on your Mac (once)

1. Put this folder somewhere permanent, e.g. `~/Projects/one-stop`.
2. Clear the download flag so macOS lets the app open: `xattr -dr com.apple.quarantine ~/Projects/one-stop`
3. Push it to a **private** GitHub repo called `one-stop`:
   ```
   cd ~/Projects/one-stop
   git init -b main && git add . && git commit -m "One Stop v1"
   git remote add origin https://github.com/OmarK29/one-stop.git
   git push -u origin main
   ```
4. Make a new, empty Google Sheet.
5. Double-click **One Stop.app**. The first launch takes about a minute. The Setup page shows the key from your CRM if it finds one. Share the sheet with the address it shows, as an **Editor**, paste the sheet link, then click **Connect**. The tabs and starting data are created for you.

Every time you open the app, it pulls the latest code from GitHub first.

## Phone (once)

1. On the Mac app, open **Setup → Put it on your phone** and copy the secrets block.
2. Go to share.streamlit.io and click **Create app**. Pick `one-stop`, branch `main`, file `app.py`. Under **Advanced settings → Secrets**, paste the block, then click **Deploy**.
3. In the app, click **Share** and invite your Gmail. A private repo makes a private app, so only invited people can open it. Community Cloud allows one private app per account.
4. On your iPhone, open the link in Safari, tap **Share**, then **Add to Home Screen**.

Optional extra lock: add `app_password = "something"` to the Secrets.

## Files

| File | What it is |
|---|---|
| `app.py` | Startup, navigation, local vs. hosted mode |
| `logic.py` | XP, done-status, the tree walker and recommender (no Streamlit, easy to test) |
| `store.py` | Google Sheets reads and writes, setup errors |
| `seed.py` | Starting items, questions, actions and settings |
| `views/` | One file per page |
| `launch.sh`, `One Stop.app` | Mac launcher: finds Python, `git pull`, installs packages when they change, opens the browser |

Settings and your key live in `~/.one-stop/`. Logs are in `~/.one-stop/launcher.log` and `~/.one-stop/app.log`.

## Troubleshooting

- **"The app can't open that sheet"**: share the sheet with the service-account address as an **Editor**.
- **"The Google Sheets API is turned off"**: enable it in Google Cloud (the message has the steps), wait a minute, and connect again.
- **The app doesn't open**: double-click **Start One Stop.command** instead. It shows what's happening in a Terminal window.
- **Changes from your phone aren't showing on the Mac**: tap **Refresh from sheet**. Reads are cached for 90 seconds.
