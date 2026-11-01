"""Edit: what you track, the guide's questions and actions, and settings. Same data as the sheet."""
from __future__ import annotations

from zoneinfo import available_timezones

import pandas as pd
import streamlit as st

import logic
from views.common import Ctx

CC = st.column_config


def page(ctx: Ctx) -> None:
    st.subheader("Edit")
    st.caption("Changes save to your Google Sheet. You can also edit the sheet directly, then tap Refresh.")
    t_items, t_tree, t_settings = st.tabs(["What I track", "Guide me tree", "Settings"])
    with t_items:
        _items(ctx)
    with t_tree:
        _tree(ctx)
    with t_settings:
        _settings(ctx)


def _editor_df(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return df[cols].reset_index(drop=True)


def _save(ctx: Ctx, tab: str, edited: pd.DataFrame, key: str) -> None:
    if st.button(f"Save {tab.lower()}", type="primary", key=f"save_{key}", icon=":material/save:"):
        ctx.store.replace(tab, edited)
        st.toast(f"Saved {tab} to the sheet", icon="💾")
        st.session_state.pop(key, None)
        st.rerun()


def _items(ctx: Ctx) -> None:
    df = ctx.store.read("Items")
    cols = ["ID", "Item", "Domain", "Kind", "Period", "Target", "XP", "Priority", "Block", "Tags",
            "Counters", "Active", "Notes"]
    view = _editor_df(df, cols)
    view["Target"] = view["Target"].map(lambda v: logic.to_int(v, 1))
    view["XP"] = view["XP"].map(lambda v: logic.to_int(v, 5))
    view["Active"] = view["Active"].map(lambda v: logic.to_bool(v, True))
    st.caption("**Floor** = non-negotiable. **Tags** let guide actions find items (e.g. 5min, reset, move). "
               "**Counters** (unideal items only) = tags the guide favours after you log one. "
               "Unideal items never cost XP. Leave ID blank on new rows.")
    edited = st.data_editor(
        view, key="ed_items", num_rows="dynamic", hide_index=True, width="stretch", height=420,
        column_order=cols[1:] + ["ID"],
        column_config={
            "ID": CC.TextColumn(disabled=True, width="small"),
            "Item": CC.TextColumn(required=True, width="medium"),
            "Domain": CC.SelectboxColumn(options=logic.DOMAINS, default="Physical"),
            "Kind": CC.SelectboxColumn(options=logic.KINDS, default="Good"),
            "Period": CC.SelectboxColumn(options=logic.PERIODS, default="Daily"),
            "Target": CC.NumberColumn(min_value=0, max_value=100, step=1, default=1,
                                      help="Times per day or week to count as done"),
            "XP": CC.NumberColumn(min_value=0, max_value=1000, step=1, default=5),
            "Priority": CC.SelectboxColumn(options=logic.PRIORITIES, default="Normal"),
            "Block": CC.TextColumn(help="Group on the Today page, e.g. Morning or Post-Isha", default="Anytime"),
            "Tags": CC.TextColumn(help="Comma-separated, e.g. 5min, reset"),
            "Counters": CC.TextColumn(help="Unideal items only: tags to favour afterwards"),
            "Active": CC.CheckboxColumn(default=True),
        })
    _save(ctx, "Items", edited, "ed_items")


def _tree(ctx: Ctx) -> None:
    q = ctx.store.read("Questions")
    a = ctx.store.read("Actions")
    tree = logic.build_tree(q, a)
    issues = logic.validate_tree(tree, ctx.items())
    if issues:
        st.warning("**Tree check**\n\n" + "\n".join(f"- {i}" for i in issues))
    else:
        st.success("Every path ends on an action.", icon=":material/check:")

    with st.expander("Map", expanded=False):
        st.graphviz_chart(logic.tree_dot(tree), width="stretch")

    st.markdown("**Questions**: one row per choice. Rows with the same Node are one question; "
                "the guide starts at `start`. **Next** is another Node or an Action.")
    edited_q = st.data_editor(
        _editor_df(q, ["Node", "Question", "Choice", "Next"]), key="ed_q", num_rows="dynamic",
        hide_index=True, width="stretch",
        column_config={"Node": CC.TextColumn(required=True, width="small"),
                       "Question": CC.TextColumn(width="large", help="Only needed on the node's first row"),
                       "Choice": CC.TextColumn(width="medium"),
                       "Next": CC.TextColumn(width="small", help="A Node or Action name; the tree check flags typos")})
    _save(ctx, "Questions", edited_q, "ed_q")

    st.markdown("**Actions** end the walk and suggest one item. **Picks from** is an ordered list: tags, "
                "domains, priorities or item names, comma-separated; join with `+` to require both "
                "(e.g. `Spiritual+low-energy`). Items already done are skipped. **Fallback** shows when "
                "nothing is left.")
    edited_a = st.data_editor(
        _editor_df(a, ["Action", "Title", "Picks from", "Fallback"]), key="ed_a", num_rows="dynamic",
        hide_index=True, width="stretch",
        column_config={"Action": CC.TextColumn(required=True, width="small"),
                       "Title": CC.TextColumn(width="medium"),
                       "Picks from": CC.TextColumn(width="medium"),
                       "Fallback": CC.TextColumn(width="large")})
    _save(ctx, "Actions", edited_a, "ed_a")


@st.cache_data
def _zones() -> list[str]:
    return sorted(z for z in available_timezones() if "/" in z and not z.startswith("Etc/"))


def _settings(ctx: Ctx) -> None:
    s, clock = ctx.settings, ctx.clock
    zones = _zones()
    with st.form("settings"):
        tz = st.selectbox("Time zone", zones, index=zones.index(clock.timezone) if clock.timezone in zones else 0)
        start = st.number_input("New day starts at (hour, 0–12)", 0, 12, clock.day_starts_at_hour,
                                help="Late-night logs before this hour count for the previous day.")
        week = st.selectbox("Week starts on", logic.WEEKDAYS, index=logic.WEEKDAYS.index(clock.week_starts_on))
        per_level = st.number_input("XP per level", 50, 5000, ctx.per_level, step=50)
        if st.form_submit_button("Save settings", type="primary"):
            new = dict(s)
            new.update({"timezone": tz, "day_starts_at_hour": int(start), "week_starts_on": week,
                        "xp_per_level": int(per_level)})
            ctx.store.replace("Settings", pd.DataFrame({"Key": list(new), "Value": list(new.values())}))
            st.toast("Settings saved", icon="💾")
            st.rerun()
