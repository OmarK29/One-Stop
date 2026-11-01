"""Today: tap to log. Grouped by block of the day; weekly items and 'noticed' items at the end."""
from __future__ import annotations

import streamlit as st

import logic
from views.common import Ctx, log_item, refresh_button


def page(ctx: Ctx) -> None:
    items = [it for it in ctx.items() if it.active]
    log = ctx.log()
    counts = logic.period_counts(items, log, ctx.clock)
    xp = logic.xp_summary(log, ctx.clock, ctx.per_level)
    today = ctx.clock.today()

    good = [it for it in items if it.good]
    floor = [it for it in good if it.priority == "Floor" and it.period == "Daily"]
    floor_done = sum(logic.is_done(it, counts) for it in floor)

    st.subheader(today.strftime("%A, %b %-d"))
    st.markdown(f"<div class='stat-line'><b>{xp.today}</b> XP today · <b>{xp.week}</b> this week · "
                f"Floor <b>{floor_done}/{len(floor)}</b></div>", unsafe_allow_html=True)
    if floor and floor_done == len(floor):
        st.success("Floor's done. The day counts.", icon=":material/verified:")

    # Daily good items, grouped by block in sheet order
    blocks: dict[str, list[logic.Item]] = {}
    for it in good:
        if it.period == "Daily":
            blocks.setdefault(it.block, []).append(it)
    for block, group in blocks.items():
        done = sum(logic.is_done(it, counts) for it in group)
        with st.expander(f"{block} · {done}/{len(group)}", expanded=done < len(group)):
            for it in group:
                _item_button(ctx, it, counts, "d")

    weekly = [it for it in good if it.period == "Weekly"]
    if weekly:
        done = sum(logic.is_done(it, counts) for it in weekly)
        with st.expander(f"This week · {done}/{len(weekly)}", expanded=True):
            for it in weekly:
                _item_button(ctx, it, counts, "w")

    unideal = [it for it in items if not it.good]
    if unideal:
        with st.expander("Noticed (no XP lost)", expanded=False):
            st.caption("Logging these just helps the guide point you at what counters them.")
            for it in unideal:
                n = counts.get(it.id, 0)
                label = it.name + (f"  ·  {n} today" if n else "")
                if st.button(label, key=f"u_{it.id}", width="stretch", icon=":material/add:"):
                    log_item(ctx, it, "Today")
                    st.rerun()

    _undo(ctx, log, today)
    refresh_button(ctx, "today_refresh")


def _item_button(ctx: Ctx, it: logic.Item, counts: dict, prefix: str) -> None:
    n, done = counts.get(it.id, 0), logic.is_done(it, counts)
    progress = f"  ·  {n}/{it.target}" if it.target > 1 else ""
    label = f"{it.name}{progress}"
    if st.button(label, key=f"{prefix}_{it.id}", width="stretch", disabled=done,
                 icon=":material/check_circle:" if done else ":material/radio_button_unchecked:",
                 help=it.notes or None):
        log_item(ctx, it, "Today")
        st.rerun()


def _undo(ctx: Ctx, log, today) -> None:
    if log.empty:
        return
    todays = log[log["Day"].astype(str).str.strip() == today.isoformat()]
    if todays.empty:
        return
    last = todays.loc[todays["_row"].idxmax()]
    stamp = str(last["Timestamp"])[11:16]
    st.write("")
    if st.button(f"Undo last: {last['Item']} ({stamp})", icon=":material/undo:", type="tertiary", key="undo"):
        fresh = ctx.store.read("Log", fresh=True)
        match = fresh[(fresh["Timestamp"] == last["Timestamp"]) & (fresh["Item ID"] == last["Item ID"])]
        if match.empty:
            st.toast("That entry changed in the sheet, so nothing was removed. Check the list and try again.")
        else:
            ctx.store.delete_row("Log", int(match["_row"].iloc[-1]))
            st.toast(f"Removed {last['Item']}")
        st.rerun()
