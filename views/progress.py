"""Progress: lifetime XP first and largest. No streaks anywhere."""
from __future__ import annotations

import datetime as dt

import altair as alt
import pandas as pd
import streamlit as st

import logic
from views.common import Ctx, refresh_button

# Categorical slots 1–3 of the validated reference palette (pass all-pairs CVD checks).
DOMAIN_COLORS = {"Physical": "#2a78d6", "Mental": "#eb6834", "Spiritual": "#1baf7a"}


def page(ctx: Ctx) -> None:
    items = ctx.items()
    log = ctx.log()
    xp = logic.xp_summary(log, ctx.clock, ctx.per_level)

    st.subheader("Progress")
    st.markdown(f"<div class='hero-xp'>{xp.total:,}<span> XP</span></div>", unsafe_allow_html=True)
    st.progress(xp.into_level / xp.per_level,
                text=f"Level {xp.level} · {xp.per_level - xp.into_level} XP to level {xp.level + 1}")
    st.markdown(f"<div class='stat-line'><b>{xp.today}</b> XP today · <b>{xp.week}</b> this week</div>",
                unsafe_allow_html=True)

    st.markdown("#### XP by day")
    daily = logic.daily_frame(log, ctx.clock, days=14)
    good = daily[daily["Kind"] == "Good"] if not daily.empty else daily
    if good.empty:
        st.caption("Log something on Today or Guide me and it shows up here.")
    else:
        chart = (alt.Chart(good).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=14)
                 .encode(x=alt.X("yearmonthdate(Day):T", title=None, axis=alt.Axis(format="%-m/%-d", grid=False)),
                         y=alt.Y("sum(XP):Q", title="XP", axis=alt.Axis(tickCount=4)),
                         color=alt.Color("Domain:N", scale=alt.Scale(domain=list(DOMAIN_COLORS),
                                                                     range=list(DOMAIN_COLORS.values())),
                                         legend=alt.Legend(orient="top", title=None)),
                         order=alt.Order("Domain:N"),
                         tooltip=[alt.Tooltip("yearmonthdate(Day):T", title="Day", format="%a %b %-d"),
                                  "Domain:N", alt.Tooltip("sum(XP):Q", title="XP")])
                 .properties(height=220))
        st.altair_chart(chart, width="stretch")
        with st.expander("As a table"):
            table = good.pivot_table(index="Day", columns="Domain", values="XP", aggfunc="sum", fill_value=0)
            table.index = table.index.strftime("%a %b %-d")
            st.dataframe(table, width="stretch")

    # Balance this week
    today = ctx.clock.today()
    week0 = ctx.clock.week_start(today)
    week = daily[daily["Day"] >= pd.Timestamp(week0)] if not daily.empty else daily
    st.markdown("#### This week")
    parts = []
    for dom in logic.DOMAINS:
        val = int(week[(week["Domain"] == dom) & (week["Kind"] == "Good")]["XP"].sum()) if not week.empty else 0
        parts.append(f"{dom} <b>{val}</b>")
    st.markdown(f"<div class='stat-line'>{' · '.join(parts)} XP</div>", unsafe_allow_html=True)

    counts = logic.period_counts(items, log, ctx.clock)
    weekly = [it for it in items if it.active and it.good and it.period == "Weekly" and it.target and it.pinned]
    for it in weekly:
        n = counts.get(it.id, 0)
        st.progress(min(1.0, n / it.target), text=f"{it.name} · {logic.fmt_amount(n, it.unit)}/{it.target}")

    _numbers(ctx, log)
    _skills(ctx, items, log)

    noticed = week[week["Kind"] == "Unideal"] if not week.empty else week
    if not noticed.empty:
        st.markdown("#### Noticed this week")
        st.caption("For awareness only. These never cost XP.")
        week_log = log.copy()
        week_log["_day"] = logic.log_days(week_log, ctx.clock)
        week_log = week_log[week_log["_day"].map(lambda d: d is not None and week0 <= d <= today)
                            & (week_log["Kind"].str.lower() == "unideal")]
        summary = week_log.groupby("Item").size().sort_values(ascending=False).rename("Times")
        st.dataframe(summary, width="stretch")

    checkins = ctx.store.read("Checkins")
    if not checkins.empty:
        st.markdown("#### Recent guide check-ins")
        recent = checkins.sort_values("_row", ascending=False).head(10)
        recent = recent.assign(When=recent["Timestamp"].astype(str).str[5:16])
        st.dataframe(recent[["When", "Recommended", "Outcome", "Path"]], hide_index=True, width="stretch")

    refresh_button(ctx, "progress_refresh")


def _numbers(ctx: Ctx, log) -> None:
    """Sleep and screen time for the last 14 days, one chart each, with your goal or limit as a line."""
    nums = logic.daily_numbers(ctx.settings)
    frame = logic.log_frame(log, ctx.clock)
    values = {n.key: logic.number_values(frame, n.item_id) for n in nums}
    if not any(values.values()):
        return
    today = ctx.clock.today()
    days = [today - dt.timedelta(days=i) for i in reversed(range(14))]
    st.markdown("#### Sleep and screen time")
    for n in nums:
        v = values[n.key]
        if not v:
            continue
        df = pd.DataFrame({"Day": [pd.Timestamp(d) for d in days], "Hours": [v.get(d, 0) / 60 for d in days],
                           "Entered": [d in v for d in days]})
        df = df[df["Entered"]]
        got = list(df["Hours"])
        goal = n.goal_min / 60
        word = "limit" if n.at_most else "goal"
        st.markdown(f"**{n.name}** · {sum(got) / len(got):.1f}h a day on average · {word} {goal:g}h")
        color = DOMAIN_COLORS["Mental"] if n.at_most else DOMAIN_COLORS["Physical"]
        bars = (alt.Chart(df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=14, color=color)
                .encode(x=alt.X("yearmonthdate(Day):T", title=None, axis=alt.Axis(format="%-m/%-d", grid=False),
                                scale=alt.Scale(domain=[pd.Timestamp(days[0]).isoformat(),
                                                        pd.Timestamp(days[-1]).isoformat()])),
                        y=alt.Y("Hours:Q", title="Hours", axis=alt.Axis(tickCount=4)),
                        tooltip=[alt.Tooltip("yearmonthdate(Day):T", title="Day", format="%a %b %-d"),
                                 alt.Tooltip("Hours:Q", format=".1f")]))
        rule = alt.Chart(pd.DataFrame({"y": [goal]})).mark_rule(strokeDash=[4, 4], opacity=.6).encode(y="y:Q")
        st.altair_chart((bars + rule).properties(height=160), width="stretch")


def _walk(h: logic.Hierarchy, gid: str, depth: int = 0, trail: frozenset = frozenset()):
    """(depth, id) for everything under an umbrella, depth-first. A skill under two umbrellas shows under both."""
    for c in h.children.get(gid, []):
        if c in trail or not h.items[c].active:
            continue
        yield depth, c
        if h.items[c].group:
            yield from _walk(h, c, depth + 1, trail | {gid})


def _skills(ctx: Ctx, items: list[logic.Item], log) -> None:
    """Umbrella tree with totals at each level, weekly volume for one skill, and progressions."""
    h = logic.build_hierarchy(items)
    roots = [it for it in h.roots() if it.group and it.active]
    if not roots:
        return
    frame = logic.log_frame(log, ctx.clock)
    today = ctx.clock.today()
    t_day = logic.totals(h, frame, today, today)
    t_week = logic.totals(h, frame, ctx.clock.week_start(today), today)
    t_all = logic.totals(h, frame)

    st.markdown("#### Skills")
    domains = st.pills("Domain", logic.DOMAINS, selection_mode="multi", key="pd", bind="query-params",
                       label_visibility="collapsed")
    for g in [r for r in roots if not domains or r.domain in domains]:
        with st.expander(f"{g.name} · {logic.fmt_totals(t_week.get(g.id)) or 'nothing yet'} this week"):
            rows = []
            for depth, iid in [(0, g.id)] + [(d + 1, i) for d, i in _walk(h, g.id)]:
                it = h.items[iid]
                rung = ""
                if it.group and h.ladder(iid):
                    cur, rungs = logic.current_rung(h, iid, frame), h.ladder(iid)
                    rung = f"{cur.name} ({rungs.index(cur) + 1}/{len(rungs)})" if t_all.get(cur.id) else "Not started"
                rows.append({"Skill": "\u2003" * depth + it.name + (" ▸" if it.group else ""),
                             "Today": logic.fmt_totals(t_day.get(iid)), "This week": logic.fmt_totals(t_week.get(iid)),
                             "All time": logic.fmt_totals(t_all.get(iid)), "Rung": rung})
            table = pd.DataFrame(rows)
            if not table["Rung"].any():
                table = table.drop(columns="Rung")
            st.dataframe(table, hide_index=True, width="stretch")

    st.markdown("#### Weekly volume")
    options = [it.id for it in sorted(h.items.values(), key=lambda it: it.row)
               if it.active and (it.group or (it.good and t_all.get(it.id)))]
    pick = st.selectbox("Skill or umbrella", options, key="pv", bind="query-params",
                        format_func=lambda i: " · ".join(b for b in (h.items[i].name, h.path(i)) if b))
    if pick:
        vol = logic.weekly_volume(h, pick, frame, ctx.clock, weeks=12)
        metrics = [m for m in ("Reps", "Minutes", "Logs") if m == "Logs" or vol[m].sum()]
        metric = st.segmented_control("Measure", metrics, default=metrics[0], key="pv_metric",
                                      label_visibility="collapsed") or metrics[0]
        if not vol[metric].sum():
            st.caption("Nothing logged here in the last 12 weeks.")
        else:
            chart = (alt.Chart(vol).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=14,
                                             color=DOMAIN_COLORS["Physical"])
                     .encode(x=alt.X("Week:T", title=None, axis=alt.Axis(format="%-m/%-d", grid=False)),
                             y=alt.Y(f"{metric}:Q", title=metric, axis=alt.Axis(tickCount=4)),
                             tooltip=[alt.Tooltip("Week:T", title="Week of", format="%b %-d"),
                                      alt.Tooltip(f"{metric}:Q")])
                     .properties(height=200))
            st.altair_chart(chart, width="stretch")
            with st.expander("As a table"):
                st.dataframe(vol.assign(Week=vol["Week"].dt.strftime("%b %-d")), hide_index=True, width="stretch")

    ladders = [it for it in sorted(h.items.values(), key=lambda it: it.row) if it.group and it.active and h.ladder(it.id)]
    if ladders:
        st.markdown("#### Progressions")
        for g in ladders:
            rungs, cur = h.ladder(g.id), logic.current_rung(h, g.id, frame)
            pos = rungs.index(cur) + 1 if t_all.get(cur.id) else 0
            text = f"{g.name}: {cur.name} · rung {pos} of {len(rungs)}" if pos else f"{g.name}: not started"
            st.progress(pos / len(rungs), text=text)
