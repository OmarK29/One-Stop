"""Pure logic: no Streamlit, no Google. Everything here takes plain data and is easy to test."""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import pandas as pd

DOMAINS = ["Physical", "Mental", "Spiritual"]
KINDS = ["Good", "Unideal"]
PERIODS = ["Daily", "Weekly"]
PRIORITIES = ["Floor", "High", "Normal", "Low"]
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

    @property
    def good(self) -> bool:
        return self.kind == "Good"

    @property
    def prio_rank(self) -> int:
        return PRIORITIES.index(self.priority)


def parse_items(df: pd.DataFrame) -> list[Item]:
    items = []
    for pos, r in enumerate(df.to_dict("records")):
        name = str(r.get("Item", "")).strip()
        if not name:
            continue
        kind = pick(KINDS, r.get("Kind"), "Good")
        items.append(Item(
            id=str(r.get("ID", "")).strip() or f"row{pos}",
            name=name,
            domain=pick(DOMAINS, r.get("Domain"), "Physical"),
            kind=kind,
            period=pick(PERIODS, r.get("Period"), "Daily"),
            target=max(1, to_int(r.get("Target"), 1)) if kind == "Good" else 0,
            xp=max(0, to_int(r.get("XP"), 5)) if kind == "Good" else 0,
            priority=pick(PRIORITIES, r.get("Priority"), "Normal"),
            block=str(r.get("Block", "")).strip() or "Anytime",
            tags=[t.lower() for t in split_list(r.get("Tags"))],
            counters=[t.lower() for t in split_list(r.get("Counters"))],
            active=to_bool(r.get("Active"), True),
            notes=str(r.get("Notes", "")).strip(),
            row=pos,
        ))
    return items


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


def period_counts(items: list[Item], log_df: pd.DataFrame, clock: Clock, today: dt.date | None = None) -> dict[str, int]:
    """How many times each item was logged in its current period (today, or this week)."""
    today = today or clock.today()
    week0 = clock.week_start(today)
    counts = {it.id: 0 for it in items}
    if log_df.empty:
        return counts
    days = log_days(log_df, clock)
    by_id = {it.id: it for it in items}
    for item_id, day in zip(log_df["Item ID"], days):
        it = by_id.get(str(item_id).strip())
        if it is None or day is None:
            continue
        if (it.period == "Daily" and day == today) or (it.period == "Weekly" and week0 <= day <= today):
            counts[it.id] += 1
    return counts


def is_done(item: Item, counts: dict[str, int]) -> bool:
    return item.good and counts.get(item.id, 0) >= item.target


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
                 item.priority.lower(), item.block.lower()} or p in item.tags


def token_matches(item: Item, token: str) -> bool:
    """'move' matches a tag/domain/priority/name; 'Spiritual+low-energy' needs both."""
    return all(_part_matches(item, part) for part in token.split("+"))


def recommend(picks_from: str, items: list[Item], counts: dict[str, int], boosts: Counter | None = None) -> list[Item]:
    """Active good items that match the action's 'Picks from' and aren't done yet, best first.

    Order: earlier token in 'Picks from' > counters today's unideal logs > priority > sheet order.
    """
    boosts = boosts or Counter()
    tokens = split_list(picks_from)
    ranked = []
    for it in items:
        if not it.active or not it.good or is_done(it, counts):
            continue
        hits = [i for i, tok in enumerate(tokens) if token_matches(it, tok)]
        if not hits:
            continue
        boost = sum(boosts[t] for t in it.tags)
        ranked.append(((hits[0], -boost, it.prio_rank, it.row), it))
    ranked.sort(key=lambda x: x[0])
    return [it for _, it in ranked]


def why(item: Item, counts: dict[str, int], boosts: Counter | None = None) -> str:
    when = "today" if item.period == "Daily" else "this week"
    bits = [item.priority if item.priority != "Normal" else "", item.domain,
            f"{counts.get(item.id, 0)}/{item.target} {when}"]
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
