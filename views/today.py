"""Today: running timers, priorities, sleep and screen time, pinned umbrellas, then pinned items grouped by
block of the day. Weekly items and 'noticed' items at the end. Settings → Display picks which sections show.
Everything else is one tap away in Browse all."""
from __future__ import annotations

import datetime as dt

import streamlit as st

import logic
from views import log as log_view
from views import me, timers
from views.common import Ctx, dark, log_item, refresh_button, set_daily_number

SHOW_PRIORITIES = 5


def page(ctx: Ctx) -> None:
    all_items = ctx.items()
    h = logic.build_hierarchy(all_items)
    log = ctx.log()
    frame = logic.log_frame(log, ctx.clock)
    counts = logic.period_counts(all_items, log, ctx.clock)
    xp = logic.xp_summary(log, ctx.clock, ctx.per_level)
    today = ctx.clock.today()

    show = set(ctx.today_sections())
    with st.container(horizontal=True, vertical_alignment="center"):
        domains = st.pills("Domain", logic.DOMAINS, selection_mode="multi", key="d", bind="query-params",
                           label_visibility="collapsed")
        hide_done = st.toggle("Hide done", key="hide", bind="query-params")

    def shown(it: logic.Item) -> bool:
        return it.active and (not domains or it.domain in domains)

    items = [it for it in all_items if shown(it)]
    good = [it for it in items if it.good]
    floor = [it for it in good if it.priority == "Floor" and it.period == "Daily" and it.target]
    floor_done = sum(logic.is_done(it, counts) for it in floor)

    st.subheader(today.strftime("%A, %b %-d"))
    st.markdown(f"<div class='stat-line'><b>{xp.today}</b> XP today · <b>{xp.week}</b> this week · "
                f"Floor <b>{floor_done}/{len(floor)}</b></div>", unsafe_allow_html=True)
    if floor and floor_done == len(floor):
        st.success("Floor's done. The day counts.", icon=":material/verified:")
    if "Pet" in show:
        _pet_line(ctx, log, xp.total)
    if "Timers" in show:
        timers.strip(ctx)

    if "Priorities" in show:
        _priorities(ctx, items, counts)
    if "Sleep & screen time" in show:
        _numbers(ctx, frame)
    if "Skills" in show:
        _umbrellas(ctx, h, [it for it in items if it.group and it.pinned], counts, frame, hide_done)

    # Pinned daily items, grouped by block in sheet order
    pinned = [it for it in good if it.pinned] if "Pinned" in show else []
    blocks: dict[str, list[logic.Item]] = {}
    for it in pinned:
        if it.period == "Daily":
            blocks.setdefault(it.block, []).append(it)
    for block, group in blocks.items():
        done = sum(logic.is_done(it, counts) for it in group)
        visible = [it for it in group if not (hide_done and logic.is_done(it, counts))]
        if not visible:
            continue
        with st.expander(f"{block} · {done}/{len(group)}", expanded=done < len(group)):
            for it in visible:
                _item_button(ctx, it, counts, "d")

    weekly = [it for it in good if it.pinned and it.period == "Weekly"] if "This week" in show else []
    visible = [it for it in weekly if not (hide_done and logic.is_done(it, counts))]
    if visible:
        done = sum(logic.is_done(it, counts) for it in weekly)
        with st.expander(f"This week · {done}/{len(weekly)}", expanded=True):
            for it in visible:
                _item_button(ctx, it, counts, "w")

    unideal = [it for it in items if not it.good and not it.group] if "Noticed" in show else []
    if unideal:
        with st.expander("Noticed (no XP lost)", expanded=False):
            st.caption("Logging these just helps the guide point you at what counters them.")
            for it in unideal:
                n = counts.get(it.id, 0)
                label = it.name + (f"  ·  {n} today" if n else "")
                if st.button(label, key=f"u_{it.id}", width="stretch", icon=":material/add:"):
                    log_item(ctx, it, "Today")
                    st.rerun()

    if st.button("Browse all", icon=":material/search:", width="stretch", key="browse_all"):
        log_view.open_dialog(ctx, "Log something")
    _undo(ctx, log, today)
    refresh_button(ctx, "today_refresh")


def _pet_line(ctx: Ctx, log, total_xp: int) -> None:
    pet = logic.pet_state(str(ctx.settings.get("pet_name") or "Pip").strip() or "Pip", total_xp,
                          logic.days_since_good_log(log, ctx.clock))
    row = st.container(horizontal=True, wrap=False, vertical_alignment="center")
    with row.container(width=48):
        me.drawing(me.pet_svg(pet, dark()), width=44, key="today_pet", row=True)
    row.caption(pet.line)


def _numbers(ctx: Ctx, frame) -> None:
    """Sleep and screen time: one number a day each. Saving again for the same day replaces it."""
    nums = logic.daily_numbers(ctx.settings)
    if not nums:
        return
    today = ctx.clock.today()
    hour = ctx.clock.now().hour
    summary, missing = [], False
    for n in nums:
        v = logic.number_values(frame, n.item_id)
        day = today if n.key == "sleep" or hour >= 20 else today - dt.timedelta(days=1)
        if day in v:
            summary.append(f"{n.name} {logic.fmt_hm(v[day])}" + (" ✓" if n.met(v[day]) else ""))
        else:
            summary.append(f"{n.name} —")
            missing = True
    with st.expander(" · ".join(summary), icon=":material/bedtime:", expanded=missing):
        for n in nums:
            _number_form(ctx, n, frame, today, hour)


def _number_form(ctx: Ctx, n: logic.DailyNumber, frame, today: dt.date, hour: int) -> None:
    v = logic.number_values(frame, n.item_id)
    with st.form(f"num_{n.key}", border=False):
        if n.key == "sleep":
            day = today
            label = f"Sleep last night · goal {logic.fmt_hm(n.goal_min)}"
        else:
            opts = ["Yesterday", "Today so far"]
            when = st.segmented_control("Day", opts, default=opts[1] if hour >= 20 else opts[0],
                                        key=f"num_day_{n.key}", label_visibility="collapsed") or opts[0]
            day = today if when == opts[1] else today - dt.timedelta(days=1)
            label = f"Screen time · limit {logic.fmt_hm(n.goal_min)} · from Settings → Screen Time"
        st.caption(label)
        c1 = c2 = c3 = st.container(horizontal=True, wrap=False, vertical_alignment="bottom")
        hrs = c1.number_input("Hours", 0, 24, value=None, placeholder="h", key=f"num_h_{n.key}")
        mins = c2.number_input("Minutes", 0, 59, value=None, step=5, placeholder="m", key=f"num_m_{n.key}")
        if c3.form_submit_button("Save"):
            total = int(hrs or 0) * 60 + int(mins or 0)
            if total or hrs == 0 or mins == 0:
                set_daily_number(ctx, n, day, total)
                st.rerun()
    recent = [f"{d.strftime('%a')} {logic.fmt_hm(m)}" for d, m in sorted(v.items(), reverse=True)[:4]]
    if recent:
        st.caption("Recent: " + " · ".join(recent))


def _priorities(ctx: Ctx, items: list[logic.Item], counts: dict) -> None:
    top = logic.priorities(items, counts, ctx.clock)
    if not top:
        return
    st.markdown("#### Priorities")
    for it, why in top[:SHOW_PRIORITIES]:
        _item_button(ctx, it, counts, "p", caption=why)
    if len(top) > SHOW_PRIORITIES:
        with st.expander(f"{len(top) - SHOW_PRIORITIES} more"):
            for it, why in top[SHOW_PRIORITIES:]:
                _item_button(ctx, it, counts, "p", caption=why)


def _umbrellas(ctx: Ctx, h: logic.Hierarchy, groups: list[logic.Item], counts: dict, frame, hide_done: bool) -> None:
    """One row per pinned umbrella with its total. Tap to open it."""
    if not groups:
        return
    today = ctx.clock.today()
    day_t = logic.totals(h, frame, today, today)
    week_t = logic.totals(h, frame, ctx.clock.week_start(today), today)
    rows = []
    for g in groups:
        leaves = [h.items[i] for i in h.leaves(g.id) if h.items[i].active and h.items[i].good]
        targeted = [it for it in leaves if it.target]
        parts, done = [], False
        if g.target:
            parts.append(f"{logic.fmt_amount(counts.get(g.id, 0), g.unit)}/{g.target}")
            done = logic.is_done(g, counts)
        elif targeted:
            n = sum(logic.is_done(it, counts) for it in targeted)
            parts.append(f"{n}/{len(targeted)} done")
            done = n == len(targeted)
        if len(targeted) < len(leaves):  # skills without a goal: show volume instead
            t, w = day_t.get(g.id), week_t.get(g.id)
            parts.append(f"{t.count if t else 0} today · {w.count if w else 0} this week")
        status = " · ".join(parts)
        if not (hide_done and done):
            rows.append((g, status, done))
    if not rows:
        return
    st.markdown("#### Skills")
    for g, status, done in rows:
        if st.button(f"{g.name}  ·  {status}", key=f"g_{g.id}", width="stretch",
                     icon=":material/check_circle:" if done else ":material/folder_open:"):
            log_view.open_dialog(ctx, g.name, scope=[g.id])


def _item_button(ctx: Ctx, it: logic.Item, counts: dict, prefix: str, caption: str = "") -> None:
    n, done = counts.get(it.id, 0), logic.is_done(it, counts)
    progress = f"  ·  {logic.fmt_amount(n, it.unit)}/{it.target}" if it.target > 1 or it.unit != "Logs" else ""
    label = caption and f"{it.name}  ·  {caption}" or f"{it.name}{progress}"
    if st.button(label, key=f"{prefix}_{it.id}", width="stretch", disabled=done,
                 icon=":material/check_circle:" if done else ":material/radio_button_unchecked:",
                 help=it.notes or None):
        if it.group or it.measure != "Check" or it.variants:
            log_view.open_dialog(ctx, it.name, scope=[it.id])
        else:
            log_item(ctx, it, "Today")
            st.rerun()


def _undo(ctx: Ctx, log, today) -> None:
    if log.empty:
        return
    # Day matches today, or it was logged today for an earlier day from Trackers
    todays = log[(log["Day"].astype(str).str.strip() == today.isoformat())
                 | (log["Timestamp"].astype(str).str[:10] == ctx.clock.now().strftime("%Y-%m-%d"))]
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
