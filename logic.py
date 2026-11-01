"""Pure logic: no Streamlit, no Google. Everything here takes plain data and is easy to test."""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import pandas as pd

DOMAINS = ["Physical", "Mental", "Spiritual"]
KINDS = ["Good", "Unideal", "Group"]
PERIODS = ["Daily", "Weekly"]
PRIORITIES = ["Floor", "High", "Normal", "Low"]
MEASURES = ["Check", "Reps", "Time", "Both"]
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

    @property
    def good(self) -> bool:
        return self.kind == "Good"

    @property
    def group(self) -> bool:
        return self.kind == "Group"

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
            measure="Check" if kind != "Good" else pick(MEASURES, r.get("Measure"), "Check"),
            variants=split_list(r.get("Variants")),
            unit=pick(UNITS, r.get("Unit"), "Logs") if kind != "Unideal" else "Logs",
            pinned=to_bool(r.get("Pinned"), True),
        ))
    _inherit(items, build_hierarchy(items))
    return items


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
        """Movement › Hypertrophy › Squats, following first parents."""
        names, seen, cur = [], {iid}, self.parents.get(iid, [])
        while cur and cur[0] not in seen:
            seen.add(cur[0])
            names.append(self.items[cur[0]].name)
            cur = self.parents.get(cur[0], [])
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
    cols = ["id", "day", "reps", "secs", "variant", "row"]
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
    })
    return out[out["day"].notna()].reset_index(drop=True)


@dataclass
class Totals:
    count: int = 0
    reps: int = 0
    secs: int = 0

    def __iadd__(self, other: "Totals") -> "Totals":
        self.count += other.count
        self.reps += other.reps
        self.secs += other.secs
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
    g = f.groupby(by).agg(count=("id", "size"), reps=("reps", "sum"), secs=("secs", "sum"))
    return {k: Totals(int(r["count"]), int(r["reps"]), int(r["secs"])) for k, r in g.iterrows()}


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
    return {"reps": int(r["reps"]), "secs": int(r["secs"]), "variant": str(r["variant"])}


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
    parts = ([f"{t.reps} reps"] if t.reps else []) + ([fmt_secs(t.secs)] if t.secs else [])
    return " · ".join(parts) or ("✓" if t.count == 1 else f"{t.count}×")


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
        rows.append({"Week": pd.Timestamp(w), "Logs": total.count, "Reps": total.reps, "Minutes": round(total.secs / 60, 1)})
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
