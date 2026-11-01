"""Shared helpers for the pages."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

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

    def display(self, key: str, default: str) -> str:
        return str(self.settings.get(f"display_{key}") or default).strip()

    def today_sections(self) -> list[str]:
        raw = self.settings.get("display_today")
        return TODAY_SECTIONS if raw is None or str(raw).strip() == "" else logic.split_list(raw)


# What Today can show, in order; Settings → Display picks which.
TODAY_SECTIONS = ["Timers", "Priorities", "Sleep & screen time", "Skills", "Pinned", "This week", "Noticed", "Pet"]


def log_item(ctx: Ctx, item: logic.Item, source: str, note: str = "", reps: int = 0, secs: int = 0,
             variant: str = "", day=None) -> None:
    """Append one log row. `day` lets a tracker cell log for an earlier day this week."""
    day = day or ctx.clock.today()
    ctx.store.append("Log", [ctx.clock.stamp(), day.isoformat(), item.id, item.name, item.domain, item.kind,
                             item.xp if item.good else 0, source, note, reps or "", secs or "", variant])
    amount = logic.fmt_totals(logic.Totals(1, reps or 0, secs or 0))
    what = " · ".join(b for b in (item.name, variant, amount if amount != "✓" else "") if b)
    if item.good:
        st.toast(f"+{item.xp} XP · {what}", icon="✅")
    else:
        st.toast(f"Noted: {item.name}. No XP lost.", icon="📝")


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


def start_timer(ctx: Ctx, item: logic.Item | None, mode: str, length: int = 0) -> None:
    ids = [t.id for t in ctx.timers()]
    n = max([logic.to_int(i[1:], 0) for i in ids if i.startswith("T")], default=0) + 1
    ctx.store.append("Timers", [f"T{n:03d}", item.id if item else "", item.name if item else mode, mode, length,
                                "" if mode == "Counter" else round(time.time(), 1), 0, 0, ctx.clock.stamp()])


def dark() -> bool:
    return st.context.theme.type == "dark"
