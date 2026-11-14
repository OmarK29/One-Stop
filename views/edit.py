"""Edit: skills (a form for one at a time, or the whole table), trackers, the guide's questions and actions,
and settings. Same data as the sheet."""
from __future__ import annotations

import re
from zoneinfo import available_timezones

import pandas as pd
import streamlit as st

import logic
import seed
from views import celebrate
from views.celebrate import SOUNDS
from views.common import Ctx
from views.me import HAIR, SKIN

CC = st.column_config


def page(ctx: Ctx) -> None:
    st.subheader("Manage")
    st.caption("Everything you log, track and time, and how. Changes save to your Google Sheet; you can also edit "
               "the sheet directly, then tap Refresh.")
    t_skill, t_items, t_trackers, t_ladders, t_boards, t_io, t_tree, t_settings = st.tabs(
        ["Skills", "All items (table)", "Trackers", "Ladders", "Timer boards", "Import / export", "Guide me tree",
         "Settings"])
    with t_ladders:
        _ladders(ctx)
    with t_boards:
        _boards(ctx)
    with t_io:
        from views import transfer
        transfer.section(ctx)
    with t_skill:
        _skill_editor(ctx)
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

    cols = ["ID", "Item", "Kind", "Parents", "Step", "Inputs", "Variants", "Rest", "Domain", "Period", "Target",
            "Unit", "XP", "Priority", "Pinned", "Block", "Tags", "Counters", "Active", "Notes", "Measure"]
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
    derived = {it.id: logic.inputs_text(it.inputs, it.sets) for it in items}  # older rows only have Measure
    view["Inputs"] = [v if str(v).strip() else derived.get(str(i).strip(), "") for v, i in zip(view["Inputs"], view["ID"])]
    view["Rest"] = view["Rest"].map(lambda v: logic.to_int(v, 0) or None)
    for col, options in (("Domain", logic.DOMAINS), ("Priority", logic.PRIORITIES),
                         ("Unit", logic.UNITS), ("Period", logic.PERIODS)):
        view[col] = view[col].map(lambda v, o=options: logic.pick(o, v, "") or None)

    st.caption("**Group** = an umbrella: it can't be logged and adds up everything under it. **Parents** = the "
               "umbrellas an item sits under (comma-separated names; more than one is fine). **Step** = its rung "
               "in a progression, 1 = easiest. **Inputs** = what you enter when logging: any of Reps, Time, Weight, "
               "Distance, Effort, plus Sets to log set by set (blank = yes/no). **Rest** = seconds between sets in a "
               "workout. **Variants** = choices "
               "picked when logging (e.g. Still, Moving, Jump). **Target** counts in **Unit**; 0 = no goal. "
               "**Pinned** = shows on Today. Blank Domain or Priority comes from the umbrella. **Floor** = "
               "non-negotiable. Unideal items never cost XP. Leave ID blank on new rows.")
    key = f"ed_items_{under}_{inactive}"
    edited = st.data_editor(
        view, key=key, num_rows="dynamic", hide_index=True, width="stretch", height=460,
        column_order=cols[1:-1] + ["ID"],
        column_config={
            "ID": CC.TextColumn(disabled=True, width="small"),
            "Item": CC.TextColumn(required=True, width="medium"),
            "Kind": CC.SelectboxColumn(options=logic.KINDS, default="Good"),
            "Parents": CC.TextColumn(width="medium", help="Umbrella names, comma-separated",
                                     default=h.items[under].name if under else None),
            "Step": CC.NumberColumn(min_value=0, max_value=50, step=1, help="Rung in a progression; 1 = easiest"),
            "Inputs": CC.TextColumn(help="e.g. Sets, Reps, Weight · Time, Distance · blank = yes/no"),
            "Rest": CC.NumberColumn(min_value=0, max_value=1800, step=15, help="Seconds; blank = Settings default"),
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
        # Measure follows Inputs, for older code and sheets that still read it
        full["Measure"] = [logic.measure_of([i for i in logic.INPUTS if i.lower() in
                                             {t.lower() for t in logic.split_list(v)}]) if str(v).strip() else m
                           for v, m in zip(full["Inputs"].fillna(""), full["Measure"].fillna(""))]
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
    """Trackers without a table: pick one, then add, reorder, rename or remove its columns."""
    ss = st.session_state
    st.caption("Each tracker is a weekly grid like your printed sheets. A column counts one or more things; "
               "an umbrella counts everything under it.")
    df = ctx.store.read("Trackers")
    rows = [r for r in df.to_dict("records") if str(r.get("Tracker", "")).strip() and str(r.get("Column", "")).strip()]
    names = list(dict.fromkeys(str(r["Tracker"]).strip() for r in rows))
    if ss.get("ed_tr_pending") in names:  # just created or renamed: select it before the selectbox exists
        ss.ed_tr_pick = ss.pop("ed_tr_pending")
    if ss.get("ed_tr_pick") not in names:
        ss.pop("ed_tr_pick", None)
    head = st.container(horizontal=True, vertical_alignment="bottom")
    pick = head.selectbox("Tracker", names, key="ed_tr_pick", placeholder="No trackers yet")
    with head.popover("New tracker", icon=":material/add:"):
        new = st.text_input("Name", key="ed_tr_new", placeholder="e.g. Evening")
        if st.button("Create", key="ed_tr_create", disabled=not new.strip()) and new.strip() not in names:
            ss.ed_tr_pending = new.strip()
            ss.ed_tr_fresh = new.strip()  # an empty tracker exists only once it has a column
            st.rerun()
    pick = ss.get("ed_tr_fresh") if ss.get("ed_tr_fresh") and ss.get("ed_tr_fresh") not in names else pick
    if pick:
        cols = [r for r in rows if str(r["Tracker"]).strip() == pick]
        if not cols:
            st.info(f"{pick} is new. Add its first column below.")
        for i, r in enumerate(cols):
            with st.container(border=True):
                row = st.container(horizontal=True, wrap=False, vertical_alignment="center")
                with row.container(gap=None):
                    st.markdown(f"**{r['Column']}**")
                    st.caption(f"Counts: {r.get('Maps to') or '—'} · shows {r.get('Show') or 'Auto'}")
                if row.button("", icon=":material/arrow_upward:", key=f"ed_tr_up_{i}", disabled=i == 0, help="Up"):
                    _tracker_write(ctx, rows, pick, _swap(cols, i, i - 1))
                if row.button("", icon=":material/arrow_downward:", key=f"ed_tr_dn_{i}", disabled=i == len(cols) - 1,
                              help="Down"):
                    _tracker_write(ctx, rows, pick, _swap(cols, i, i + 1))
                if row.button("", icon=":material/delete:", key=f"ed_tr_rm_{i}", help="Remove column"):
                    _tracker_write(ctx, rows, pick, cols[:i] + cols[i + 1:])
        _tracker_column_form(ctx, rows, pick, cols)
        if names and pick in names:
            with st.expander("Rename or delete this tracker"):
                new_name = st.text_input("Name", value=pick, key=f"ed_tr_rn_{pick}")
                c = st.container(horizontal=True)
                if c.button("Rename", key="ed_tr_rename", disabled=not new_name.strip() or new_name.strip() in names):
                    for r in rows:
                        if str(r["Tracker"]).strip() == pick:
                            r["Tracker"] = new_name.strip()
                    ss.ed_tr_pending = new_name.strip()
                    _tracker_write(ctx, rows, None, None)
                if c.button("Delete tracker", key="ed_tr_delete", type="tertiary", icon=":material/delete:"):
                    _tracker_write(ctx, rows, pick, [])
    with st.expander("Edit all trackers as a table"):
        edited = st.data_editor(
            _editor_df(df, ["Tracker", "Column", "Maps to", "Show"]), key="ed_tr", num_rows="dynamic",
            hide_index=True, width="stretch",
            column_config={"Tracker": CC.TextColumn(required=True, width="small"),
                           "Column": CC.TextColumn(required=True, width="medium"),
                           "Maps to": CC.TextColumn(width="large"),
                           "Show": CC.SelectboxColumn(options=logic.SHOWS, default="Auto")})
        _save(ctx, "Trackers", edited, "ed_tr")


def _tracker_column_form(ctx: Ctx, rows: list[dict], tracker: str, cols: list[dict]) -> None:
    items = ctx.items()
    h = logic.build_hierarchy(items)
    choices = [it.id for it in sorted(items, key=lambda it: it.row) if it.active and (it.good or it.group)]
    with st.expander("Add a column", icon=":material/add:", expanded=not cols):
        with st.form(f"ed_tr_add_{tracker}", border=False):
            what = st.multiselect("What it counts", choices, format_func=lambda i: " · ".join(
                b for b in (h.items[i].name + (" ▸" if h.items[i].group else ""), h.path(i)) if b),
                help="One or more skills, habits or umbrellas")
            name = st.text_input("Column name (optional)", placeholder="Defaults to the first thing's name")
            show = st.segmented_control("Each cell shows", logic.SHOWS, default="Auto", required=True,
                                        help="Auto: reps and/or time, else a tick or count")
            if st.form_submit_button("Add column", type="primary"):
                if not what:
                    st.error("Pick at least one thing to count.")
                    return
                col = {"Tracker": tracker, "Column": (name.strip() or h.items[what[0]].name).replace(",", " /"),
                       "Maps to": ", ".join(h.items[i].name for i in what), "Show": show}
                st.session_state.ed_tr_fresh = None
                _tracker_write(ctx, rows, tracker, cols + [col])


def _swap(cols: list[dict], a: int, b: int) -> list[dict]:
    out = list(cols)
    out[a], out[b] = out[b], out[a]
    return out


def _tracker_write(ctx: Ctx, rows: list[dict], tracker: str | None, new_cols: list[dict] | None) -> None:
    """Replace one tracker's columns (keeping its place among the others), or just write `rows` as they are."""
    if tracker is not None:
        at = next((i for i, r in enumerate(rows) if str(r["Tracker"]).strip() == tracker), len(rows))
        others = [r for r in rows if str(r["Tracker"]).strip() != tracker]
        rows = others[:at] + list(new_cols or []) + others[at:]
    ctx.store.replace("Trackers", pd.DataFrame([{k: r.get(k, "") for k in ("Tracker", "Column", "Maps to", "Show")}
                                                for r in rows]))
    st.toast("Saved trackers", icon="💾")
    st.rerun()


def _ladders(ctx: Ctx) -> None:
    st.markdown("An **ease ladder** is a goal, then easier and easier ways to start it. Rows with the same "
                "**Ladder** name are one ladder; **Step** 1 is the real goal and higher steps are easier. "
                "**Minutes** is how long you get to start a step before it drops to the next one (blank = the "
                "default in Settings). **Logs as** is an optional skill: starting that step times or logs it.")
    try:
        df = ctx.store.read("Ladders")
    except Exception:
        st.info("The Ladders tab appears the next time the app restarts.")
        return
    view = _editor_df(df, ["Ladder", "Step", "Do", "Minutes", "Logs as"])
    for col in ("Step", "Minutes"):
        view[col] = pd.to_numeric(view[col], errors="coerce")
    edited = st.data_editor(
        view, key="ed_ld", num_rows="dynamic",
        hide_index=True, width="stretch",
        column_config={"Ladder": CC.TextColumn(required=True, width="small"),
                       "Step": CC.NumberColumn(min_value=1, max_value=50, step=1, width="small"),
                       "Do": CC.TextColumn(required=True, width="large"),
                       "Minutes": CC.NumberColumn(min_value=1, max_value=240, step=1, width="small"),
                       "Logs as": CC.TextColumn(width="medium", help="An item or umbrella name (optional)")})
    h = logic.build_hierarchy(ctx.items())
    issues = [f"Ladder '{n}', step '{r.do}': there's no item called '{r.logs_as}'."
              for n, rungs in ctx.ladders().items() for r in rungs if r.logs_as and h.find(r.logs_as) is None]
    if issues:
        st.warning("\n".join(f"- {i}" for i in issues))
    _save(ctx, "Ladders", edited, "ed_ld")


def _boards(ctx: Ctx) -> None:
    st.markdown("A **board** is a set of timers you start together from the Timers page. Rows with the same "
                "**Board** are one board. **Mode** is Stopwatch, Countdown, Interval or Counter; **Length** is "
                "seconds for a countdown. **Item** is an optional skill the timer logs to. **Options**: `repeat`, "
                "`delay=10`, `work=40, rest=20, rounds=8` (intervals), `color=blue` (blue, green, orange, red, "
                "violet, gray).")
    try:
        df = ctx.store.read("Boards")
    except Exception:
        st.info("The Boards tab appears the next time the app restarts.")
        return
    view = _editor_df(df, ["Board", "Label", "Mode", "Length", "Item", "Options"])
    view["Length"] = pd.to_numeric(view["Length"], errors="coerce")
    edited = st.data_editor(
        view, key="ed_bd", num_rows="dynamic", hide_index=True, width="stretch",
        column_config={"Board": CC.TextColumn(required=True, width="small"),
                       "Label": CC.TextColumn(width="medium"),
                       "Mode": CC.SelectboxColumn(options=logic.TIMER_MODES, default="Countdown"),
                       "Length": CC.NumberColumn(min_value=0, max_value=86400, step=5, help="Seconds"),
                       "Item": CC.TextColumn(width="medium"),
                       "Options": CC.TextColumn(width="medium")})
    _save(ctx, "Boards", edited, "ed_bd")


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
    pages = ["Guide me", "Today", "Track", "Workout", "Timers", "Me", "Progress"]
    with st.form("settings"):
        st.markdown("##### Day and XP")
        tz = st.selectbox("Time zone", zones, index=zones.index(clock.timezone) if clock.timezone in zones else 0)
        start = st.number_input("New day starts at (hour, 0–12)", 0, 12, clock.day_starts_at_hour,
                                help="Late-night logs before this hour count for the previous day.")
        week = st.selectbox("Week starts on", logic.WEEKDAYS, index=logic.WEEKDAYS.index(clock.week_starts_on))
        per_level = st.number_input("XP per level", 50, 5000, ctx.per_level, step=50)

        st.markdown("##### Display")
        st.caption("Dark mode follows your phone or Mac. To choose yourself: ⋮ menu (top right) → Settings → "
                   "Choose app theme.")
        c1, c2, c3 = st.columns(3)
        start_page = c1.selectbox("Opens on", pages, index=_index(pages, ctx.display("start_page", "Guide me")))
        layout = c2.selectbox("Layout", ["Comfortable", "Compact"],
                              index=_index(["Comfortable", "Compact"], ctx.display("layout", "Comfortable")))
        text = c3.selectbox("Text size", ["Normal", "Large"],
                            index=_index(["Normal", "Large"], ctx.display("text", "Normal")))
        st.caption("To hide sections of a page, use its **Show** menu (top of Today, Me and Progress).")

        ladder_min = st.number_input("Ease ladders: minutes to start each step", 1, 120,
                                     logic.to_int(s.get("ladder_minutes"), 5),
                                     help="Used when a step's Minutes is blank. Change one ladder on Manage → Ladders.")

        st.markdown("##### Sounds")
        c1, c2, c3 = st.columns(3)
        snd_log = c1.selectbox("Each log", SOUNDS, index=_index(SOUNDS, s.get("sound_log") or "Pop"))
        snd_big = c2.selectbox("Big moments", SOUNDS, index=_index(SOUNDS, s.get("sound_big") or "Fanfare"),
                               help="Finishing a goal, a new best, a workout, or starting a ladder step")
        volume = c3.slider("Volume", 0, 100, logic.to_int(s.get("sound_volume"), 60), step=10)

        st.markdown("##### Workouts and units")
        c1, c2, c3 = st.columns(3)
        rest_default = c1.number_input("Rest between sets (s)", 0, 1800, logic.to_int(s.get("rest_seconds"), 90),
                                       step=15)
        w_units, d_units = ["lb", "kg"], ["mi", "km"]
        w_unit = c2.selectbox("Weight in", w_units, index=_index(w_units, s.get("weight_unit") or "lb"))
        d_unit = c3.selectbox("Distance in", d_units, index=_index(d_units, s.get("distance_unit") or "mi"))

        st.markdown("##### Sleep and screen time")
        c1, c2 = st.columns(2)
        track_sleep = c1.toggle("Track sleep", value=logic.to_bool(s.get("track_sleep"), True))
        sleep = c1.number_input("Sleep goal (hours)", 4.0, 12.0, logic.to_float(s.get("sleep_goal_hours"), 7.5),
                                step=0.25)
        track_screen = c2.toggle("Track screen time", value=logic.to_bool(s.get("track_screen_time"), True))
        screen = c2.number_input("Daily screen time limit (hours)", 0.0, 16.0,
                                 logic.to_float(s.get("screen_time_limit_hours"), 2.0), step=0.25,
                                 help="At or under the limit earns XP. Over it is just noticed, never a penalty.")

        st.markdown("##### Profile and character")
        st.caption("Age and sex pick the right comparison group on Me. Both are optional and stay in your sheet.")
        c1, c2 = st.columns(2)
        age = c1.number_input("Age", 0, 100, logic.to_int(s.get("profile_age"), 0), help="0 = not set")
        sexes = ["Not set", "Male", "Female"]
        sex = c2.selectbox("Sex (for fitness norms)", sexes,
                           index=_index(sexes, logic.pick(["Male", "Female"], s.get("profile_sex"), "Not set")))
        c1, c2, c3 = st.columns(3)
        skin = c1.selectbox("Skin tone", list(SKIN), index=_index(list(SKIN), s.get("avatar_skin") or "Medium light"))
        hair = c2.selectbox("Hair", list(HAIR), index=_index(list(HAIR), s.get("avatar_hair") or "Black"))
        pet = c3.text_input("Pet's name", value=str(s.get("pet_name") or "Pip"), max_chars=20)

        if st.form_submit_button("Save settings", type="primary"):
            new = dict(s)
            new.update({"timezone": tz, "day_starts_at_hour": int(start), "week_starts_on": week,
                        "xp_per_level": int(per_level), "ladder_minutes": int(ladder_min),
                        "display_start_page": start_page, "display_layout": layout, "display_text": text,
                        "track_sleep": track_sleep, "sleep_goal_hours": sleep,
                        "track_screen_time": track_screen, "screen_time_limit_hours": screen,
                        "profile_age": int(age), "profile_sex": "" if sex == "Not set" else sex,
                        "rest_seconds": int(rest_default), "weight_unit": w_unit, "distance_unit": d_unit,
                        "sound_log": snd_log, "sound_big": snd_big, "sound_volume": int(volume),
                        "avatar_skin": skin, "avatar_hair": hair, "pet_name": pet.strip() or "Pip"})
            ctx.store.replace("Settings", pd.DataFrame({"Key": list(new), "Value": list(new.values())}))
            st.toast("Settings saved", icon="💾")
            st.rerun()
    row = st.container(horizontal=True)
    if row.button("Hear a log", icon=":material/volume_up:", type="tertiary", key="snd_test_log",
                  help="Plays the saved sound; save settings first after changing it"):
        celebrate.queue("test_log")
        st.rerun()
    if row.button("Hear a big moment", icon=":material/celebration:", type="tertiary", key="snd_test_big"):
        celebrate.queue("test_big")
        st.rerun()


def _index(options: list[str], value) -> int:
    return options.index(value) if value in options else 0


# ---------- one skill at a time ----------

NEW_SKILL, NEW_GROUP, NEW_GOAL, NEW_IDENTITY = "__new_skill__", "__new_group__", "__new_goal__", "__new_identity__"
NEW_KIND = {NEW_SKILL: "Good", NEW_GROUP: "Group", NEW_GOAL: "Goal", NEW_IDENTITY: "Identity"}
KIND_LABEL = {"Group": "Umbrella", "Goal": "Goal", "Identity": "Identity"}


def _skill_editor(ctx: Ctx) -> None:
    """Add or change one skill or umbrella, its variants and its progression, without the big table."""
    df = ctx.store.read("Items")
    items = logic.parse_items(df)
    h = logic.build_hierarchy(items)
    ordered = [it for it in sorted(items, key=lambda it: it.row) if it.kind != "Unideal"]
    options = list(NEW_KIND) + [it.id for it in ordered]

    def label(i: str) -> str:
        if i in NEW_KIND:
            return "➕ New " + {"Good": "skill"}.get(NEW_KIND[i], KIND_LABEL.get(NEW_KIND[i], "").lower())
        it = h.items[i]
        mark = {"Identity": "🌱 ", "Goal": "🎯 "}.get(it.kind, "")
        return " · ".join(b for b in (mark + it.name + (" ▸" if it.group else ""), h.path(i)) if b)

    if "sk_pending" in st.session_state:  # set by a save, before the selectbox exists this run
        st.session_state.sk_sel = st.session_state.pop("sk_pending")
    st.caption("**Identity** is who you're becoming; **goals** sit under it, and skills and umbrellas sit under "
               "goals. **Variants** are the same level done different ways (Still, Moving, Jump). A **progression** "
               "is levels of difficulty under one umbrella (Squat → Single-leg squat → Stair squat), easiest first.")
    sel = st.selectbox("Skill, umbrella, goal or identity", options, index=None, key="sk_sel", format_func=label,
                       placeholder="Pick one to change, or add a new one")
    if sel is None:
        return
    it = h.items.get(sel)
    kind = it.kind if it else NEW_KIND[sel]
    _skill_form(ctx, df, h, it, kind)
    if it is None:
        return
    if it.kind in ("Goal", "Identity"):
        _beneath_picker(ctx, df, h, it)
    elif it.group:
        _progression(ctx, df, h, it)
    elif h.ladder_of(it.id):
        gid = h.ladder_of(it.id)
        rungs = h.ladder(gid)
        st.caption(f"Rung {rungs.index(it) + 1} of {len(rungs)} in **{h.items[gid].name}**.")
        st.button(f"Edit the {h.items[gid].name} progression", key="sk_open_ladder", on_click=_select_item,
                  args=(gid,))
    else:
        _make_progression(ctx, df, h, it)


def _select_item(iid: str) -> None:
    st.session_state.sk_sel = iid


def _skill_form(ctx: Ctx, df: pd.DataFrame, h: logic.Hierarchy, it: logic.Item | None, kind: str) -> None:
    group = kind in logic.GROUP_KINDS
    raw = _raw_row(df, it.id) if it else {}
    below = {it.id} | _beneath(h, it.id) if it else set()
    # Identities sit at the top; goals sit under identities; everything else can sit under any umbrella or goal.
    allowed = {"Identity": (), "Goal": ("Identity",)}.get(kind, ("Group", "Goal"))
    groups = [g for g in sorted(h.items.values(), key=lambda g: g.row) if g.kind in allowed and g.id not in below]
    current = [h.items[p].name for p in h.parents.get(it.id, [])] if it else []

    with st.form(f"sk_form_{it.id if it else kind}"):
        name = st.text_input("Name", value=it.name if it else "", max_chars=80,
                             placeholder={"Identity": "e.g. A martial artist", "Goal": "e.g. Run a half marathon"}
                             .get(kind, ""))
        if group:
            kind = st.segmented_control("Type", list(KIND_LABEL), default=kind, format_func=KIND_LABEL.get,
                                        required=True)
        parents = st.multiselect({"Goal": "Under these identities", "Identity": "Under (identities are the top)"}
                                 .get(kind, "Under these umbrellas or goals"),
                                 [g.name for g in groups] + [c for c in current if c not in {g.name for g in groups}],
                                 default=current, disabled=kind == "Identity" and not current,
                                 help="More than one is fine.")
        if not group:
            inputs = st.pills("When you log it, enter", logic.INPUTS, selection_mode="multi",
                              default=it.inputs if it else ["Reps"],
                              help="Pick none for a yes/no item. Time can be typed or timed with the stopwatch.")
            c1, c2 = st.columns(2)
            sets = c1.toggle("Log set by set", value=it.sets if it else True,
                             help="Each set is its own row, like a gym tracker")
            rest = c2.number_input("Rest between sets (s)", 0, 1800, it.rest if it and it.rest else 0, step=15,
                                   help="For workouts. 0 = the default in Settings")
            variants = st.multiselect("Variants (same level, different ways)", it.variants if it else [],
                                      default=it.variants if it else [], accept_new_options=True,
                                      placeholder="Type one and press Enter",
                                      help="Picked when you log, e.g. Still, Moving, Jump or Left, Right.")
        c1, c2, c3 = st.columns(3)
        period = c1.selectbox("Goal per", logic.PERIODS, index=logic.PERIODS.index(it.period if it else "Weekly"))
        target = c2.number_input("Goal (0 = none)", 0, 100000, it.target if it else 0)
        unit = c3.selectbox("Counted in", logic.UNITS, index=logic.UNITS.index(it.unit if it else "Logs"))
        c1, c2, c3 = st.columns(3)
        own_prio = logic.pick(logic.PRIORITIES, raw.get("Priority"), "")
        own_dom = logic.pick(logic.DOMAINS, raw.get("Domain"), "")
        prio = c1.selectbox("Priority", ["Same as umbrella"] + logic.PRIORITIES,
                            index=(logic.PRIORITIES.index(own_prio) + 1) if own_prio else 0)
        domain = c2.selectbox("Domain", ["Same as umbrella"] + logic.DOMAINS,
                              index=(logic.DOMAINS.index(own_dom) + 1) if own_dom else 0)
        xp = c3.number_input("XP per log", 0, 1000, it.xp if it and not group else 5, disabled=group)
        c1, c2 = st.columns(2)
        pinned = c1.toggle("Show on Today", value=it.pinned if it else False)
        active = c2.toggle("Active", value=it.active if it else True)
        notes = st.text_input("Notes", value=it.notes if it else "")
        saved = st.form_submit_button("Save" if it else "Add", type="primary", icon=":material/save:")

    if not saved:
        if it and st.button("Archive" if it.active else "Bring back", type="tertiary", key="sk_archive",
                            icon=":material/archive:" if it.active else ":material/unarchive:",
                            help="Archived items stay in the sheet and your history, just out of the way."):
            _write_items(ctx, _set(df, it.id, {"Active": not it.active}))
        return
    name = name.strip()
    problem = _name_problem(h, name, it)
    if problem:
        st.error(problem)
        return
    values = {"Item": name, "Kind": kind, "Parents": ", ".join(parents),
              "Period": period, "Target": int(target), "Unit": unit,
              "Priority": "" if prio == "Same as umbrella" else prio,
              "Domain": "" if domain == "Same as umbrella" else domain,
              "XP": 0 if group else int(xp), "Pinned": pinned, "Active": active, "Notes": notes}
    if not group:
        values |= {"Inputs": logic.inputs_text(inputs or [], sets) or "", "Measure": logic.measure_of(inputs or []),
                   "Rest": int(rest) or "", "Variants": ", ".join(v.strip() for v in variants if v.strip())}
    if it is None:
        new_id = _next_id(df)
        df = pd.concat([df, pd.DataFrame([_blank_row(new_id) | values])], ignore_index=True)
        _write_items(ctx, df, select=new_id)
    else:
        df = _set(df, it.id, values)
        if name != it.name:
            df = _rename(ctx, df, it.name, name)
        _write_items(ctx, df)


def _beneath_picker(ctx: Ctx, df: pd.DataFrame, h: logic.Hierarchy, g: logic.Item) -> None:
    """What sits under a goal (skills and umbrellas) or an identity (goals). Changes their Parents."""
    want = ("Goal",) if g.kind == "Identity" else ("Good", "Group")
    candidates = [it for it in sorted(h.items.values(), key=lambda it: it.row)
                  if it.kind in want and it.active and it.id != g.id]
    current = [c for c in h.children.get(g.id, []) if h.items[c].kind in want]
    st.markdown(f"#### {'Goals' if g.kind == 'Identity' else 'Skills and umbrellas'} under {g.name}")
    picked = st.multiselect("Under it", [it.id for it in candidates], default=current, key=f"sk_under_{g.id}",
                            format_func=lambda i: " · ".join(b for b in (h.items[i].name, h.path(i)) if b),
                            label_visibility="collapsed",
                            help="An umbrella brings everything beneath it, so its logs count toward this too.")
    if not st.button("Save", type="primary", key=f"sk_save_under_{g.id}", icon=":material/save:"):
        return
    for iid in set(picked) ^ set(current):
        it = h.items[iid]
        keep = [p for p in it.parents if h.lookup.get(p.lower()) != g.id]
        df = _set(df, iid, {"Parents": ", ".join(keep + ([g.name] if iid in picked else []))})
    _write_items(ctx, df)


def _progression(ctx: Ctx, df: pd.DataFrame, h: logic.Hierarchy, g: logic.Item) -> None:
    """The rungs under an umbrella, easiest first. Add a row for a new, harder rung."""
    rungs = h.ladder(g.id)
    st.markdown(f"#### Progression in {g.name}")
    st.caption("Easiest at the top. Add a row for a new rung; drag isn't supported, so put a rung where it belongs "
               "with **Order** (1 = easiest). Removing a row keeps the skill under this umbrella, just not as a rung.")
    table = pd.DataFrame({"Order": [r.step for r in rungs], "Rung": [r.name for r in rungs],
                          "Variants": [", ".join(r.variants) for r in rungs]})
    edited = st.data_editor(table, key=f"sk_ladder_{g.id}", num_rows="dynamic", hide_index=True, width="stretch",
                            column_config={"Order": CC.NumberColumn(min_value=1, max_value=50, step=1, width="small"),
                                           "Rung": CC.TextColumn(required=True, width="medium"),
                                           "Variants": CC.TextColumn(help="Same level, comma-separated")})
    others = [c for c in h.children.get(g.id, []) if not h.items[c].group and not h.items[c].step]
    if others:
        st.caption("Also under this umbrella, not as rungs: " + ", ".join(h.items[c].name for c in others)
                   + ". Type one of these names as a rung to add it.")
    if not st.button("Save progression", type="primary", key="sk_save_ladder", icon=":material/save:"):
        return
    rows = edited.dropna(subset=["Rung"])
    rows = rows[rows["Rung"].astype(str).str.strip() != ""]
    rows = rows.assign(_o=[logic.to_int(o, 999) for o in rows["Order"]], _i=range(len(rows))).sort_values(["_o", "_i"])
    measure = rungs[0].measure if rungs else "Reps"
    inputs = logic.inputs_text(rungs[0].inputs, rungs[0].sets) if rungs else "Sets, Reps"
    kept = set()
    for step, r in enumerate(rows.to_dict("records"), start=1):
        name = str(r["Rung"]).strip()
        variants = ", ".join(logic.split_list(r.get("Variants")))
        found = h.find(name)
        if found and found.group:
            st.error(f"'{name}' is an umbrella, so it can't be a rung.")
            return
        if "," in name or ";" in name:
            st.error(f"'{name}' has a comma in it. Use / or & instead.")
            return
        if found:
            parents = found.parents if any(h.lookup.get(p.lower()) == g.id for p in found.parents) \
                else found.parents + [g.name]
            df = _set(df, found.id, {"Step": step, "Variants": variants, "Parents": ", ".join(parents)})
            kept.add(found.id)
        else:
            new_id = _next_id(df)
            df = pd.concat([df, pd.DataFrame([_blank_row(new_id) | {
                "Item": name, "Kind": "Good", "Parents": g.name, "Step": step, "Measure": measure, "Inputs": inputs,
                "Variants": variants, "Period": "Weekly", "Target": 0, "XP": 5, "Pinned": False}])],
                ignore_index=True)
    for r in rungs:
        if r.id not in kept:
            df = _set(df, r.id, {"Step": ""})
    _write_items(ctx, df)


def _make_progression(ctx: Ctx, df: pd.DataFrame, h: logic.Hierarchy, it: logic.Item) -> None:
    with st.expander("Make this the first rung of a progression"):
        st.caption(f"Creates an umbrella where {it.name} sits now, puts {it.name} under it as rung 1, then opens "
                   f"it so you can add harder rungs.")
        name = st.text_input("Progression name", value=f"{it.name} progression", key=f"sk_newlad_{it.id}")
        if st.button("Create progression", key="sk_make_ladder", icon=":material/stairs:"):
            name = name.strip()
            problem = _name_problem(h, name, None)
            if problem:
                st.error(problem)
                return
            gid = _next_id(df)
            df = pd.concat([df, pd.DataFrame([_blank_row(gid) | {
                "Item": name, "Kind": "Group", "Parents": ", ".join(h.items[p].name for p in h.parents.get(it.id, [])),
                "Period": it.period, "Target": 0, "XP": 0, "Pinned": False}])], ignore_index=True)
            df = _set(df, it.id, {"Parents": name, "Step": 1})
            _write_items(ctx, df, select=gid)


def _name_problem(h: logic.Hierarchy, name: str, it: logic.Item | None) -> str | None:
    if not name:
        return "Give it a name."
    if "," in name or ";" in name:
        return "Names can't contain commas or semicolons (Parents and trackers use them to separate names). Try / or &."
    other = h.find(name)
    if other and (it is None or other.id != it.id):
        return f"There's already an item called '{other.name}'."
    return None


def _raw_row(df: pd.DataFrame, iid: str) -> dict:
    match = df[df["ID"].astype(str).str.strip() == iid]
    return match.iloc[0].to_dict() if not match.empty else {}


def _set(df: pd.DataFrame, iid: str, values: dict) -> pd.DataFrame:
    df = df.copy()
    mask = df["ID"].astype(str).str.strip() == iid
    for k, v in values.items():
        if k not in df.columns:
            df[k] = ""
        df[k] = df[k].astype(object)
        df.loc[mask, k] = v
    return df


def _next_id(df: pd.DataFrame) -> str:
    nums = [int(m.group(1)) for i in df["ID"].astype(str) if (m := re.fullmatch(r"\s*I(\d+)\s*", i))]
    return f"I{max(nums, default=0) + 1:03d}"


def _blank_row(iid: str) -> dict:
    return {h: "" for h in seed.ITEMS_HEADER} | {"ID": iid, "Active": True, "Block": "Anytime"}


def _swap_token(text: str, old: str, new: str, seps: str = ",") -> str:
    """Replace a whole name inside a comma- (or comma- and +-) separated list, keeping everything else."""
    pattern = rf"(^|[{re.escape(seps)}]\s*)({re.escape(old)})(\s*(?=[{re.escape(seps)}]|$))"
    return re.sub(pattern, lambda m: m.group(1) + new + m.group(3), str(text or ""), flags=re.IGNORECASE)


def _rename(ctx: Ctx, df: pd.DataFrame, old: str, new: str) -> pd.DataFrame:
    """Follow a rename everywhere a name is used: Parents, tracker columns and Guide me actions."""
    df = df.copy()
    df["Parents"] = df["Parents"].map(lambda v: _swap_token(v, old, new))
    tr = ctx.store.read("Trackers")
    tr2 = tr.assign(**{"Maps to": tr["Maps to"].map(lambda v: _swap_token(v, old, new))})
    if not tr2["Maps to"].equals(tr["Maps to"]):
        ctx.store.replace("Trackers", tr2)
    ac = ctx.store.read("Actions")
    ac2 = ac.assign(**{"Picks from": ac["Picks from"].map(lambda v: _swap_token(v, old, new, ",+"))})
    if not ac2["Picks from"].equals(ac["Picks from"]):
        ctx.store.replace("Actions", ac2)
    return df


def _write_items(ctx: Ctx, df: pd.DataFrame, select: str | None = None) -> None:
    ctx.store.replace("Items", df.sort_values("_row", na_position="last") if "_row" in df.columns else df)
    st.toast("Saved to the sheet", icon="💾")
    if select:
        st.session_state.sk_pending = select
    st.rerun()
