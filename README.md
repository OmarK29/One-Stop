# One Stop

Track physical, mental and spiritual habits in one Google Sheet. **Guide me** walks you through a few questions and lands on the one thing worth doing next. You get XP, not streaks. Unideal things are logged for awareness and never cost XP.

The same code runs on your Mac and, hosted free, on your phone. Both read and write the same sheet.

## Pages

| Page | What it does |
|---|---|
| **Guide me** | One question at a time, then **one** action. If that action has an ease ladder, **Hard to start?** starts it at the matching step. That action is the most important item you haven't done yet, chosen from your answers. The buttons are **Did it**, **Another option** and **Not now**, and every walk is saved to *Checkins*. |
| **Today** | Your pet and any running timers at the top, then **Priorities** (Floor and High items not done, weekly items behind pace), **sleep and screen time** for the day, your pinned umbrellas, then pinned items by block of the day. Filter by domain or hide what's done. *Noticed* holds the unideal items. **Browse all** finds anything else. Undo removes your last tap. Settings → Display picks which sections show. |
| **Track** | Everything you log, three ways: **Trackers** (your printed grids), **Goals** (identity → goal → skills) and **Skills** (your umbrellas). Each opens on **Today**; **Week**, **Month** and **Year** show more, and the arrows step back in time. Trackers' Today is a grid of tiles (tap one to log); Week is the full day-by-column grid with **Print week**; Month and Year show progress only (days you did each column, the total, and a small chart). In the trees, tap any row to log to it. **Log something** opens the quick log (recent and pinned first, search, drill down, or **New skill**). On the log screen you can switch to a neighbouring skill or rung in one tap, add a variant with **＋**, see your notes and last time's numbers, and use the stopwatch beside the time fields. Old `/log` and `/trackers?t=…` links open here. |
| **Workout** | A gym-style session for the gym or a planned workout. Start empty or from a tracker (Hypertrophy brings its skills, at your current rung). Each skill shows last time's sets to beat; tick off sets one by one, and a rest timer starts after each (+30s or Skip). New bests are flagged as they happen. Swap progression rungs or add a skill (or a brand-new one) mid-workout. **Finish** gives a summary and +10 XP. Other pages show a "workout running" link while it's on. |
| **Timers** | **Ease ladders** first: when a goal is hard to start, you get a few minutes to start it, and if you don't, it beeps and the step gets easier. Then any number of timers at once: **stopwatch**, **countdown** (keeps counting as overtime instead of stopping; **+1 min**; optional **repeat**), **interval** (work/rest × rounds) and **counter**. Each can have a label, a colour, a delayed start and a skill to log to. **Boards** start a saved set together (Gym, Morning, Intervals), and you can save what's running as a new board. **History** shows what each timer did. |
| **Me** | **Who I'm becoming**: each identity and its goals with this week's work toward them. Then your character (the belt colour follows your level), six stats (Strength, Endurance, Mobility, Skill, Mind, Spirit) built from the XP of what you log, your pet, and **How you compare**: your best set against common fitness norms, weekly active minutes against the WHO guideline, and sleep, screen time and water against typical figures. Stats only go up, and the pet never gets sick or leaves. It just naps when you've been away. |
| **Progress** | Lifetime XP (always the biggest number), your level, XP by day for each domain, weekly goals, 14 days of sleep and screen time against your goal and limit, your umbrellas with totals at every level, weekly volume for any skill, how far up each progression you are, what you noticed this week, and recent check-ins. |
| **Manage** | Everything you log, track and time. **Skills** adds or changes one skill or umbrella at a time: its umbrellas, what you enter when logging, its **variants** (same level, different ways) and its **progression** (harder levels, easiest first). Renaming follows the name into Parents, trackers and Guide me. **All items (table)** edits everything at once. Also trackers, ease ladders, timer boards, **Import / export**, the Guide me tree (with a map and a tree check), and settings. |
| **Setup** | Mac only. Connect the sheet, get the phone setup block, or quit. |

## The sheet (you can edit it directly)

- **Items**: what you track.
  - **Domain** is Physical, Mental or Spiritual. **Kind** is Good, Unideal, Group, Goal or Identity. **Period** is Daily or Weekly.
  - A **Group** is an umbrella (e.g. Movement → Hypertrophy → Squats). It can't be logged; it adds up everything under it.
  - **Identity** and **Goal** are umbrellas too, for who you're becoming and what you're working toward: Identity → Goal → skills. List a goal in a skill's or umbrella's Parents and its logs count toward that goal. The app starts you with a draft set to rename or delete.
  - **Parents** lists the umbrellas an item sits under, comma-separated. More than one is fine (Squats sits under Hypertrophy and Endurance), and it still counts once higher up.
  - **Step** is the item's rung in a progression under its umbrella, 1 = easiest. The app shows your current rung (the hardest one you've logged) and keeps the rest one tap away.
  - **Inputs** is what you enter when logging: any of Reps, Time, Weight, Distance and Effort (1–10), plus `Sets` to log set by set. Blank means yes/no (one tap). Older rows without Inputs use **Measure** (Check, Reps, Time or Both), which the app keeps in step. **Rest** is seconds between sets in a workout (blank = the default in Settings). **Variants** are the same level done different ways, picked when logging, e.g. `Still, Moving, Jump`. A **progression** is different levels: rungs with a **Step** under one umbrella.
  - **Target** is how much per period counts as done, counted in **Unit** (Logs, Reps or Minutes), so "100 push-ups a week" works. 0 means no goal, just tracking. **XP** is per log, however many reps.
  - **Priority** is Floor, High, Normal or Low. **Floor** means non-negotiable. Blank Domain or Priority comes from the umbrella.
  - **Pinned** puts it on Today. **Block** is the group it appears under there.
  - **Tags** are free words such as `5min`, `reset` or `move`.
  - **Counters** applies to unideal items only. It lists the tags Guide me favours after you log one.
- **Trackers**: one row per column of a weekly grid. **Maps to** is one or more items or umbrellas; **Show** is Auto (reps and/or time, else a tick), Reps, Time or Count.
- **Questions**: one row per choice. Rows that share a **Node** make one question, and the walk starts at `start`. **Next** is another Node or an Action.
- **Actions**: **Picks from** is an ordered list of tags, domains, priorities, item names or umbrella names. An umbrella suggests the least-done skill under it this week, at your current rung. Join two with `+` to require both, e.g. `Spiritual+low-energy`. Items already done this period are skipped. **Fallback** shows when nothing is left.
- **Log**, **Checkins**: written by the app. Log has **Reps**, **Seconds**, **Variant**, **Weight**, **Distance**, **Effort**, **Set** and **Session** (which workout a set belongs to) too. Sleep and screen time are Log rows with Item ID `SLEEP` and `SCREEN` (one per day; entering it again replaces it). Screen time over your limit is logged as unideal: noticed, never a penalty.
- **Timers**: running timers, the running ease ladder and the running workout, written by the app.
- **Boards**: one row per timer; rows with the same **Board** start together. **Options**: `repeat`, `delay=10`, `work=40, rest=20, rounds=8`, `color=blue`.
- **Timer history**: what each timer did (logged or discarded), written by the app.
- **Ladders**: one row per step. Rows with the same **Ladder** are one ladder; **Step** 1 is the real goal and higher steps are easier. **Minutes** is how long you get to start a step before it drops to the next (blank = `ladder_minutes` in Settings, 5 to start). **Logs as** is an optional skill that step times or logs. Starting a step is a Log row with Item ID `LADDER`, so you can see which step you usually start at. Add ladders on the Timers page (**New ladder**: one step per line) or on Edit → Ladders.
- **Settings**: time zone, the hour the day starts (late-night logs count for the day before), the week's start day, XP per level, display options (`display_*`), sleep goal and screen-time limit, your age and sex for the fitness norms, your character's look, and your pet's name. All of these are on Edit → Settings. Add a row such as `stat_strength` = `Hypertrophy, Isometrics` to change what feeds a stat.

**Dark mode** follows your phone or Mac. To choose yourself, open the ⋮ menu (top right) → Settings → Choose app theme.

Rows you type into Items without an ID get one automatically. Item names can't contain commas, since Parents and Maps to are comma-separated; Edit flags this, along with unknown parents and loops.

Filters live in the page link, e.g. `…/track?v=Goals&p=Week` or `…/track?t=Hypertrophy`, so you can add a Home Screen icon that opens straight to one view.

Every page shows everything by default; scroll to see it all. To hide sections, use the page's **Show** menu (Today, Me and Progress; Progress also has **Month in review**: totals, new bests, workouts and ladder starts). Your choice is saved in Settings, so it's the same on every device.

New tabs (like Timers, Ladders, Boards and Timer history) and new columns and the draft identities and goals are added automatically the first time new code opens your sheet. Sheets made before umbrellas existed are upgraded once, on first open: the new columns are added, the starter skills and umbrellas are appended (only names you don't already have), and Brush teeth, Shower and a few others are filed under them where Parents is blank.

## Import, export and logging by voice

Manage → **Import / export** reads and writes one simple CSV format:

```
Date,Time,Item,Variant,Set,Reps,Duration,Weight,Distance,Effort,Note
2026-11-13,07:10,Push-ups,Archer,1,15,,,,7,
2026-11-13,,Ruck / walk,Ruck,,,45:00,30,2.4,,
```

Only Item is required; Date defaults to today, Duration takes `1:30`, `90s` or `2 min`, and columns can be in any order. **Template for your AI** gives you instructions (with your own items, inputs and variants) to paste into ChatGPT, Claude or any assistant once; then say what you did and paste its reply into the import box. The preview flags unknown names (and can add them as new skills), adds new variants, and skips rows already in your log, so pasting twice is safe. **Export** downloads the same format for a month, 30 days, a year, or everything.

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

Every time you open the app, it pulls the latest code from GitHub first. If One Stop is already running from older code, it restarts so the new version loads cleanly.

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
| `logic.py` | XP, done-status, umbrellas and totals, priorities, trackers, timers and intervals, ladders, sets and personal bests, import/export, the month report, sleep and screen time, stats, the pet, fitness standards, the tree walker and recommender (no Streamlit, easy to test) |
| `store.py` | Google Sheets reads and writes, setup errors |
| `seed.py` | Starting items, skills, trackers, questions, actions and settings |
| `views/` | One file per page; `log.py` is also the dialog Today and Trackers open |
| `.streamlit/config.toml` | The light and dark themes |
| `launch.sh`, `One Stop.app` | Mac launcher: finds Python, `git pull`, installs packages when they change, opens the browser |

Settings and your key live in `~/.one-stop/`. Logs are in `~/.one-stop/launcher.log` and `~/.one-stop/app.log`.

## Troubleshooting

- **"The app can't open that sheet"**: share the sheet with the service-account address as an **Editor**.
- **"The Google Sheets API is turned off"**: enable it in Google Cloud (the message has the steps), wait a minute, and connect again.
- **The app doesn't open**: double-click **Start One Stop.command** instead. It shows what's happening in a Terminal window.
- **Changes from your phone aren't showing on the Mac**: tap **Refresh from sheet**. Reads are cached for 90 seconds.
