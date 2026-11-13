"""Pure logic: no Streamlit, no Google. Everything here takes plain data and is easy to test."""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import pandas as pd

DOMAINS = ["Physical", "Mental", "Spiritual"]
KINDS = ["Good", "Unideal", "Group", "Goal", "Identity"]
GROUP_KINDS = ("Group", "Goal", "Identity")  # umbrellas: can't be logged, add up what's beneath
PERIODS = ["Daily", "Weekly"]
PRIORITIES = ["Floor", "High", "Normal", "Low"]
MEASURES = ["Check", "Reps", "Time", "Both"]
INPUTS = ["Reps", "Time", "Weight", "Distance", "Effort"]  # what you can enter when logging; none = yes/no
MEASURE_INPUTS = {"Reps": ["Sets", "Reps"], "Time": ["Time"], "Both": ["Reps", "Time"]}  # for rows without Inputs
UNITS = ["Logs", "Reps", "Minutes"]
SHOWS = ["Auto", "Reps", "Time", "Count"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ---------- small parsers ----------

def to_int(value, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def to_bool(value, default: bool = True) -> bool:
    s = str(value).strip().lower()
    if s == "" or s == "nan":
        return default
    return s not in ("false", "no", "n", "0", "off")


def split_list(value) -> list[str]:
    return [t.strip() for t in re.split(r"[,;]", str(value or "")) if t.strip()]


def pick(options: list[str], value, default: str) -> str:
    """Case-insensitive match against a fixed list, so 'spiritual' in the sheet still works."""
    s = str(value).strip().lower()
    for o in options:
        if o.lower() == s:
            return o
    return default


# ---------- time ----------

@dataclass
class Clock:
    timezone: str = "America/New_York"
    day_starts_at_hour: int = 3
    week_starts_on: str = "Monday"
    _fixed_now: dt.datetime | None = None  # tests only

    @classmethod
    def from_settings(cls, settings: dict) -> "Clock":
        tz = str(settings.get("timezone") or "America/New_York").strip()
        try:
            ZoneInfo(tz)
        except Exception:
            tz = "America/New_York"
        return cls(
            timezone=tz,
            day_starts_at_hour=max(0, min(12, to_int(settings.get("day_starts_at_hour"), 3))),
            week_starts_on=pick(WEEKDAYS, settings.get("week_starts_on"), "Monday"),
        )

    def now(self) -> dt.datetime:
        if self._fixed_now is not None:
            return self._fixed_now
        return dt.datetime.now(ZoneInfo(self.timezone))

    def day_of(self, ts: dt.datetime) -> dt.date:
        return (ts - dt.timedelta(hours=self.day_starts_at_hour)).date()

    def today(self) -> dt.date:
        return self.day_of(self.now())

    def week_start(self, day: dt.date) -> dt.date:
        start = WEEKDAYS.index(self.week_starts_on)
        return day - dt.timedelta(days=(day.weekday() - start) % 7)

    def stamp(self) -> str:
        return self.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------- items ----------

@dataclass
class Item:
    id: str
    name: str
    domain: str
    kind: str
    period: str
    target: int
    xp: int
    priority: str
    block: str
    tags: list[str]
    counters: list[str]
    active: bool
    notes: str
    row: int  # position in the sheet, used for ordering
    parents: list[str] = field(default_factory=list)  # names or IDs, as typed
    step: int = 0  # rung in a progression, 1 = easiest; 0 = not part of one
    measure: str = "Check"
    variants: list[str] = field(default_factory=list)
    unit: str = "Logs"  # what Target counts
    pinned: bool = True
    ancestors: set[str] = field(default_factory=set)  # lowercase names and IDs of every umbrella above
    inputs: list[str] = field(default_factory=list)  # from INPUTS, in that order; empty = yes/no
    sets: bool = False  # logged set by set
    rest: int = 0  # seconds of rest after a set in a workout; 0 = the default from Settings

    @property
    def yes_no(self) -> bool:
        return not self.inputs

    @property
    def good(self) -> bool:
        return self.kind == "Good"

    @property
    def group(self) -> bool:
        """An umbrella of any kind: a skill group, a goal or an identity."""
        return self.kind in GROUP_KINDS

    @property
    def prio_rank(self) -> int:
        return PRIORITIES.index(self.priority)


def parse_items(df: pd.DataFrame) -> list[Item]:
    """Items with Domain and Priority inherited from umbrellas where left blank."""
    items = []
    for pos, r in enumerate(df.to_dict("records")):
        name = str(r.get("Item", "")).strip()
        if not name:
            continue
        kind = pick(KINDS, r.get("Kind"), "Good")
        items.append(Item(
            id=str(r.get("ID", "")).strip() or f"row{pos}",
            name=name,
            domain=pick(DOMAINS, r.get("Domain"), ""),
            kind=kind,
            period=pick(PERIODS, r.get("Period"), "Daily"),
            target=0 if kind == "Unideal" else max(0, to_int(r.get("Target"), 1 if kind == "Good" else 0)),
            xp=max(0, to_int(r.get("XP"), 5)) if kind == "Good" else 0,
            priority=pick(PRIORITIES, r.get("Priority"), ""),
            block=str(r.get("Block", "")).strip() or "Anytime",
            tags=[t.lower() for t in split_list(r.get("Tags"))],
            counters=[t.lower() for t in split_list(r.get("Counters"))],
            active=to_bool(r.get("Active"), True),
            notes=str(r.get("Notes", "")).strip(),
            row=pos,
            parents=split_list(r.get("Parents")),
            step=max(0, to_int(r.get("Step"), 0)),
            measure=pick(MEASURES, r.get("Measure"), "Check"),
            variants=split_list(r.get("Variants")),
            unit=pick(UNITS, r.get("Unit"), "Logs") if kind != "Unideal" else "Logs",
            pinned=to_bool(r.get("Pinned"), True),
            rest=max(0, to_int(r.get("Rest"), 0)),
        ))
        _set_inputs(items[-1], r.get("Inputs"))
    _inherit(items, build_hierarchy(items))
    return items


def _set_inputs(it: Item, raw) -> None:
    """Inputs from the Inputs column, or from the older Measure column when Inputs is blank. Measure is kept
    in step (Check, Reps, Time or Both) for code and sheets that still read it."""
    if it.kind != "Good":
        it.inputs, it.sets, it.measure = [], False, "Check"
        return
    if str(raw or "").strip().upper() in ("TRUE", "FALSE"):  # a stray checkbox, not something typed
        raw = ""
    tokens = {t.lower() for t in split_list(raw)} if str(raw or "").strip() else \
        {t.lower() for t in MEASURE_INPUTS.get(it.measure, [])}
    it.inputs = [i for i in INPUTS if i.lower() in tokens]
    it.sets = "sets" in tokens and bool(it.inputs)
    reps, time_ = "Reps" in it.inputs, "Time" in it.inputs
    it.measure = "Both" if reps and time_ else "Reps" if reps else "Time" if time_ else \
        ("Both" if it.inputs else "Check")


def inputs_text(inputs: list[str], sets: bool) -> str:
    return ", ".join((["Sets"] if sets and inputs else []) + [i for i in INPUTS if i in inputs])


def measure_of(inputs: list[str]) -> str:
    reps, time_ = "Reps" in inputs, "Time" in inputs
    return "Both" if reps and time_ else "Reps" if reps else "Time" if time_ else ("Both" if inputs else "Check")


def _inherit(items: list[Item], h: "Hierarchy") -> None:
    """Blank Domain/Priority come from the nearest umbrella that sets one (highest priority wins
    when there are several parents)."""
    memo: dict[tuple[str, str], str] = {}

    def resolve(iid: str, attr: str, visiting: frozenset) -> str:
        if (iid, attr) in memo:
            return memo[(iid, attr)]
        own = getattr(h.items[iid], attr)
        if not own:
            found = [resolve(p, attr, visiting | {iid}) for p in h.parents.get(iid, []) if p not in visiting]
            found = [f for f in found if f]
            if found:
                own = min(found, key=PRIORITIES.index) if attr == "priority" else found[0]
        memo[(iid, attr)] = own
        return own

    for it in items:
        it.priority = resolve(it.id, "priority", frozenset()) or "Normal"
        it.domain = resolve(it.id, "domain", frozenset()) or "Physical"
        it.ancestors = {x for a in h.ancestors(it.id) for x in (a.lower(), h.items[a].name.lower())}


# ---------- umbrellas ----------

@dataclass
class Hierarchy:
    """Items as a tree. A skill can sit under several umbrellas; only Groups can be parents."""
    items: dict[str, Item]
    parents: dict[str, list[str]]
    children: dict[str, list[str]]
    lookup: dict[str, str]  # lowercase name or ID -> ID
    problems: list[str]

    def find(self, name_or_id: str) -> Item | None:
        iid = self.lookup.get(str(name_or_id).strip().lower())
        return self.items.get(iid) if iid else None

    def ancestors(self, iid: str) -> list[str]:
        out, stack = [], list(self.parents.get(iid, []))
        while stack:
            a = stack.pop(0)
            if a not in out and a != iid:
                out.append(a)
                stack.extend(self.parents.get(a, []))
        return out

    def leaves(self, iid: str) -> list[str]:
        """Loggable items at or under `iid`, each once, in sheet order."""
        out, seen, stack = [], set(), [iid]
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            if self.items[x].group:
                stack.extend(reversed(self.children.get(x, [])))
            else:
                out.append(x)
        return sorted(out, key=lambda i: self.items[i].row)

    def roots(self) -> list[Item]:
        return [it for it in self.items.values() if not self.parents.get(it.id)]

    def skill_roots(self) -> list[Item]:
        """Top-level skill umbrellas (Movement, Hygiene…), not identities or goals."""
        return [it for it in self.items.values() if it.kind == "Group"
                and not any(self.items[p].kind == "Group" for p in self.parents.get(it.id, []))]

    def ladder(self, group_id: str) -> list[Item]:
        """The progression under an umbrella: children with a Step, easiest first."""
        rungs = [self.items[c] for c in self.children.get(group_id, []) if self.items[c].step]
        return sorted(rungs, key=lambda it: (it.step, it.row))

    def ladder_of(self, iid: str) -> str | None:
        """The umbrella whose progression this item is a rung of."""
        if not self.items[iid].step:
            return None
        return next((p for p in self.parents.get(iid, []) if self.ladder(p)), None)

    def path(self, iid: str) -> str:
        """Movement › Hypertrophy › Squats, following first parents (skill umbrellas before goals)."""
        def first(ps: list[str]) -> list[str]:
            return sorted(ps, key=lambda p: self.items[p].kind != "Group")
        names, seen, cur = [], {iid}, first(self.parents.get(iid, []))
        while cur and cur[0] not in seen:
            seen.add(cur[0])
            names.append(self.items[cur[0]].name)
            cur = first(self.parents.get(cur[0], []))
        return " › ".join(reversed(names))


def build_hierarchy(items: list[Item]) -> Hierarchy:
    by_id = {it.id: it for it in items}
    lookup: dict[str, str] = {}
    problems = []
    for it in items:
        key = it.name.lower()
        if key in lookup:
            problems.append(f"Two items are called '{it.name}'. Parents and trackers use the first one.")
        else:
            lookup[key] = it.id
    for it in items:
        lookup.setdefault(it.id.lower(), it.id)
    parents: dict[str, list[str]] = {}
    children: dict[str, list[str]] = defaultdict(list)
    for it in items:
        for token in it.parents:
            pid = lookup.get(token.lower())
            if pid is None:
                problems.append(f"'{it.name}' lists '{token}' as a parent, but there's no item with that name.")
            elif not by_id[pid].group:
                problems.append(f"'{it.name}' lists '{by_id[pid].name}' as a parent, but its Kind isn't Group.")
            elif pid != it.id and pid not in parents.get(it.id, []):
                parents.setdefault(it.id, []).append(pid)
                children[pid].append(it.id)
    h = Hierarchy(by_id, parents, dict(children), lookup, problems)
    for it in items:
        if _loop_members(h, it.id):
            problems.append(f"Loop: '{it.name}' ends up inside itself. Check its Parents.")
    return h


def _loop_members(h: Hierarchy, iid: str) -> set[str]:
    seen, stack = set(), list(h.parents.get(iid, []))
    while stack:
        a = stack.pop()
        if a == iid:
            return {iid}
        if a not in seen:
            seen.add(a)
            stack.extend(h.parents.get(a, []))
    return set()


def validate_items(items: list[Item], trackers: list["TrackerColumn"] | None = None) -> list[str]:
    """Problems with Parents, Steps and tracker columns, for the Edit page."""
    h = build_hierarchy(items)
    issues = list(h.problems)
    for it in items:
        if "," in it.name or ";" in it.name:
            issues.append(f"'{it.name}' has a comma in its name, so Parents and trackers can't point at it.")
        if it.group and not h.children.get(it.id):
            issues.append(f"Umbrella '{it.name}' has nothing under it yet.")
        if it.step and not h.ladder_of(it.id):
            issues.append(f"'{it.name}' has a Step but isn't under an umbrella.")
    for col in trackers or []:
        for token in col.maps_to:
            if h.find(token) is None:
                issues.append(f"Tracker '{col.tracker}', column '{col.column}': there's no item called '{token}'.")
        if not col.maps_to:
            issues.append(f"Tracker '{col.tracker}', column '{col.column}' doesn't map to anything.")
    return issues


# ---------- log ----------

def log_days(log_df: pd.DataFrame, clock: Clock) -> pd.Series:
    """Day of each log row. Uses the Day column; falls back to the timestamp for rows typed by hand."""
    def parse(raw):
        s = str(raw or "").strip()
        if not s:
            return None
        try:
            return pd.to_datetime(s).to_pydatetime()
        except (ValueError, TypeError):
            return None

    out = []
    for r in log_df.to_dict("records"):
        d = parse(r.get("Day"))
        if d is not None:
            out.append(d.date())
            continue
        ts = parse(r.get("Timestamp"))
        out.append(clock.day_of(ts) if ts is not None else None)
    return pd.Series(out, index=log_df.index, dtype=object)


def log_frame(log_df: pd.DataFrame, clock: Clock) -> pd.DataFrame:
    """The log as plain columns: id, day, reps, secs, variant, row (sheet order). Rows without a day are dropped."""
    cols = ["id", "day", "reps", "secs", "variant", "row", "weight", "dist", "effort", "session"]
    if log_df.empty:
        return pd.DataFrame(columns=cols)
    get = lambda c: log_df[c] if c in log_df.columns else pd.Series("", index=log_df.index)
    out = pd.DataFrame({
        "id": get("Item ID").map(lambda v: str(v).strip()),
        "day": log_days(log_df, clock),
        "reps": get("Reps").map(lambda v: max(0, to_int(v, 0))),
        "secs": get("Seconds").map(lambda v: max(0, to_int(v, 0))),
        "variant": get("Variant").map(lambda v: str(v).strip()),
        "row": get("_row") if "_row" in log_df.columns else pd.Series(range(len(log_df)), index=log_df.index),
        "weight": get("Weight").map(lambda v: max(0.0, to_float(v, 0.0))),
        "dist": get("Distance").map(lambda v: max(0.0, to_float(v, 0.0))),
        "effort": get("Effort").map(lambda v: max(0, min(10, to_int(v, 0)))),
        "session": get("Session").map(lambda v: str(v).strip()),
    })
    return out[out["day"].notna()].reset_index(drop=True)


@dataclass
class Totals:
    count: int = 0
    reps: int = 0
    secs: int = 0
    dist: float = 0.0
    volume: float = 0.0  # reps × weight

    def __iadd__(self, other: "Totals") -> "Totals":
        self.count += other.count
        self.reps += other.reps
        self.secs += other.secs
        self.dist += other.dist
        self.volume += other.volume
        return self

    def amount(self, unit: str) -> int:
        return {"Reps": self.reps, "Minutes": self.secs // 60}.get(unit, self.count)


def leaf_totals(frame: pd.DataFrame, start: dt.date | None = None, end: dt.date | None = None,
                by: str = "id") -> dict:
    """Totals per item ID (or per `by` column) for logs between start and end, inclusive."""
    f = frame
    if start is not None:
        f = f[f["day"] >= start]
    if end is not None:
        f = f[f["day"] <= end]
    if f.empty:
        return {}
    f = f.assign(_dist=f["dist"] if "dist" in f else 0.0,
                 _vol=(f["reps"] * f["weight"]) if "weight" in f else 0.0)
    g = f.groupby(by).agg(count=("id", "size"), reps=("reps", "sum"), secs=("secs", "sum"), dist=("_dist", "sum"),
                          vol=("_vol", "sum"))
    return {k: Totals(int(r["count"]), int(r["reps"]), int(r["secs"]), float(r["dist"]), float(r["vol"]))
            for k, r in g.iterrows()}


def totals(h: Hierarchy, frame: pd.DataFrame, start: dt.date | None = None,
           end: dt.date | None = None) -> dict[str, Totals]:
    """Totals per item, rolled up the tree. A skill under two umbrellas that share a grandparent
    counts once at the grandparent."""
    out: dict[str, Totals] = defaultdict(Totals)
    for iid, t in leaf_totals(frame, start, end).items():
        if iid not in h.items:
            continue
        for x in [iid, *h.ancestors(iid)]:
            out[x] += t
    return out


def period_counts(items: list[Item], log_df: pd.DataFrame, clock: Clock, today: dt.date | None = None) -> dict[str, int]:
    """Progress on each item in its current period (today, or this week), counted in its Unit.
    Umbrellas count everything beneath them."""
    today = today or clock.today()
    h = build_hierarchy(items)
    frame = log_frame(log_df, clock)
    day = totals(h, frame, today, today)
    week = totals(h, frame, clock.week_start(today), today)
    return {it.id: (day if it.period == "Daily" else week).get(it.id, Totals()).amount(it.unit) for it in items}


def is_done(item: Item, counts: dict[str, int]) -> bool:
    return item.kind != "Unideal" and item.target > 0 and counts.get(item.id, 0) >= item.target


def current_rung(h: Hierarchy, group_id: str, frame: pd.DataFrame) -> Item | None:
    """The hardest rung you've logged, or the first rung if you haven't started."""
    rungs = h.ladder(group_id)
    if not rungs:
        return None
    logged = set(frame["id"]) if not frame.empty else set()
    done = [r for r in rungs if r.id in logged]
    return done[-1] if done else rungs[0]


def off_rungs(h: Hierarchy, frame: pd.DataFrame) -> set[str]:
    """Rungs that aren't your current one, so suggestions skip them."""
    out = set()
    for gid, it in h.items.items():
        if it.group and h.ladder(gid):
            cur = current_rung(h, gid, frame)
            out |= {r.id for r in h.ladder(gid) if r is not cur}
    return out


def last_log(frame: pd.DataFrame, iid: str) -> dict | None:
    rows = frame[frame["id"] == iid]
    if rows.empty:
        return None
    r = rows.loc[rows["row"].idxmax()]
    return {"reps": int(r["reps"]), "secs": int(r["secs"]), "variant": str(r["variant"]),
            "weight": float(r.get("weight", 0) or 0), "dist": float(r.get("dist", 0) or 0),
            "effort": int(r.get("effort", 0) or 0)}


def last_sets(frame: pd.DataFrame, iid: str, before_session: str = "") -> list[dict]:
    """The sets of the last time you did this (the last session, or the last day), oldest first."""
    rows = frame[(frame["id"] == iid) & ((frame["session"] != before_session) if before_session else True)]
    if rows.empty:
        return []
    last = rows.loc[rows["row"].idxmax()]
    same = rows[rows["session"] == last["session"]] if last["session"] else rows[rows["day"] == last["day"]]
    return [{"reps": int(r.reps), "secs": int(r.secs), "weight": float(r.weight), "dist": float(r.dist),
             "effort": int(r.effort), "variant": str(r.variant)} for r in same.sort_values("row").itertuples()]


def fmt_set(x: dict) -> str:
    """'12 × 25 lb', '1:30', '3.1 mi in 28:00', '✓'."""
    bits = []
    if x.get("reps"):
        bits.append(f"{x['reps']}" + (f" × {x['weight']:g} {WEIGHT_UNIT}" if x.get("weight") else " reps"))
    elif x.get("weight"):
        bits.append(f"{x['weight']:g} {WEIGHT_UNIT}")
    if x.get("dist"):
        bits.append(f"{x['dist']:g} {DIST_UNIT}" + (f" in {fmt_secs(x['secs'])}" if x.get("secs") else ""))
    elif x.get("secs"):
        bits.append(fmt_secs(x["secs"]))
    if x.get("effort"):
        bits.append(f"effort {x['effort']}")
    return " · ".join(bits) or "✓"


BEST_LABELS = {"reps": "reps", "secs": "time", "weight": "weight", "dist": "distance", "volume": "set volume"}


def bests(frame: pd.DataFrame, iid: str) -> dict[str, float]:
    """Your best single log for this item: most reps, longest time, heaviest, farthest, biggest reps × weight."""
    rows = frame[frame["id"] == iid]
    if rows.empty:
        return {}
    return {"reps": float(rows["reps"].max()), "secs": float(rows["secs"].max()), "weight": float(rows["weight"].max()),
            "dist": float(rows["dist"].max()), "volume": float((rows["reps"] * rows["weight"]).max())}


def new_bests(previous: dict[str, float], entry: dict) -> list[str]:
    """What this log beats. Nothing on a first-ever log: there's nothing to beat yet."""
    if not previous:
        return []
    now = {"reps": entry.get("reps", 0), "secs": entry.get("secs", 0), "weight": entry.get("weight", 0),
           "dist": entry.get("dist", 0), "volume": entry.get("reps", 0) * entry.get("weight", 0)}
    out = []
    for k, v in now.items():
        if v and v > previous.get(k, 0):
            if k == "volume" and ("reps" in [o[0] for o in out] or not entry.get("weight")):
                continue
            shown = fmt_secs(int(v)) if k == "secs" else f"{v:g}" + {"weight": f" {WEIGHT_UNIT}",
                                                                      "dist": f" {DIST_UNIT}"}.get(k, "")
            out.append((k, f"{BEST_LABELS[k]} {shown}"))
    return [t for _, t in out]


def recent_ids(frame: pd.DataFrame, limit: int = 8) -> list[str]:
    """Most recently logged item IDs, newest first, each once."""
    out = []
    for iid in frame.sort_values("row", ascending=False)["id"]:
        if iid and iid not in out:
            out.append(iid)
            if len(out) >= limit:
                break
    return out


# ---------- formatting ----------

def fmt_secs(secs: int) -> str:
    h, rem = divmod(int(secs), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_totals(t: Totals | None, show: str = "Auto") -> str:
    """'40 reps · 2:30', '2×', '✓' or '' for nothing."""
    if t is None or not t.count:
        return ""
    if show == "Count":
        return f"{t.count}×"
    if show == "Reps":
        return f"{t.reps} reps" if t.reps else ""
    if show == "Time":
        return fmt_secs(t.secs) if t.secs else ""
    parts = ([f"{t.reps} reps"] if t.reps else []) + ([fmt_secs(t.secs)] if t.secs else []) + \
        ([f"{t.dist:g} {DIST_UNIT}"] if t.dist else [])
    return " · ".join(parts) or ("✓" if t.count == 1 else f"{t.count}×")


DIST_UNIT = "mi"  # set from Settings at startup (set_units)
WEIGHT_UNIT = "lb"


def set_units(settings: dict) -> None:
    global DIST_UNIT, WEIGHT_UNIT
    DIST_UNIT = str(settings.get("distance_unit") or "mi").strip() or "mi"
    WEIGHT_UNIT = str(settings.get("weight_unit") or "lb").strip() or "lb"


def fmt_amount(n: int, unit: str) -> str:
    return {"Reps": f"{n} reps", "Minutes": f"{n} min"}.get(unit, str(n))


# ---------- priorities ----------

def priorities(items: list[Item], counts: dict[str, int], clock: Clock,
               today: dt.date | None = None) -> list[tuple[Item, str]]:
    """What needs attention now: Floor, then High items not done today, then weekly items behind pace
    (only pinned ones or Floor/High, so untargeted skills never crowd it)."""
    today = today or clock.today()
    elapsed = (today - clock.week_start(today)).days + 1
    daily, behind = [], []
    for it in items:
        if not it.active or it.kind == "Unideal" or not it.target or is_done(it, counts):
            continue
        n = counts.get(it.id, 0)
        if it.period == "Daily":
            if it.priority in ("Floor", "High"):
                left = f" · {fmt_amount(n, it.unit)}/{it.target}" if it.target > 1 or it.unit != "Logs" else ""
                daily.append((it.prio_rank, it.row, it, it.priority + left))
        elif it.pinned or it.priority in ("Floor", "High"):
            expected = int(it.target * elapsed / 7 + 0.5)
            if n < expected:
                behind.append((it.prio_rank, it.row, it, f"{fmt_amount(n, it.unit)}/{it.target} · behind pace"))
    return [(it, why) for *_, it, why in sorted(daily, key=lambda x: x[:2]) + sorted(behind, key=lambda x: x[:2])]


def counter_boosts(items: list[Item], counts: dict[str, int]) -> Counter:
    """Tags to favour, from the Counters of unideal items logged today."""
    boosts: Counter = Counter()
    for it in items:
        if not it.good and it.period == "Daily" and counts.get(it.id, 0):
            for tag in it.counters:
                boosts[tag] += counts[it.id]
    return boosts


# ---------- recommendations ----------

def _part_matches(item: Item, part: str) -> bool:
    p = part.strip().lower()
    if not p:
        return False
    if p == "any":
        return True
    return p in {item.id.lower(), item.name.lower(), item.domain.lower(),
                 item.priority.lower(), item.block.lower()} or p in item.tags or p in item.ancestors


def token_matches(item: Item, token: str) -> bool:
    """'move' matches a tag/domain/priority/name/umbrella; 'Spiritual+low-energy' needs both."""
    return all(_part_matches(item, part) for part in token.split("+"))


def recommend(picks_from: str, items: list[Item], counts: dict[str, int], boosts: Counter | None = None,
              week_logs: dict[str, int] | None = None, skip: set[str] | None = None) -> list[Item]:
    """Active good items that match the action's 'Picks from' and aren't done yet, best first.

    Order: earlier token in 'Picks from' > counters today's unideal logs > priority > (for umbrella
    names) least logged this week > sheet order. `skip` drops rungs that aren't your current one.
    """
    boosts = boosts or Counter()
    week_logs = week_logs or {}
    skip = skip or set()
    tokens = split_list(picks_from)
    ranked = []
    for it in items:
        if not it.active or not it.good or it.id in skip or is_done(it, counts):
            continue
        hits = [i for i, tok in enumerate(tokens) if token_matches(it, tok)]
        if not hits:
            continue
        boost = sum(boosts[t] for t in it.tags)
        via_umbrella = any(p.strip().lower() in it.ancestors for p in tokens[hits[0]].split("+"))
        ranked.append(((hits[0], -boost, it.prio_rank, week_logs.get(it.id, 0) if via_umbrella else 0, it.row), it))
    ranked.sort(key=lambda x: x[0])
    return [it for _, it in ranked]


def why(item: Item, counts: dict[str, int], boosts: Counter | None = None) -> str:
    when = "today" if item.period == "Daily" else "this week"
    bits = [item.priority if item.priority != "Normal" else "", item.domain,
            f"{fmt_amount(counts.get(item.id, 0), item.unit)}/{item.target} {when}" if item.target else ""]
    if boosts and any(boosts[t] for t in item.tags):
        bits.append("helps with something you noticed today")
    return " · ".join(b for b in bits if b)


# ---------- decision tree ----------

@dataclass
class Question:
    node: str
    text: str
    choices: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Action:
    node: str
    title: str
    picks_from: str
    fallback: str


@dataclass
class Tree:
    questions: dict[str, Question]
    actions: dict[str, Action]
    start: str | None


def build_tree(questions_df: pd.DataFrame, actions_df: pd.DataFrame) -> Tree:
    questions: dict[str, Question] = {}
    for r in questions_df.to_dict("records"):
        node = str(r.get("Node", "")).strip()
        if not node:
            continue
        q = questions.setdefault(node, Question(node=node, text=""))
        text = str(r.get("Question", "")).strip()
        if text and not q.text:
            q.text = text
        choice, nxt = str(r.get("Choice", "")).strip(), str(r.get("Next", "")).strip()
        if choice:
            q.choices.append((choice, nxt))
    for q in questions.values():
        q.text = q.text or q.node
    actions: dict[str, Action] = {}
    for r in actions_df.to_dict("records"):
        node = str(r.get("Action", "")).strip()
        if not node:
            continue
        actions[node] = Action(node=node, title=str(r.get("Title", "")).strip() or node,
                               picks_from=str(r.get("Picks from", "")).strip(),
                               fallback=str(r.get("Fallback", "")).strip())
    start = "start" if "start" in questions else (next(iter(questions), None))
    return Tree(questions=questions, actions=actions, start=start)


def validate_tree(tree: Tree, items: list[Item] | None = None) -> list[str]:
    issues = []
    if tree.start is None:
        return ["There are no questions. Add one with Node = start."]
    if tree.start != "start":
        issues.append(f"No node called 'start', so the guide begins at '{tree.start}'.")
    clash = set(tree.questions) & set(tree.actions)
    for n in sorted(clash):
        issues.append(f"'{n}' is both a question and an action. Rename one.")
    for q in tree.questions.values():
        if not q.choices:
            issues.append(f"Question '{q.node}' has no choices.")
        for label, nxt in q.choices:
            if not nxt:
                issues.append(f"Question '{q.node}', choice '{label}' has no Next.")
            elif nxt not in tree.questions and nxt not in tree.actions:
                issues.append(f"Question '{q.node}', choice '{label}' goes to '{nxt}', which doesn't exist.")
    # reachability + loops
    seen, stack, loops = set(), [(tree.start, (tree.start,))], set()
    while stack:
        node, trail = stack.pop()
        seen.add(node)
        q = tree.questions.get(node)
        if not q:
            continue
        for _, nxt in q.choices:
            if nxt in trail:
                loops.add(f"{node} → {nxt}")
            elif nxt and nxt not in seen:
                stack.append((nxt, trail + (nxt,)))
    for loop in sorted(loops):
        issues.append(f"Loop: {loop} goes back to an earlier question.")
    for n in sorted((set(tree.questions) | set(tree.actions)) - seen):
        issues.append(f"'{n}' can't be reached from start.")
    if items is not None:
        for a in tree.actions.values():
            if not a.picks_from and not a.fallback:
                issues.append(f"Action '{a.node}' has no Picks from and no Fallback.")
            elif a.picks_from and not any(token_matches(it, tok) for it in items if it.good
                                          for tok in split_list(a.picks_from)):
                issues.append(f"Action '{a.node}': nothing matches '{a.picks_from}', so it will always show its fallback.")
    return issues


def tree_dot(tree: Tree) -> str:
    """Graphviz source for the Edit page's map."""
    def esc(s: str) -> str:
        return s.replace('"', '\\"')
    lines = ['digraph G {', 'rankdir=LR; bgcolor="transparent";',
             'node [fontname="Helvetica", fontsize=11, style="rounded,filled", shape=box, color="#2F7D6D", fillcolor="#E6F2EF"];',
             'edge [fontname="Helvetica", fontsize=9, color="#7A8B87"];']
    for q in tree.questions.values():
        lines.append(f'"{esc(q.node)}" [label="{esc(q.text)}"];')
    for a in tree.actions.values():
        lines.append(f'"{esc(a.node)}" [label="{esc(a.title)}\\n({esc(a.picks_from or "fallback")})", '
                     f'shape=box, fillcolor="#FFF4DD", color="#C98A16"];')
    for q in tree.questions.values():
        for label, nxt in q.choices:
            if nxt:
                lines.append(f'"{esc(q.node)}" -> "{esc(nxt)}" [label="{esc(label)}"];')
    lines.append("}")
    return "\n".join(lines)


# ---------- trackers ----------

@dataclass
class TrackerColumn:
    tracker: str
    column: str
    maps_to: list[str]
    show: str


def parse_trackers(df: pd.DataFrame) -> dict[str, list[TrackerColumn]]:
    """Tracker name -> its columns, in sheet order."""
    out: dict[str, list[TrackerColumn]] = {}
    for r in df.to_dict("records"):
        tracker, column = str(r.get("Tracker", "")).strip(), str(r.get("Column", "")).strip()
        if tracker and column:
            out.setdefault(tracker, []).append(TrackerColumn(
                tracker, column, split_list(r.get("Maps to")), pick(SHOWS, r.get("Show"), "Auto")))
    return out


def column_leaves(h: Hierarchy, col: TrackerColumn) -> list[str]:
    """Every loggable item a tracker column covers, each once."""
    out = []
    for token in col.maps_to:
        it = h.find(token)
        for leaf in (h.leaves(it.id) if it else []):
            if leaf not in out:
                out.append(leaf)
    return out


def tracker_grid(h: Hierarchy, cols: list[TrackerColumn], frame: pd.DataFrame,
                 week0: dt.date) -> tuple[list[dt.date], dict[tuple, Totals]]:
    """The week's days and {(day, column name): Totals}, plus {("week", column name): Totals}.
    Each log counts once per column even if the column maps to an umbrella and a skill inside it."""
    days = [week0 + dt.timedelta(days=i) for i in range(7)]
    week = frame[(frame["day"] >= days[0]) & (frame["day"] <= days[-1])] if not frame.empty else frame
    grid: dict[tuple, Totals] = {}
    for col in cols:
        f = week[week["id"].isin(column_leaves(h, col))] if not week.empty else week
        for day, t in leaf_totals(f, by="day").items():
            grid[(day, col.column)] = t
        grid[("week", col.column)] = leaf_totals(f.assign(_all=1), by="_all").get(1, Totals()) if not f.empty else Totals()
    return days, grid


def weekly_volume(h: Hierarchy, iid: str, frame: pd.DataFrame, clock: Clock, weeks: int = 12) -> pd.DataFrame:
    """Week start, Logs, Reps, Minutes for an item or umbrella over the last `weeks` weeks."""
    leaves = set(h.leaves(iid))
    this_week = clock.week_start(clock.today())
    starts = [this_week - dt.timedelta(weeks=i) for i in reversed(range(weeks))]
    f = frame[frame["id"].isin(leaves)] if not frame.empty else frame
    rows = []
    for w in starts:
        t = leaf_totals(f, w, w + dt.timedelta(days=6), by="id")
        total = Totals()
        for v in t.values():
            total += v
        rows.append({"Week": pd.Timestamp(w), "Logs": total.count, "Reps": total.reps,
                     "Minutes": round(total.secs / 60, 1), "Distance": round(total.dist, 2),
                     "Volume": round(total.volume)})
    return pd.DataFrame(rows)


# ---------- XP ----------

@dataclass
class XPSummary:
    total: int
    today: int
    week: int
    level: int
    into_level: int
    per_level: int


def xp_summary(log_df: pd.DataFrame, clock: Clock, per_level: int = 250) -> XPSummary:
    per_level = max(50, per_level)
    if log_df.empty:
        return XPSummary(0, 0, 0, 1, 0, per_level)
    xp = log_df["XP"].map(lambda v: max(0, to_int(v, 0)))
    days = log_days(log_df, clock)
    today = clock.today()
    week0 = clock.week_start(today)
    total = int(xp.sum())
    t = int(sum(x for x, d in zip(xp, days) if d == today))
    w = int(sum(x for x, d in zip(xp, days) if d is not None and week0 <= d <= today))
    return XPSummary(total, t, w, 1 + total // per_level, total % per_level, per_level)


def daily_frame(log_df: pd.DataFrame, clock: Clock, days: int = 14) -> pd.DataFrame:
    """One row per (day, domain, kind) with count and XP, for the last `days` days."""
    cols = ["Day", "Domain", "Kind", "Count", "XP"]
    if log_df.empty:
        return pd.DataFrame(columns=cols)
    df = log_df.copy()
    df["_day"] = log_days(df, clock)
    df = df[df["_day"].notna()]
    start = clock.today() - dt.timedelta(days=days - 1)
    df = df[df["_day"] >= start]
    if df.empty:
        return pd.DataFrame(columns=cols)
    df["_xp"] = df["XP"].map(lambda v: max(0, to_int(v, 0)))
    df["Domain"] = df["Domain"].map(lambda v: pick(DOMAINS, v, "Physical"))
    df["Kind"] = df["Kind"].map(lambda v: pick(KINDS, v, "Good"))
    out = (df.groupby(["_day", "Domain", "Kind"]).agg(Count=("_xp", "size"), XP=("_xp", "sum"))
             .reset_index().rename(columns={"_day": "Day"}))
    out["Day"] = pd.to_datetime(out["Day"])
    return out


def to_float(value, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def days_since_good_log(log_df: pd.DataFrame, clock: Clock) -> int | None:
    """Days since the last log that earned XP; None if there's never been one."""
    if log_df.empty:
        return None
    xp = log_df["XP"].map(lambda v: to_int(v, 0))
    days = [d for d, x in zip(log_days(log_df, clock), xp) if d is not None and x > 0]
    return (clock.today() - max(days)).days if days else None


# ---------- sleep and screen time ----------

@dataclass
class DailyNumber:
    """A number entered once a day. Entering it again for the same day replaces it."""
    key: str
    item_id: str  # what the Log's Item ID column holds; there's no Items row for these
    name: str
    domain: str
    at_most: bool  # True: a limit (screen time); False: a goal (sleep)
    goal_min: int
    xp: int = 5

    def met(self, minutes: int) -> bool:
        return minutes <= self.goal_min if self.at_most else minutes >= self.goal_min

    def entry(self, minutes: int) -> tuple[str, int]:
        """Kind and XP for a log row. Going over a limit is just noticed, like any unideal item."""
        if self.met(minutes):
            return "Good", self.xp
        return ("Unideal", 0) if self.at_most else ("Good", 0)

    def as_item(self) -> Item:
        return Item(id=self.item_id, name=self.name, domain=self.domain, kind="Good", period="Daily", target=0,
                    xp=self.xp, priority="Normal", block="", tags=[], counters=[], active=True, notes="", row=10**6,
                    measure="Time", unit="Minutes", pinned=False)


def daily_numbers(settings: dict) -> list[DailyNumber]:
    sleep = round(to_float(settings.get("sleep_goal_hours"), 7.5) * 60)
    screen = round(to_float(settings.get("screen_time_limit_hours"), 2) * 60)
    out = []
    if to_bool(settings.get("track_sleep"), True):
        out.append(DailyNumber("sleep", "SLEEP", "Sleep", "Physical", False, max(0, sleep)))
    if to_bool(settings.get("track_screen_time"), True):
        out.append(DailyNumber("screen", "SCREEN", "Screen time", "Mental", True, max(0, screen)))
    return out


def number_values(frame: pd.DataFrame, item_id: str) -> dict[dt.date, int]:
    """Minutes per day for a daily number; the latest entry wins if there are several."""
    f = frame[frame["id"] == item_id] if not frame.empty else frame
    if f.empty:
        return {}
    latest = f.sort_values("row").groupby("day").tail(1)
    return {d: int(s) // 60 for d, s in zip(latest["day"], latest["secs"])}


def fmt_hm(minutes: int | float) -> str:
    h, m = divmod(int(round(minutes)), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


# ---------- timers ----------

TIMER_MODES = ["Stopwatch", "Countdown", "Interval", "Counter"]
LADDER_MODE = "Ladder"  # an ease ladder run, kept in the Timers tab: Label = ladder, Reps = step index


@dataclass
class Timer:
    id: str
    item_id: str
    label: str
    mode: str
    length: int  # countdown seconds
    started: float | None  # Unix time it was last started; None while paused
    elapsed: float  # seconds banked before `started`
    reps: int
    row: int
    options: dict = field(default_factory=dict)  # repeat, delay, work, rest, rounds, color
    board: str = ""

    @property
    def running(self) -> bool:
        return self.started is not None

    def seconds(self, now: float) -> int:
        """Seconds run so far; negative while a delayed start is still counting down to its start."""
        return int(self.elapsed + (now - self.started if self.started is not None else 0))

    def finished(self, now: float) -> bool:
        """Past zero (a countdown keeps counting as overtime), or all interval rounds done."""
        if self.mode == "Interval":
            o = self.options
            return interval_spot(max(0, self.seconds(now)), o.get("work", 0), o.get("rest", 0), o.get("rounds", 0))[3]
        return (self.mode == "Countdown" and self.length > 0 and not self.options.get("repeat")
                and self.seconds(now) >= self.length)

    def logged_secs(self, now: float) -> int:
        """What 'Log' records: the time you actually did, overtime included; for intervals, the work time."""
        s = max(0, self.seconds(now))
        if self.mode == "Counter":
            return 0
        if self.mode == "Interval":
            o = self.options
            return interval_work_secs(s, o.get("work", 0), o.get("rest", 0), o.get("rounds", 0))
        return s


def parse_timers(df: pd.DataFrame) -> list[Timer]:
    out = []
    for r in df.to_dict("records"):
        tid = str(r.get("ID", "")).strip()
        if not tid:
            continue
        started = str(r.get("Started", "")).strip()
        out.append(Timer(id=tid, item_id=str(r.get("Item ID", "")).strip(), label=str(r.get("Label", "")).strip(),
                         mode=pick(TIMER_MODES + [LADDER_MODE, SESSION_MODE], r.get("Mode"), "Stopwatch"), length=max(0, to_int(r.get("Length"), 0)),
                         started=to_float(started) if started else None,
                         elapsed=max(0.0, to_float(r.get("Elapsed"), 0.0)), reps=max(0, to_int(r.get("Reps"), 0)),
                         row=to_int(r.get("_row"), 0), options=timer_options(r.get("Options")),
                         board=str(r.get("Board", "") or "").strip()))
    return out


# ---------- character stats ----------

STATS = ["Strength", "Endurance", "Mobility", "Skill", "Mind", "Spirit"]
# What feeds each stat: item names, umbrella names, domains or tags, like an Action's Picks from.
STAT_SOURCES = {
    "Strength": "Hypertrophy, Isometrics, Calisthenics skill practice, HC workout",
    "Endurance": "Endurance, Plyos / sprints / speed work, 10k steps, Outside walk",
    "Mobility": "Mobility, Hands & ankles work",
    "Skill": "Martial Arts, Calisthenics skill practice",
    "Mind": "Mental",
    "Spirit": "Spiritual",
}
STAT_BLURB = {
    "Strength": "Hypertrophy and holds", "Endurance": "Cardio, walks and speed work",
    "Mobility": "Mobility and joint work", "Skill": "Martial arts and calisthenics skills",
    "Mind": "Everything in the Mental domain", "Spirit": "Everything in the Spiritual domain",
}


def stat_sources(settings: dict) -> dict[str, str]:
    """Settings keys like stat_strength override the defaults."""
    return {s: str(settings.get(f"stat_{s.lower()}") or STAT_SOURCES[s]) for s in STATS}


def stat_level(points: int) -> tuple[int, int, int]:
    """Level, points into it, points the level spans. Level L starts at 25·L·(L−1): 0, 50, 150, 300, 500…"""
    level = 1
    while 25 * (level + 1) * level <= points:
        level += 1
    start = 25 * level * (level - 1)
    return level, points - start, 50 * level


@dataclass
class Stat:
    name: str
    points: int
    week: int
    level: int
    into: int
    span: int


def stats(items: list[Item], log_df: pd.DataFrame, clock: Clock, settings: dict) -> list[Stat]:
    """Each stat's points are the XP of the logs that feed it. One log can feed several stats."""
    by_id = ({it.id: it for it in items} | {n.item_id: n.as_item() for n in daily_numbers(settings)}
             | {LADDER_ID: ladder_item()})
    sources = {s: split_list(v) for s, v in stat_sources(settings).items()}
    feeds = {iid: [s for s, toks in sources.items() if any(token_matches(it, t) for t in toks)]
             for iid, it in by_id.items()}
    pts, week = Counter(), Counter()
    if not log_df.empty:
        week0 = clock.week_start(clock.today())
        for iid, x, d in zip(log_df["Item ID"].map(lambda v: str(v).strip()),
                             log_df["XP"].map(lambda v: max(0, to_int(v, 0))), log_days(log_df, clock)):
            for s in feeds.get(iid, []):
                pts[s] += x
                if d is not None and d >= week0:
                    week[s] += x
    return [Stat(s, pts[s], week[s], *stat_level(pts[s])) for s in STATS]


# ---------- avatar and pet ----------

BELTS = [(1, "White", "#f4f4f2"), (3, "Yellow", "#f2c53d"), (6, "Orange", "#ee8a2c"), (10, "Green", "#3a9b4b"),
         (15, "Blue", "#2f6fd0"), (21, "Purple", "#7b4fc4"), (28, "Brown", "#7a4b2a"), (36, "Black", "#1c1c1c")]
TITLES = ["Beginner", "Learner", "Apprentice", "Practitioner", "Adept", "Expert", "Master", "Grandmaster"]


def belt(level: int) -> tuple[str, str, str, int | None]:
    """Belt name, colour, title, and the level the next belt comes at."""
    i = max(n for n, (lv, *_) in enumerate(BELTS) if level >= lv)
    nxt = BELTS[i + 1][0] if i + 1 < len(BELTS) else None
    return BELTS[i][1], BELTS[i][2], TITLES[i], nxt


PET_STAGES = [(0, "Egg"), (100, "Hatchling"), (500, "Young"), (1500, "Grown"), (4000, "Elder")]


@dataclass
class Pet:
    name: str
    stage: str
    stage_index: int
    next_at: int | None  # total XP the next stage comes at
    mood: str  # Happy, Content, Sleepy, Hibernating
    line: str


def pet_state(name: str, total_xp: int, days_since: int | None) -> Pet:
    """Grows with lifetime XP. Mood follows how recently you logged. It never gets sick and never leaves."""
    i = max(n for n, (xp, _) in enumerate(PET_STAGES) if total_xp >= xp)
    stage = PET_STAGES[i][1]
    nxt = PET_STAGES[i + 1][0] if i + 1 < len(PET_STAGES) else None
    if days_since == 0:
        mood, line = "Happy", f"{name} is bouncing around. You showed up today."
    elif days_since == 1:
        mood, line = "Content", f"{name} is curled up nearby, waiting for today's first log."
    elif days_since is not None and days_since <= 3:
        mood, line = "Sleepy", f"{name} is napping. One log wakes it up."
    else:
        mood, line = "Hibernating", f"{name} is hibernating, safe and warm. It wakes the moment you log something."
    if stage == "Egg":
        line = f"An egg, warm to the touch. It hatches at {PET_STAGES[1][0]} XP." + (
            " It wiggled when you logged today." if days_since == 0 else "")
    return Pet(name, stage, i, nxt, mood, line)


# ---------- standards ----------

TIERS = ["Needs work", "Fair", "Good", "Very good", "Excellent"]
AGE_BANDS = [30, 40, 50, 60]  # under 30, 30s, 40s, 50s, 60+


@dataclass
class Standard:
    name: str
    names: tuple[str, ...]  # item names it reads, squashed to letters (see _squash)
    metric: str  # "reps" or "secs"
    cuts: dict  # sex -> list of 4 lower bounds (Fair, Good, Very good, Excellent), or per age band
    source: str


def _squash(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


# Rough reference points, not test results: one set in your log isn't a supervised test.
STANDARDS = [
    Standard("Push-ups", ("pushups", "pushup"), "reps",
             {"Male": [[17, 22, 29, 36], [12, 17, 22, 30], [10, 13, 17, 25], [7, 10, 13, 21], [5, 8, 11, 18]],
              "Female": [[10, 15, 21, 30], [8, 13, 20, 27], [5, 11, 15, 24], [2, 7, 11, 21], [2, 5, 12, 17]]},
             "ACSM/CSEP push-up norms by age and sex (max in one set)"),
    Standard("Pull-ups", ("pullups", "pullup"), "reps",
             {"Male": [1, 5, 10, 15], "Female": [1, 2, 4, 8]}, "Common fitness benchmarks (max in one set)"),
    Standard("Squats", ("squat", "squats", "airsquat", "bodyweightsquat"), "reps",
             {"Male": [20, 30, 40, 50], "Female": [15, 25, 35, 45]}, "Common bodyweight benchmarks (max in one set)"),
    Standard("Plank", ("plank",), "secs", {"Any": [30, 60, 120, 180]}, "Common plank-hold benchmarks"),
    Standard("Dead hang", ("deadhang",), "secs",
             {"Male": [30, 60, 90, 120], "Female": [15, 30, 60, 90]}, "Common grip-strength benchmarks"),
    Standard("Wall-sit", ("wallsit", "wallsitheellifted"), "secs",
             {"Male": [25, 50, 75, 100], "Female": [20, 35, 45, 60]}, "Wall-sit test norms (heel lifted is harder)"),
]


def _cuts_for(std: Standard, sex: str, age: int) -> list[int]:
    def one(s: str) -> list[int]:
        c = std.cuts.get(s) or std.cuts.get("Any")
        if c and isinstance(c[0], list):
            c = c[sum(age >= a for a in AGE_BANDS)] if age else c[0]
        return c
    if sex in std.cuts or "Any" in std.cuts:
        return one(sex if sex in std.cuts else "Any")
    m, f = one("Male"), one("Female")  # sex not set: halfway between
    return [round((a + b) / 2) for a, b in zip(m, f)]


@dataclass
class Comparison:
    name: str
    best: int | None
    metric: str
    tier: str | None
    cuts: list[int]
    source: str


def compare_standards(items: list[Item], frame: pd.DataFrame, sex: str, age: int) -> list[Comparison]:
    """Your best single log for each standard's exercise, against the reference tiers."""
    out = []
    for std in STANDARDS:
        ids = {it.id for it in items if not it.group and _squash(it.name) in std.names}
        f = frame[frame["id"].isin(ids)] if ids and not frame.empty else frame.iloc[0:0]
        best = int(f[std.metric].max()) if not f.empty and f[std.metric].max() > 0 else None
        cuts = _cuts_for(std, sex, age)
        tier = TIERS[sum(best >= c for c in cuts)] if best is not None else None
        out.append(Comparison(std.name, best, std.metric, tier, cuts, std.source))
    return out


def active_minutes(items: list[Item], frame: pd.DataFrame, start: dt.date, end: dt.date) -> int:
    """Minutes logged on Physical items (not sleep) between start and end."""
    ids = {it.id for it in items if it.domain == "Physical" and not it.group}
    f = frame[frame["id"].isin(ids) & (frame["day"] >= start) & (frame["day"] <= end)] if not frame.empty else frame
    return int(f["secs"].sum()) // 60 if not f.empty else 0


def stat_days(items: list[Item], frame: pd.DataFrame, settings: dict, stat: str, start: dt.date, end: dt.date) -> int:
    """Distinct days between start and end with a log feeding `stat`."""
    toks = split_list(stat_sources(settings)[stat])
    ids = {it.id for it in items if any(token_matches(it, t) for t in toks)}
    f = frame[frame["id"].isin(ids) & (frame["day"] >= start) & (frame["day"] <= end)] if not frame.empty else frame
    return int(f["day"].nunique()) if not f.empty else 0


# ---------- ease ladders ----------

LADDER_ID = "LADDER"  # Log rows for starting a ladder step; there's no Items row for these
LADDER_XP = 5


@dataclass
class Rung:
    ladder: str
    step: int
    do: str
    minutes: int  # time to start this step before dropping to the next one
    logs_as: str  # item name, or ""


def parse_ladders(df: pd.DataFrame, default_minutes: int = 5) -> dict[str, list[Rung]]:
    """Ladder name -> its steps, the real goal first and the easiest last."""
    out: dict[str, list[Rung]] = {}
    for pos, r in enumerate(df.to_dict("records")):
        name, do = str(r.get("Ladder", "")).strip(), str(r.get("Do", "")).strip()
        if not name or not do:
            continue
        out.setdefault(name, []).append(Rung(name, to_int(r.get("Step"), 1000 + pos), do,
                                             max(1, to_int(r.get("Minutes"), default_minutes)),
                                             str(r.get("Logs as", "") or "").strip()))
    for rungs in out.values():
        rungs.sort(key=lambda g: g.step)
    return out


@dataclass
class LadderSpot:
    index: int  # which step you're on now
    into: float  # seconds into its window
    window: int  # seconds you get to start it
    ran_out: bool  # the easiest step's window has passed too


def ladder_spot(rungs: list[Rung], index: int, started: float, now: float) -> LadderSpot:
    """Where a run is now. Each step's window that passes without a start drops you one step."""
    i, t = max(0, min(index, len(rungs) - 1)), max(0.0, now - started)
    while t >= rungs[i].minutes * 60:
        if i == len(rungs) - 1:
            return LadderSpot(i, rungs[i].minutes * 60, rungs[i].minutes * 60, True)
        t -= rungs[i].minutes * 60
        i += 1
    return LadderSpot(i, t, rungs[i].minutes * 60, False)


def ladder_item() -> Item:
    """Starting counts: it feeds Mind, and the pet notices."""
    return Item(id=LADDER_ID, name="Started a ladder step", domain="Mental", kind="Good", period="Daily", target=0,
                xp=LADDER_XP, priority="Normal", block="", tags=[], counters=[], active=True, notes="", row=10**6,
                pinned=False)


def ladders_for(ladders: dict[str, list[Rung]], h: Hierarchy, item_id: str) -> list[str]:
    """Ladders with a step that logs as this item, or as an umbrella above it."""
    targets = {item_id, *h.ancestors(item_id)}
    out = []
    for name, rungs in ladders.items():
        if any((it := h.find(r.logs_as)) and it.id in targets for r in rungs if r.logs_as):
            out.append(name)
    return out


# ---------- periods (Track page) ----------

PERIODS_VIEW = ["Today", "Week", "Month", "Year"]


def period_range(clock: Clock, period: str, offset: int = 0) -> tuple[dt.date, dt.date, str]:
    """First day, last day and a label for the period `offset` steps back (negative) from now."""
    today = clock.today()
    if period == "Today":
        d = today + dt.timedelta(days=offset)
        return d, d, "Today" if offset == 0 else "Yesterday" if offset == -1 else d.strftime("%a %b %-d")
    if period == "Week":
        w = clock.week_start(today) + dt.timedelta(weeks=offset)
        e = w + dt.timedelta(days=6)
        return w, e, f"{w.strftime('%b %-d')} – {e.strftime('%b %-d' if e.month != w.month else '%-d')}"
    if period == "Month":
        y, m = divmod(today.year * 12 + today.month - 1 + offset, 12)
        first = dt.date(y, m + 1, 1)
        nxt = dt.date(y + (m + 1) // 12, (m + 1) % 12 + 1, 1)
        return first, nxt - dt.timedelta(days=1), first.strftime("%B %Y")
    y = today.year + offset
    return dt.date(y, 1, 1), dt.date(y, 12, 31), str(y)


def days_active(frame: pd.DataFrame, ids, start: dt.date, end: dt.date) -> int:
    f = frame[frame["id"].isin(set(ids)) & (frame["day"] >= start) & (frame["day"] <= end)] if not frame.empty else frame
    return int(f["day"].nunique()) if not f.empty else 0


def activity(frame: pd.DataFrame, ids, start: dt.date, end: dt.date, by: str) -> list[int]:
    """Logs per day (by='day') or per month (by='month') between start and end, for a sparkline."""
    f = frame[frame["id"].isin(set(ids)) & (frame["day"] >= start) & (frame["day"] <= end)] if not frame.empty else frame
    if by == "day":
        n = (end - start).days + 1
        counts = Counter((d - start).days for d in f["day"]) if not f.empty else Counter()
        return [counts.get(i, 0) for i in range(n)]
    counts = Counter(d.month for d in f["day"]) if not f.empty else Counter()
    return [counts.get(m, 0) for m in range(1, 13)]


def walk(h: Hierarchy, gid: str, depth: int = 0, trail: frozenset = frozenset()):
    """(depth, id) for everything under an umbrella, depth-first. A skill under two umbrellas shows under both."""
    for c in h.children.get(gid, []):
        if c in trail or not h.items[c].active:
            continue
        yield depth, c
        if h.items[c].group:
            yield from walk(h, c, depth + 1, trail | {gid})


# ---------- import and export ----------

CSV_COLUMNS = ["Date", "Time", "Item", "Variant", "Set", "Reps", "Duration", "Weight", "Distance", "Effort", "Note"]


def parse_duration(v) -> int | None:
    """'1:30', '1:02:00', '90', '90s', '2m', '1.5 min' → seconds. None if it doesn't read as a time."""
    s = str(v or "").strip().lower()
    if not s:
        return 0
    if re.fullmatch(r"\d+(:\d{1,2}){1,2}", s):
        parts = [int(x) for x in s.split(":")]
        return sum(p * 60 ** i for i, p in enumerate(reversed(parts)))
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(s|sec|secs|seconds|m|min|mins|minutes|h|hr|hrs|hours)?", s)
    if not m:
        return None
    n, u = float(m.group(1)), (m.group(2) or "s")[0]
    return int(round(n * {"s": 1, "m": 60, "h": 3600}[u]))


def export_rows(log_df: pd.DataFrame, clock: Clock, start: dt.date | None = None, end: dt.date | None = None) -> pd.DataFrame:
    """The log in the simple CSV format (CSV_COLUMNS), oldest first."""
    if log_df.empty:
        return pd.DataFrame(columns=CSV_COLUMNS)
    days = log_days(log_df, clock)
    out = []
    for r, d in zip(log_df.to_dict("records"), days):
        if d is None or (start and d < start) or (end and d > end):
            continue
        secs = to_int(r.get("Seconds"), 0)
        out.append({"Date": d.isoformat(), "Time": str(r.get("Timestamp", ""))[11:16], "Item": r.get("Item", ""),
                    "Variant": r.get("Variant", ""), "Set": r.get("Set", ""), "Reps": r.get("Reps", ""),
                    "Duration": fmt_secs(secs) if secs else "", "Weight": r.get("Weight", ""),
                    "Distance": r.get("Distance", ""), "Effort": r.get("Effort", ""), "Note": r.get("Note", "")})
    return pd.DataFrame(out, columns=CSV_COLUMNS)


@dataclass
class ImportRow:
    line: int
    item: Item | None
    raw_item: str
    day: dt.date | None
    time: str
    variant: str
    set_no: int
    reps: int
    secs: int
    weight: float
    dist: float
    effort: int
    note: str
    problem: str  # empty when it's fine
    new_variant: bool = False  # the variant isn't on the item yet; importing adds it


def parse_import(text: str, items: list[Item], today: dt.date) -> list[ImportRow]:
    """Rows in the CSV format, matched to your items by name (close spellings are fine). Columns can be in
    any order and any can be missing except Item; Date defaults to today."""
    import csv
    import difflib
    import io
    lines = [ln for ln in str(text or "").strip().splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        return []
    reader = csv.reader(io.StringIO("\n".join(lines)), skipinitialspace=True)
    rows = list(reader)
    header = [h.strip().lower() for h in rows[0]]
    if "item" not in header:  # no header row: assume the standard order
        header = [c.lower() for c in CSV_COLUMNS]
    else:
        rows = rows[1:]
    by_name = {it.name.lower(): it for it in items if it.active and not it.group and it.kind == "Good"}
    out = []
    for n, r in enumerate(rows, start=1):
        rec = {h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(header)}
        raw = rec.get("item", "")
        item = by_name.get(raw.lower())
        if item is None and raw:
            close = difflib.get_close_matches(raw.lower(), list(by_name), n=1, cutoff=0.75)
            item = by_name[close[0]] if close else None
        problem = "" if item else (f"No item called '{raw}'" if raw else "No item")
        try:
            day = dt.date.fromisoformat(rec["date"]) if rec.get("date") else today
        except ValueError:
            day, problem = None, problem or f"Can't read the date '{rec.get('date')}' (use 2026-11-13)"
        secs = parse_duration(rec.get("duration") or rec.get("seconds") or "")
        if secs is None:
            secs, problem = 0, problem or f"Can't read the duration '{rec.get('duration')}' (use 1:30)"
        variant = rec.get("variant", "")
        known = {v.lower(): v for v in item.variants} if item else {}
        variant = known.get(variant.lower(), variant)
        out.append(ImportRow(n, item, raw, day, rec.get("time", ""), variant, to_int(rec.get("set"), 0),
                             max(0, to_int(rec.get("reps"), 0)), secs, max(0.0, to_float(rec.get("weight"), 0.0)),
                             max(0.0, to_float(rec.get("distance"), 0.0)), max(0, min(10, to_int(rec.get("effort"), 0))),
                             rec.get("note", ""), problem,
                             bool(item and variant and variant.lower() not in known)))
    return out


def ai_template(items: list[Item], today: dt.date) -> str:
    """Instructions to paste into any AI assistant, so it turns what you say into rows One Stop can import."""
    good = [it for it in sorted(items, key=lambda it: it.row) if it.active and it.kind == "Good"]
    lines = [
        "Turn what I tell you about my day into CSV rows for my One Stop app. Reply with only the CSV.",
        f"Header (always include it): {','.join(CSV_COLUMNS)}",
        f"Date is YYYY-MM-DD (today is {today.isoformat()}; use it unless I say another day). Time is HH:MM, "
        "or blank.",
        "Item must be one of the names below, spelled exactly. Variant must be one listed for that item, or blank.",
        "One row per set when I describe sets (Set = 1, 2, 3...). Otherwise one row per thing, Set blank.",
        f"Duration is m:ss or h:mm:ss. Weight is in {WEIGHT_UNIT}, Distance in {DIST_UNIT}. Effort is 1-10 if I "
        "say how hard it felt. Leave anything I didn't mention blank. Quote any field with a comma in it.",
        "If I mention something that isn't in the list, use my words for Item; the app will flag it.",
        "",
        "My items (what each takes):",
    ]
    for it in good:
        what = inputs_text(it.inputs, it.sets) or "yes/no"
        lines.append(f"- {it.name}: {what}" + (f"; variants: {', '.join(it.variants)}" if it.variants else ""))
    lines += ["", "Example:", ",".join(CSV_COLUMNS),
              f"{today.isoformat()},07:10,Push-ups,,1,15,,,,,",
              f"{today.isoformat()},07:12,Push-ups,,2,12,,,,7,",
              f"{today.isoformat()},,Plank,,,,1:30,,,,felt strong",
              f"{today.isoformat()},,Fajr,,,,,,,,"]
    return "\n".join(lines)


# ---------- timer options ----------

TIMER_COLORS = ["blue", "green", "orange", "red", "violet", "gray"]


def timer_options(raw) -> dict:
    """'repeat, delay=10, work=40, rest=20, rounds=8, color=blue' → {'repeat': True, 'delay': 10, ...}."""
    out: dict = {}
    for tok in split_list(raw):
        k, _, v = tok.partition("=")
        k = k.strip().lower()
        out[k] = (v.strip() if k == "color" else to_int(v, 0)) if _ else True
    return out


def options_text(opts: dict) -> str:
    return ", ".join(k if v is True else f"{k}={v}" for k, v in opts.items() if v not in (None, False, 0, ""))


def interval_spot(secs: float, work: int, rest: int, rounds: int) -> tuple[str, int, float, bool]:
    """Phase ('Work' or 'Rest'), round number, seconds left in the phase, and whether all rounds are done."""
    cycle = max(1, work + rest)
    if rounds and secs >= cycle * rounds - rest:
        return "Done", rounds, 0, True
    n, into = divmod(secs, cycle)
    if into < work:
        return "Work", int(n) + 1, work - into, False
    return "Rest", int(n) + 1, cycle - into, False


def interval_work_secs(secs: float, work: int, rest: int, rounds: int) -> int:
    """Seconds of work done so far, for logging."""
    cycle = max(1, work + rest)
    n, into = divmod(max(0.0, secs), cycle)
    total = n * work + min(into, work)
    return int(min(total, work * rounds) if rounds else total)


# ---------- month report ----------

def month_report(items: list[Item], frame: pd.DataFrame, log_df: pd.DataFrame, clock: Clock, start: dt.date,
                 end: dt.date) -> dict:
    """Totals for one month: logs, active days, reps, minutes, distance, sets, workouts, new bests,
    ladder starts and your most-logged skills."""
    by_id = {it.id: it for it in items}
    f = frame[(frame["day"] >= start) & (frame["day"] <= end)] if not frame.empty else frame
    good = f[f["id"].isin({i for i, it in by_id.items() if it.kind == "Good"})] if not f.empty else f
    before = frame[frame["day"] < start] if not frame.empty else frame
    prs = []
    for iid in (good["id"].unique() if not good.empty else []):
        best = bests(before, iid)  # grows as the month goes, so each new best is counted once
        for r in good[good["id"] == iid].sort_values("row").itertuples():
            entry = {"reps": r.reps, "secs": r.secs, "weight": r.weight, "dist": r.dist}
            hit = new_bests(best, entry)
            if hit:
                prs.append(f"{by_id[iid].name}: {', '.join(hit)}")
            now = entry | {"volume": r.reps * r.weight}
            best = {k: max(best.get(k, 0), now[k]) for k in now}
    top = good.groupby("id").size().sort_values(ascending=False).head(5) if not good.empty else pd.Series(dtype=int)
    return {
        "logs": int(len(good)),
        "days": int(f["day"].nunique()) if not f.empty else 0,
        "reps": int(good["reps"].sum()) if not good.empty else 0,
        "minutes": int(good["secs"].sum()) // 60 if not good.empty else 0,
        "distance": float(good["dist"].sum()) if not good.empty else 0.0,
        "sets": int((good["session"] != "").sum()) if not good.empty else 0,
        "workouts": int(f[f["id"] == WORKOUT_ID]["id"].size) if not f.empty else 0,
        "ladder_starts": int(f[f["id"] == LADDER_ID]["id"].size) if not f.empty else 0,
        "bests": prs,
        "top": [(by_id[i].name, int(n)) for i, n in top.items() if i in by_id],
    }


WORKOUT_ID = "WORKOUT"  # a finished workout session in the Log
SESSION_MODE = "Session"  # a running workout, kept in the Timers tab: Item ID = its skills, comma-separated
