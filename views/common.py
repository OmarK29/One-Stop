"""Shared helpers for the pages."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

import logic
from store import Store

DOMAIN_ICON = {"Physical": "💪", "Mental": "🧠", "Spiritual": "🤲"}


@dataclass
class Ctx:
    store: Store
    clock: logic.Clock
    settings: dict
    cloud: bool
    pages: dict = field(default_factory=dict)  # url path -> st.Page, for links and switch_page

    @property
    def per_level(self) -> int:
        return logic.to_int(self.settings.get("xp_per_level"), 250)

    def items(self) -> list[logic.Item]:
        return logic.parse_items(self.store.read("Items"))

    def log(self):
        return self.store.read("Log")

    def trackers(self) -> dict[str, list[logic.TrackerColumn]]:
        return logic.parse_trackers(self.store.read("Trackers"))

    def timers(self) -> list[logic.Timer]:
        try:
            return logic.parse_timers(self.store.read("Timers"))
        except Exception:  # the tab is new; a sheet that hasn't been upgraded yet just has no timers
            return []

    def boards(self) -> dict[str, list[dict]]:
        """Board name -> its timers (Label, Mode, Length, Item, Options), in sheet order."""
        try:
            df = self.store.read("Boards")
        except Exception:  # the tab is new; a sheet that hasn't been upgraded yet just has none
            return {}
        out: dict[str, list[dict]] = {}
        for r in df.to_dict("records"):
            name = str(r.get("Board", "")).strip()
            mode = logic.pick(logic.TIMER_MODES, r.get("Mode"), "Stopwatch")
            if name:
                out.setdefault(name, []).append({
                    "Label": str(r.get("Label", "")).strip() or mode, "Mode": mode,
                    "Length": max(0, logic.to_int(r.get("Length"), 0)), "Item": str(r.get("Item", "") or "").strip(),
                    "Options": str(r.get("Options", "") or "").strip()})
        return out

    def ladders(self) -> dict[str, list[logic.Rung]]:
        try:
            df = self.store.read("Ladders")
        except Exception:  # the tab is new; a sheet that hasn't been upgraded yet just has none
            return {}
        return logic.parse_ladders(df, logic.to_int(self.settings.get("ladder_minutes"), 5))

    def display(self, key: str, default: str) -> str:
        return str(self.settings.get(f"display_{key}") or default).strip()

    def sections(self, page: str, options: list[str]) -> list[str]:
        """Which sections a page shows. Everything until you hide some with its Show menu."""
        raw = self.settings.get(f"display_{page}")
        if raw is None or str(raw).strip() == "":
            return list(options)
        return [o for o in logic.split_list(raw) if o in options]


def show_menu(ctx: Ctx, page: str, options: list[str], where=None) -> set[str]:
    """A small 'Show' popover to hide sections of a page; the choice is saved to Settings."""
    current = ctx.sections(page, options)
    with (where or st).popover("Show", icon=":material/tune:"):
        st.caption("Sections on this page")
        st.pills("Sections", options, selection_mode="multi", default=current, key=f"show_{page}",
                 label_visibility="collapsed", on_change=_save_sections, args=(ctx, page))
    return set(current)


def _save_sections(ctx: Ctx, page: str) -> None:
    picked = st.session_state.get(f"show_{page}") or []
    save_settings(ctx, {f"display_{page}": ", ".join(picked) or "none"})


def save_settings(ctx: Ctx, updates: dict) -> None:
    new = dict(ctx.settings) | updates
    ctx.store.replace("Settings", pd.DataFrame({"Key": list(new), "Value": list(new.values())}))
    ctx.settings.update(updates)


# What Today can show, in order; its Show menu picks which.
TODAY_SECTIONS = ["Pet", "Timers", "Priorities", "Sleep & screen time", "Skills", "Pinned", "This week", "Noticed"]


def log_item(ctx: Ctx, item: logic.Item, source: str, note: str = "", reps: int = 0, secs: int = 0,
             variant: str = "", day=None, weight: float = 0, dist: float = 0, effort: int = 0, set_no: int = 0,
             session: str = "", xp: int | None = None, frame=None, check_bests: bool = True) -> list[str]:
    """Append one log row. `day` logs for an earlier day; `set_no`/`session` mark a set in a workout.
    Returns any new personal bests (and toasts them)."""
    day = day or ctx.clock.today()
    if frame is None:
        frame = logic.log_frame(ctx.log(), ctx.clock)
    hits = logic.new_bests(logic.bests(frame, item.id), {"reps": reps, "secs": secs, "weight": weight,
                                                         "dist": dist}) if check_bests else []
    earned = (item.xp if xp is None else xp) if item.good else 0
    ctx.store.append_dicts("Log", [{
        "Timestamp": ctx.clock.stamp(), "Day": day.isoformat(), "Item ID": item.id, "Item": item.name,
        "Domain": item.domain, "Kind": item.kind, "XP": earned, "Source": source, "Note": note, "Reps": reps or "",
        "Seconds": secs or "", "Variant": variant, "Weight": weight or "", "Distance": dist or "",
        "Effort": effort or "", "Set": set_no or "", "Session": session}])
    what = " · ".join(b for b in (item.name, variant, logic.fmt_set(
        {"reps": reps, "secs": secs, "weight": weight, "dist": dist})) if b and b != "✓")
    if hits:
        st.toast(f"New best · {item.name}: {', '.join(hits)}", icon="🏆")
    if item.good:
        st.toast((f"+{earned} XP · " if earned else "") + (f"Set {set_no} · " if set_no else "") + what, icon="✅")
    else:
        st.toast(f"Noted: {item.name}. No XP lost.", icon="📝")
    return hits


def add_variant(ctx: Ctx, item: logic.Item, variant: str) -> str:
    """Add a variant to an item right where you are (in the gym, mid-set). Returns the name as saved."""
    variant = variant.strip().replace(",", " /")
    known = {v.lower(): v for v in item.variants}
    if not variant or variant.lower() in known:
        return known.get(variant.lower(), variant)
    df = ctx.store.read("Items", fresh=True)
    match = df[df["ID"].astype(str).str.strip() == item.id]
    if not match.empty:
        ctx.store.update_row("Items", int(match["_row"].iloc[0]), {"Variants": ", ".join(item.variants + [variant])})
        item.variants.append(variant)
        st.toast(f"Added {variant} to {item.name}", icon="➕")
    return variant


def add_skill(ctx: Ctx, name: str, parents: list[str], inputs: list[str], sets: bool,
              variants: list[str] | None = None) -> str | None:
    """A new skill from wherever you are. Returns its ID, or None (with a message) if the name won't work."""
    name = name.strip()
    items = ctx.items()
    if not name:
        st.error("Give it a name.")
        return None
    if "," in name or ";" in name:
        st.error("Names can't contain commas or semicolons. Try / or &.")
        return None
    if any(it.name.lower() == name.lower() for it in items):
        st.error(f"There's already something called {name}.")
        return None
    df = ctx.store.read("Items", fresh=True)
    nums = [logic.to_int(str(i).strip()[1:], 0) for i in df["ID"] if str(i).strip().startswith("I")]
    iid = f"I{max(nums, default=0) + 1:03d}"
    ctx.store.append_dicts("Items", [{
        "ID": iid, "Item": name, "Kind": "Good", "Period": "Weekly", "Target": 0, "XP": 5, "Active": True,
        "Block": "Anytime", "Parents": ", ".join(parents), "Measure": logic.measure_of(inputs),
        "Variants": ", ".join(variants or []), "Pinned": False, "Inputs": logic.inputs_text(inputs, sets)}])
    st.toast(f"Added {name}", icon="➕")
    return iid


def timer_history(ctx: Ctx, t: logic.Timer, outcome: str, secs: int = 0, reps: int = 0) -> None:
    try:
        ctx.store.append_dicts("Timer history", [{"Timestamp": ctx.clock.stamp(), "Label": t.label, "Mode": t.mode,
                                                  "Seconds": secs, "Reps": reps, "Outcome": outcome,
                                                  "Board": t.board}])
    except Exception:  # history is nice to have; never block a log on it
        pass


def log_checkin(ctx: Ctx, path: str, recommended: str, outcome: str) -> None:
    ctx.store.append("Checkins", [ctx.clock.stamp(), ctx.clock.today().isoformat(), path, recommended, outcome])


def refresh_button(ctx: Ctx, key: str) -> None:
    if st.button("Refresh from sheet", key=key, icon=":material/refresh:", type="tertiary"):
        ctx.store.refresh()
        st.rerun()


def set_daily_number(ctx: Ctx, num: logic.DailyNumber, day, minutes: int) -> None:
    """Sleep or screen time for a day. A second entry for the same day replaces the first."""
    kind, xp = num.entry(minutes)
    fresh = ctx.store.read("Log", fresh=True)
    same = fresh[(fresh["Item ID"].astype(str).str.strip() == num.item_id)
                 & (fresh["Day"].astype(str).str.strip() == day.isoformat())] if not fresh.empty else fresh
    row = {"Timestamp": ctx.clock.stamp(), "Day": day.isoformat(), "Item ID": num.item_id, "Item": num.name,
           "Domain": num.domain, "Kind": kind, "XP": xp, "Source": "Today", "Note": "", "Reps": "",
           "Seconds": minutes * 60, "Variant": ""}
    if same.empty:
        ctx.store.append("Log", list(row.values()))
    else:
        ctx.store.update_row("Log", int(same["_row"].iloc[-1]), row)
    verdict = ("under your limit" if num.at_most else "goal met") if num.met(minutes) else \
        ("over your limit, noted" if num.at_most else "under your goal")
    st.toast(f"{num.name} {logic.fmt_hm(minutes)} · {verdict}" + (f" · +{xp} XP" if xp else ""),
             icon="✅" if num.met(minutes) else "📝")


def start_timer(ctx: Ctx, item: logic.Item | None, mode: str, length: int = 0, options: str = "",
                board: str = "", label: str = "") -> None:
    opts = logic.timer_options(options)
    delay = opts.get("delay", 0) if isinstance(opts.get("delay"), int) else 0
    ctx.store.append_dicts("Timers", [{
        "ID": _next_timer_id(ctx), "Item ID": item.id if item else "", "Label": label or (item.name if item else mode),
        "Mode": mode, "Length": length, "Started": "" if mode == "Counter" else round(time.time() + delay, 1),
        "Elapsed": 0, "Reps": 0, "Created": ctx.clock.stamp(), "Options": options, "Board": board}])


def start_ladder(ctx: Ctx, name: str, index: int = 0) -> None:
    """One ladder at a time: starting another replaces the one running."""
    for t in ctx.timers():
        if t.mode == logic.LADDER_MODE:
            fresh = ctx.store.read("Timers", fresh=True)
            match = fresh[fresh["ID"].astype(str).str.strip() == t.id]
            if not match.empty:
                ctx.store.delete_row("Timers", int(match["_row"].iloc[0]))
    ctx.store.append("Timers", [_next_timer_id(ctx), "", name, logic.LADDER_MODE, 0, round(time.time(), 1), 0, index,
                                ctx.clock.stamp()])


def _next_timer_id(ctx: Ctx) -> str:
    ids = [t.id for t in ctx.timers()]
    return f"T{max([logic.to_int(i[1:], 0) for i in ids if i.startswith('T')], default=0) + 1:03d}"


def dark() -> bool:
    return st.context.theme.type == "dark"
