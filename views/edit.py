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
    t_items, t_trackers, t_tree, t_settings = st.tabs(["What I track", "Trackers", "Guide me tree", "Settings"])
    with t_items:
        _items(ctx)
    with t_trackers:
        _trackers(ctx)
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
    items = logic.parse_items(df)
    h = logic.build_hierarchy(items)
    issues = logic.validate_items(items, [c for cols in ctx.trackers().values() for c in cols])
    if issues:
        st.warning("**Tree check**\n\n" + "\n".join(f"- {i}" for i in issues))

    c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
    groups = [it for it in items if it.group]
    under = c1.selectbox("Umbrella", [g.id for g in groups], index=None, placeholder="All items", key="ed_under",
                         format_func=lambda i: " › ".join(b for b in (h.path(i), h.items[i].name) if b))
    inactive = c2.toggle("Show inactive", key="ed_inactive")

    cols = ["ID", "Item", "Kind", "Parents", "Step", "Measure", "Variants", "Domain", "Period", "Target", "Unit",
            "XP", "Priority", "Pinned", "Block", "Tags", "Counters", "Active", "Notes"]
    view = df[cols + ["_row"]].reset_index(drop=True)
    keep = pd.Series(True, index=view.index)
    if under:
        inside = {under} | _beneath(h, under)
        keep &= view["ID"].astype(str).str.strip().isin(inside)
    if not inactive:
        keep &= view["Active"].map(lambda v: logic.to_bool(v, True))
    hidden, view = view[~keep], view[keep].reset_index(drop=True)

    kind = view["Kind"].map(lambda v: logic.pick(logic.KINDS, v, "Good"))
    view["Kind"] = kind
    view["Target"] = [logic.to_int(v, 1 if k == "Good" else 0) for v, k in zip(view["Target"], kind)]
    view["XP"] = view["XP"].map(lambda v: logic.to_int(v, 5))
    view["Step"] = view["Step"].map(lambda v: logic.to_int(v, 0) or None)
    view["Active"] = view["Active"].map(lambda v: logic.to_bool(v, True))
    view["Pinned"] = view["Pinned"].map(lambda v: logic.to_bool(v, True))
    for col, options in (("Domain", logic.DOMAINS), ("Priority", logic.PRIORITIES), ("Measure", logic.MEASURES),
                         ("Unit", logic.UNITS), ("Period", logic.PERIODS)):
        view[col] = view[col].map(lambda v, o=options: logic.pick(o, v, "") or None)

    st.caption("**Group** = an umbrella: it can't be logged and adds up everything under it. **Parents** = the "
               "umbrellas an item sits under (comma-separated names; more than one is fine). **Step** = its rung "
               "in a progression, 1 = easiest. **Measure** = what you enter when logging. **Variants** = choices "
               "picked when logging (e.g. Still, Moving, Jump). **Target** counts in **Unit**; 0 = no goal. "
               "**Pinned** = shows on Today. Blank Domain or Priority comes from the umbrella. **Floor** = "
               "non-negotiable. Unideal items never cost XP. Leave ID blank on new rows.")
    key = f"ed_items_{under}_{inactive}"
    edited = st.data_editor(
        view, key=key, num_rows="dynamic", hide_index=True, width="stretch", height=460,
        column_order=cols[1:] + ["ID"],
        column_config={
            "ID": CC.TextColumn(disabled=True, width="small"),
            "Item": CC.TextColumn(required=True, width="medium"),
            "Kind": CC.SelectboxColumn(options=logic.KINDS, default="Good"),
            "Parents": CC.TextColumn(width="medium", help="Umbrella names, comma-separated",
                                     default=h.items[under].name if under else None),
            "Step": CC.NumberColumn(min_value=0, max_value=50, step=1, help="Rung in a progression; 1 = easiest"),
            "Measure": CC.SelectboxColumn(options=logic.MEASURES, default="Check",
                                          help="Check = one tap; Reps, Time or Both ask when you log"),
            "Variants": CC.TextColumn(help="Comma-separated, picked when logging"),
            "Domain": CC.SelectboxColumn(options=logic.DOMAINS, help="Blank = same as its umbrella"),
            "Period": CC.SelectboxColumn(options=logic.PERIODS, default="Daily"),
            "Target": CC.NumberColumn(min_value=0, max_value=100000, step=1, default=1,
                                      help="How much per day or week counts as done, in Unit. 0 = no goal"),
            "Unit": CC.SelectboxColumn(options=logic.UNITS, default="Logs", help="What Target counts"),
            "XP": CC.NumberColumn(min_value=0, max_value=1000, step=1, default=5, help="Per log"),
            "Priority": CC.SelectboxColumn(options=logic.PRIORITIES, help="Blank = same as its umbrella"),
            "Pinned": CC.CheckboxColumn(default=True, help="Show on Today"),
            "Block": CC.TextColumn(help="Group on the Today page, e.g. Morning or Post-Isha", default="Anytime"),
            "Tags": CC.TextColumn(help="Comma-separated, e.g. 5min, reset"),
            "Counters": CC.TextColumn(help="Unideal items only: tags to favour afterwards"),
            "Active": CC.CheckboxColumn(default=True),
        })
    if st.button("Save items", type="primary", key="save_ed_items", icon=":material/save:"):
        # Rows hidden by the filter go back where they were; new rows go at the end.
        full = pd.concat([hidden, edited], ignore_index=True).sort_values("_row", na_position="last")
        ctx.store.replace("Items", full)
        st.toast("Saved Items to the sheet", icon="💾")
        st.session_state.pop(key, None)
        st.rerun()


def _beneath(h: logic.Hierarchy, gid: str) -> set[str]:
    out, stack = set(), list(h.children.get(gid, []))
    while stack:
        c = stack.pop()
        if c not in out:
            out.add(c)
            stack.extend(h.children.get(c, []))
    return out


def _trackers(ctx: Ctx) -> None:
    st.markdown("Each tracker is a weekly grid like your printed sheets: one row per column. **Maps to** is one "
                "or more items or umbrellas (comma-separated); an umbrella counts everything under it. **Show** "
                "picks what a cell displays: Auto shows reps and/or time, else a tick or count.")
    df = ctx.store.read("Trackers")
    edited = st.data_editor(
        _editor_df(df, ["Tracker", "Column", "Maps to", "Show"]), key="ed_tr", num_rows="dynamic",
        hide_index=True, width="stretch",
        column_config={"Tracker": CC.TextColumn(required=True, width="small"),
                       "Column": CC.TextColumn(required=True, width="medium"),
                       "Maps to": CC.TextColumn(width="large"),
                       "Show": CC.SelectboxColumn(options=logic.SHOWS, default="Auto")})
    _save(ctx, "Trackers", edited, "ed_tr")


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
                "domains, priorities, item names or umbrella names, comma-separated; join with `+` to require "
                "both (e.g. `Spiritual+low-energy`). An umbrella suggests the least-done skill under it this week, "
                "at your current rung. Items already done are skipped. **Fallback** shows when nothing is left.")
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
