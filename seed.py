"""Starting data, written to a brand-new sheet once. Everything here is editable
in the app (Edit page) or directly in the Google Sheet."""

# New columns go at the end so existing sheets (and their dropdowns) keep their layout.
ITEMS_HEADER = ["ID", "Item", "Domain", "Kind", "Period", "Target", "XP",
                "Priority", "Block", "Tags", "Counters", "Active", "Notes",
                "Parents", "Step", "Measure", "Variants", "Unit", "Pinned"]

# (Item, Domain, Kind, Period, Target, XP, Priority, Block, Tags, Counters, Notes)
_ITEMS = [
    # Prayers: the skeleton of the day
    ("Fajr", "Spiritual", "Good", "Daily", 1, 10, "Floor", "Prayers", "prayer", "", ""),
    ("Duhr", "Spiritual", "Good", "Daily", 1, 10, "Floor", "Prayers", "prayer", "", ""),
    ("Asr", "Spiritual", "Good", "Daily", 1, 10, "Floor", "Prayers", "prayer", "", ""),
    ("Maghrib", "Spiritual", "Good", "Daily", 1, 10, "Floor", "Prayers", "prayer", "", ""),
    ("Isha", "Spiritual", "Good", "Daily", 1, 10, "Floor", "Prayers", "prayer", "", ""),
    # Pre-Fajr
    ("Morning dua", "Spiritual", "Good", "Daily", 1, 5, "Normal", "Pre-Fajr", "5min, low-energy, flare-safe", "", ""),
    ("Wudu", "Spiritual", "Good", "Daily", 1, 5, "Floor", "Pre-Fajr", "5min, reset, flare-safe", "", ""),
    ("Brush teeth", "Physical", "Good", "Daily", 1, 5, "Floor", "Pre-Fajr", "5min, flare-safe", "", ""),
    ("Horse stance", "Physical", "Good", "Daily", 1, 5, "Normal", "Pre-Fajr", "5min, move", "", ""),
    # Post-Fajr
    ("Dhikr", "Spiritual", "Good", "Daily", 1, 5, "High", "Post-Fajr", "5min, reset, low-energy, flare-safe, no-phone", "", ""),
    ("5 min no phone", "Mental", "Good", "Daily", 1, 5, "High", "Post-Fajr", "5min, reset, no-phone, low-energy, flare-safe", "", ""),
    ("Floortime / mobility", "Physical", "Good", "Daily", 1, 5, "Normal", "Post-Fajr", "move, low-energy, flare-safe", "", ""),
    # Morning
    ("RA meds", "Physical", "Good", "Daily", 1, 5, "High", "Morning", "5min, flare-safe", "", ""),
    ("ADHD meds", "Mental", "Good", "Daily", 1, 5, "High", "Morning", "5min", "", ""),
    ("Protein shake", "Physical", "Good", "Daily", 1, 5, "Normal", "Morning", "5min, fuel", "", ""),
    ("Morning class (any length)", "Mental", "Good", "Daily", 1, 5, "Floor", "Morning", "5min, focus", "", "5 minutes counts"),
    ("Outside walk", "Physical", "Good", "Daily", 1, 5, "High", "Morning", "move, outside, reset, low-energy", "", ""),
    # Anytime
    ("10k steps", "Physical", "Good", "Daily", 1, 5, "Normal", "Anytime", "move, outside", "", ""),
    ("120g protein", "Physical", "Good", "Daily", 1, 5, "Normal", "Anytime", "fuel", "", ""),
    ("MyFitnessPal logged", "Physical", "Good", "Daily", 1, 5, "Normal", "Anytime", "5min", "", ""),
    # Post-Isha
    ("HC workout", "Physical", "Good", "Daily", 1, 10, "High", "Post-Isha", "move, deep", "", ""),
    # Sleep setup
    ("Journal entry", "Mental", "Good", "Daily", 1, 5, "Floor", "Sleep setup", "5min, reset, low-energy, flare-safe, no-phone", "", ""),
    ("Shower", "Physical", "Good", "Daily", 1, 5, "Normal", "Sleep setup", "reset", "", ""),
    ("Devices on charge / no screen", "Mental", "Good", "Daily", 1, 5, "High", "Sleep setup", "no-phone", "", ""),
    # Weekly (targets are starting guesses: edit them)
    ("Quran in English", "Spiritual", "Good", "Weekly", 5, 5, "Normal", "This week", "low-energy, no-phone, deep", "", "Target is a guess"),
    ("Quranic Arabic study", "Spiritual", "Good", "Weekly", 3, 10, "Normal", "This week", "deep, focus", "", "Target is a guess"),
    ("Run (half-marathon training)", "Physical", "Good", "Weekly", 3, 10, "Normal", "This week", "move, outside, deep", "", "Target is a guess"),
    ("BJJ class", "Physical", "Good", "Weekly", 2, 10, "Normal", "This week", "move, deep", "", "Target is a guess"),
    ("Calisthenics skill practice", "Physical", "Good", "Weekly", 3, 10, "Normal", "This week", "move, deep", "", "Muscle-up, handstand pushup, splits"),
    # Unideal: logged for awareness, never cost XP. Counters = tags the guide favours afterwards.
    ("Doomscrolling", "Mental", "Unideal", "Daily", 0, 0, "Low", "Noticed", "", "no-phone, reset", ""),
    ("Late-night screens", "Mental", "Unideal", "Daily", 0, 0, "Low", "Noticed", "", "no-phone", ""),
    ("Sat too long without moving", "Physical", "Unideal", "Daily", 0, 0, "Low", "Noticed", "", "move", ""),
    ("Skipped a meal", "Physical", "Unideal", "Daily", 0, 0, "Low", "Noticed", "", "fuel", ""),
    ("Delayed a prayer", "Spiritual", "Unideal", "Daily", 0, 0, "Low", "Noticed", "", "prayer", ""),
]

# Existing items that belong under an umbrella. On an older sheet these are only filled in if Parents is blank.
ITEM_PARENTS = {
    "Brush teeth": "Hygiene",
    "Shower": "Hygiene",
    "Horse stance": "Isometrics",
    "Floortime / mobility": "Mobility",
    "Run (half-marathon training)": "Endurance",
    "BJJ class": "Martial Arts",
}

# Skills and umbrellas. A Group is an umbrella: it can't be logged and adds up everything beneath it.
# Blank Domain and Priority are inherited from the parent. Target 0 = tracked, no goal.
# (Item, Parents, Kind, Measure, Period, Target, Step, Variants, Pinned, Domain, Notes)
_SKILLS = [
    ("Movement", "", "Group", "", "Weekly", 0, "", "", True, "Physical", ""),
    ("Hypertrophy", "Movement", "Group", "", "Weekly", 0, "", "", True, "", ""),
    ("Push-ups", "Hypertrophy", "Good", "Reps", "Weekly", 0, "", "", False, "", ""),
    ("Pull-ups", "Hypertrophy", "Good", "Reps", "Weekly", 0, "", "", False, "", ""),
    ("Squats", "Hypertrophy, Endurance", "Group", "", "Weekly", 0, "", "", False, "", "Progression: Step 1 is easiest"),
    ("Squat", "Squats", "Good", "Reps", "Weekly", 0, 1, "", False, "", ""),
    ("Single-leg squat", "Squats", "Good", "Reps", "Weekly", 0, 2, "", False, "", ""),
    ("Stair squat", "Squats", "Good", "Reps", "Weekly", 0, 3, "1-step, 2-step", False, "", ""),
    ("SL stair squat", "Squats", "Good", "Reps", "Weekly", 0, 4, "1-step, 2-step", False, "", ""),
    ("Single-leg DL", "Hypertrophy", "Good", "Reps", "Weekly", 0, "", "", False, "", ""),
    ("Leg raises", "Hypertrophy", "Good", "Reps", "Weekly", 0, "", "", False, "", ""),
    ("OHP", "Hypertrophy", "Good", "Reps", "Weekly", 0, "", "", False, "", "Overhead press"),
    ("SA row", "Hypertrophy", "Good", "Reps", "Weekly", 0, "", "", False, "", "Single-arm row"),
    ("Dips", "Hypertrophy", "Good", "Reps", "Weekly", 0, "", "", False, "", ""),
    ("Isometrics", "Movement", "Group", "", "Weekly", 0, "", "", False, "", ""),
    ("Wall-sit (heel lifted)", "Isometrics", "Good", "Time", "Weekly", 0, "", "", False, "", ""),
    ("Dead hang", "Isometrics", "Good", "Time", "Weekly", 0, "", "Shoulder-width, Narrow", False, "", ""),
    ("Plank", "Isometrics", "Good", "Time", "Weekly", 0, "", "", False, "", ""),
    ("Bridge / back extension", "Isometrics", "Good", "Both", "Weekly", 0, "", "Bridge, Back extension", False, "", ""),
    ("Mobility", "Movement", "Group", "", "Weekly", 0, "", "", False, "", ""),
    ("Hands & ankles work", "Mobility", "Good", "Both", "Weekly", 0, "", "", False, "", ""),
    ("Splits & mobility", "Mobility", "Good", "Time", "Weekly", 0, "", "", False, "", ""),
    ("Endurance", "Movement", "Group", "", "Weekly", 0, "", "", False, "", ""),
    ("Elliptical", "Endurance", "Good", "Time", "Weekly", 0, "", "", False, "", ""),
    ("Jog", "Endurance", "Good", "Time", "Weekly", 0, "", "", False, "", ""),
    ("Ruck / walk", "Endurance", "Good", "Time", "Weekly", 0, "", "Ruck, Walk", False, "", ""),
    ("Plyos / sprints / speed work", "Movement", "Good", "Both", "Weekly", 0, "", "Plyos, Sprint, Speed work", False, "", ""),
    ("Hygiene", "", "Group", "", "Daily", 0, "", "", True, "Physical", ""),
    ("Floss", "Hygiene", "Good", "Check", "Daily", 1, "", "", False, "", ""),
    ("Oil hair", "Hygiene", "Good", "Check", "Weekly", 2, "", "", False, "", ""),
    ("Moisturize", "Hygiene", "Good", "Check", "Daily", 1, "", "", False, "", ""),
    ("Supplements", "Hygiene", "Good", "Check", "Daily", 1, "", "", False, "", ""),
    ("Compression", "Hygiene", "Good", "Check", "Daily", 1, "", "", False, "", ""),
    ("Water", "Hygiene", "Good", "Check", "Daily", 8, "", "", False, "", "One tap per glass"),
    ("Martial Arts", "", "Group", "", "Weekly", 0, "", "", True, "Physical", ""),
    ("Footwork", "Martial Arts", "Group", "", "Weekly", 0, "", "", False, "", ""),
    ("Circle shuffle in stance", "Footwork", "Good", "Time", "Weekly", 0, "", "", False, "", ""),
    ("Stance transitions", "Footwork", "Good", "Both", "Weekly", 0, "", "", False, "", ""),
    ("Shuffling & evasion", "Footwork", "Good", "Time", "Weekly", 0, "", "", False, "", ""),
    ("Ground Drills", "Martial Arts", "Group", "", "Weekly", 0, "", "", False, "", "BJJ solo drills"),
    ("Roll to stand", "Ground Drills", "Good", "Reps", "Weekly", 0, "", "Forward, Backward", False, "", "Slow and controlled"),
    ("Cartwheel", "Ground Drills", "Good", "Reps", "Weekly", 0, "", "Left, Right", False, "", ""),
    ("All-fours walk", "Ground Drills", "Good", "Both", "Weekly", 0, "", "Front, Back", False, "", "Off hands and feet"),
    ("Shrimp", "Ground Drills", "Good", "Reps", "Weekly", 0, "", "Forward, Backward", False, "", ""),
    ("Bridge & over-shoulder bridge", "Ground Drills", "Good", "Reps", "Weekly", 0, "", "Bridge, Over-shoulder", False, "", ""),
    ("Technical stand-up", "Ground Drills", "Good", "Reps", "Weekly", 0, "", "", False, "", "Getting off the ground"),
    ("Kicks & Knees", "Martial Arts", "Group", "", "Weekly", 0, "", "", False, "", ""),
    *[(f"{k} kick", "Kicks & Knees", "Good", "Reps", "Weekly", 0, "", "Still, Moving, Jump", False, "", "")
      for k in ("Front", "Side", "Back", "Round", "Hook", "Axe")],
    ("Knees", "Kicks & Knees", "Good", "Reps", "Weekly", 0, "", "Still, Moving, Jump", False, "", ""),
    ("Hands & Arms", "Martial Arts", "Group", "", "Weekly", 0, "", "", False, "", ""),
    ("Arm strikes", "Hands & Arms", "Good", "Reps", "Weekly", 0, "", "Jab, Cross, Hook, Uppercut, Elbow", False, "", ""),
    ("Blocking", "Hands & Arms", "Good", "Both", "Weekly", 0, "", "", False, "", ""),
    ("Throw & Catch", "Martial Arts", "Good", "Reps", "Weekly", 0, "", "Accuracy, Distance", False, "", ""),
    ("Play", "Martial Arts", "Good", "Time", "Weekly", 0, "", "", False, "", ""),
    ("Balance & Sense", "Martial Arts", "Group", "", "Weekly", 0, "", "", False, "", "Balance, proprioception, touch"),
    ("Balance", "Balance & Sense", "Good", "Time", "Weekly", 0, "", "", False, "", ""),
    ("Proprioception drills", "Balance & Sense", "Good", "Time", "Weekly", 0, "", "", False, "", ""),
    ("Reaction drills", "Balance & Sense", "Good", "Reps", "Weekly", 0, "", "", False, "", ""),
    ("Offense", "Martial Arts", "Group", "", "Weekly", 0, "", "", False, "", ""),
    ("Shooting", "Offense", "Good", "Reps", "Weekly", 0, "", "Basic, Extended", False, "",
     "Extended: front knee compressed, drive from the back toes"),
]


def skill_row(item_id: str, row: tuple) -> list:
    name, parents, kind, measure, period, target, step, variants, pinned, domain, notes = row
    xp = 5 if kind == "Good" else 0
    return [item_id, name, domain, kind, period, target, xp, "", "", "", "", True, notes,
            parents, step, measure, variants, "", pinned]


ITEMS = [[f"I{i:03d}", *row[:10], True, row[10], ITEM_PARENTS.get(row[0], ""), "", "", "", "", True]
         for i, row in enumerate(_ITEMS, start=1)]
ITEMS += [skill_row(f"I{i:03d}", row) for i, row in enumerate(_SKILLS, start=len(ITEMS) + 1)]
SKILLS = _SKILLS

QUESTIONS_HEADER = ["Node", "Question", "Choice", "Next"]
QUESTIONS = [
    ["start", "Is a prayer time in right now that you haven't prayed?", "Yes", "pray"],
    ["start", "", "No / not sure", "body"],
    ["body", "How's your body right now?", "RA flaring or in pain", "flare"],
    ["body", "", "Tired, low energy", "low"],
    ["body", "", "Okay", "head"],
    ["body", "", "Energized", "time"],
    ["low", "What's going on in your head?", "Scattered or overwhelmed", "reset"],
    ["low", "", "Heavy or down", "gentle"],
    ["low", "", "Fine, just tired", "easy"],
    ["head", "What's your head like?", "Scattered, can't start", "reset"],
    ["head", "", "Restless", "move"],
    ["head", "", "Clear", "time"],
    ["time", "How much time do you have?", "Under 10 min", "quick"],
    ["time", "", "10–30 min", "medium"],
    ["time", "", "30+ min", "big"],
]

ACTIONS_HEADER = ["Action", "Title", "Picks from", "Fallback"]
ACTIONS = [
    ["pray", "Pray", "prayer", "All five are logged today. Sit for a minute of dhikr."],
    ["flare", "Look after your body first", "flare-safe", "Meds, compression, rest. A flare day still counts."],
    ["reset", "Reset your head", "no-phone, reset", "Put the phone in another room for 5 minutes."],
    ["gentle", "Something gentle", "Spiritual+low-energy, low-energy", "Make wudu and sit quietly for a few minutes."],
    ["easy", "One small win", "low-energy, 5min", "Drink some water and rest. Today still counts."],
    ["move", "Move", "move, Movement", "Ten slow squats, or a lap outside."],
    ["quick", "Quick win", "5min", "Everything quick is done. Rest, or pick anything left."],
    ["medium", "Knock out something that matters", "Floor, High", "Everything important is done. Enjoy a free half hour."],
    ["big", "Deep work", "deep, Floor, High", "Nothing big is left. Pick a project, or rest."],
]

LOG_HEADER = ["Timestamp", "Day", "Item ID", "Item", "Domain", "Kind", "XP", "Source", "Note",
              "Reps", "Seconds", "Variant"]
CHECKINS_HEADER = ["Timestamp", "Day", "Path", "Recommended", "Outcome"]
SETTINGS_HEADER = ["Key", "Value"]
SETTINGS = [
    ["timezone", "America/New_York"],
    ["day_starts_at_hour", 3],
    ["week_starts_on", "Monday"],
    ["xp_per_level", 250],
    ["sleep_goal_hours", 7.5],
    ["screen_time_limit_hours", 2],
    ["pet_name", "Pip"],
]

# Printed-style weekly grids. Maps to = skills or umbrellas (comma-separated); Show = Auto, Reps, Time or Count.
TRACKERS_HEADER = ["Tracker", "Column", "Maps to", "Show"]
_TRACKERS = {
    "Movement": [("Wall-sit (heel lifted)", "Wall-sit (heel lifted)"), ("Deadhang (SW or N)", "Dead hang"),
                 ("Plank", "Plank"), ("Bridge or Back Ext.", "Bridge / back extension"),
                 ("Hands & Ankles Work", "Hands & ankles work"),
                 ("Splits & Mobility", "Splits & mobility, Floortime / mobility"),
                 ("Elliptical", "Elliptical"), ("Jog", "Jog, Run (half-marathon training)"),
                 ("Ruck|Walk", "Ruck / walk, Outside walk"),
                 ("Plyos, Sprint, Speed Work", "Plyos / sprints / speed work")],
    "Hypertrophy": [("Push-ups", "Push-ups"), ("Pull-ups", "Pull-ups"), ("SL Stair Squats", "Squats"),
                    ("Single-Leg DL", "Single-leg DL"), ("Leg Raises", "Leg raises"), ("OHP", "OHP"),
                    ("SA Row", "SA row"), ("Dips", "Dips")],
    "Hygiene": [("Brush", "Brush teeth"), ("Floss", "Floss"), ("Shower", "Shower"), ("Oil Hair", "Oil hair"),
                ("Moisturize", "Moisturize"), ("Supplements", "Supplements"), ("Compression", "Compression"),
                ("Water", "Water")],
    "Martial Arts": [("Footwork", "Footwork"), ("Ground Drills", "Ground Drills"),
                     ("Kicks & Knees", "Kicks & Knees"), ("Hands & Arms", "Hands & Arms"),
                     ("Throw & Catch", "Throw & Catch"), ("Play", "Play"),
                     ("Balance & Sense Coord.", "Balance & Sense")],
}
TRACKERS = [[t, col, maps, "Auto"] for t, cols in _TRACKERS.items() for col, maps in cols]

# Running timers and counters, so they survive a closed tab and show on every device.
# Started = when it was last started (Unix seconds), blank while paused; Elapsed = seconds banked before that.
TIMERS_HEADER = ["ID", "Item ID", "Label", "Mode", "Length", "Started", "Elapsed", "Reps", "Created"]

TABS = {
    "Items": (ITEMS_HEADER, ITEMS),
    "Trackers": (TRACKERS_HEADER, TRACKERS),
    "Log": (LOG_HEADER, []),
    "Questions": (QUESTIONS_HEADER, QUESTIONS),
    "Actions": (ACTIONS_HEADER, ACTIONS),
    "Checkins": (CHECKINS_HEADER, []),
    "Settings": (SETTINGS_HEADER, SETTINGS),
    "Timers": (TIMERS_HEADER, []),
}
