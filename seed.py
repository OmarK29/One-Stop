"""Starting data, written to a brand-new sheet once. Everything here is editable
in the app (Edit page) or directly in the Google Sheet."""

ITEMS_HEADER = ["ID", "Item", "Domain", "Kind", "Period", "Target", "XP",
                "Priority", "Block", "Tags", "Counters", "Active", "Notes"]

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

ITEMS = [[f"I{i:03d}", *row[:10], True, row[10]] for i, row in enumerate(_ITEMS, start=1)]

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
    ["move", "Move", "move", "Ten slow squats, or a lap outside."],
    ["quick", "Quick win", "5min", "Everything quick is done. Rest, or pick anything left."],
    ["medium", "Knock out something that matters", "Floor, High", "Everything important is done. Enjoy a free half hour."],
    ["big", "Deep work", "deep, Floor, High", "Nothing big is left. Pick a project, or rest."],
]

LOG_HEADER = ["Timestamp", "Day", "Item ID", "Item", "Domain", "Kind", "XP", "Source", "Note"]
CHECKINS_HEADER = ["Timestamp", "Day", "Path", "Recommended", "Outcome"]
SETTINGS_HEADER = ["Key", "Value"]
SETTINGS = [
    ["timezone", "America/New_York"],
    ["day_starts_at_hour", 3],
    ["week_starts_on", "Monday"],
    ["xp_per_level", 250],
]

TABS = {
    "Items": (ITEMS_HEADER, ITEMS),
    "Log": (LOG_HEADER, []),
    "Questions": (QUESTIONS_HEADER, QUESTIONS),
    "Actions": (ACTIONS_HEADER, ACTIONS),
    "Checkins": (CHECKINS_HEADER, []),
    "Settings": (SETTINGS_HEADER, SETTINGS),
}
