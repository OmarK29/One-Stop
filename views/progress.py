"""Progress: lifetime XP first and largest. No streaks anywhere."""
from __future__ import annotations

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
    weekly = [it for it in items if it.active and it.good and it.period == "Weekly"]
    for it in weekly:
        n = counts.get(it.id, 0)
        st.progress(min(1.0, n / it.target), text=f"{it.name} · {n}/{it.target}")

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
