"""Add: a friendly way to start tracking something, from Today or Track. No tables: pick what kind of thing
it is, how often, when, and where it shows. Check-offs can be yes/no or a number of times; skills take reps,
time and the rest; 'just notice' things never cost XP."""
from __future__ import annotations

import streamlit as st

import logic
from views import celebrate
from views.common import Ctx

KINDS = {"Check off": "✅ Check off", "Skill": "💪 Skill or exercise", "Notice": "👀 Just notice"}
IDEAS = {
    "Check off": ["Drink water", "Floss", "Stretch", "Take vitamins", "Read", "Make bed", "Walk outside",
                  "Call family"],
    "Skill": ["Push-ups", "Plank", "Squats", "Run", "Jump rope", "Handstand", "Kicks", "Stretching flow"],
    "Notice": ["Snacked late", "Phone in bed", "Skipped water", "Stayed up late"],
}
IMPORTANCE = {"Nice to do": "Normal", "Important": "High", "Non-negotiable": "Floor"}
NEW_TRACKER = "＋ New tracker"


def open_add(ctx: Ctx, tracker: str | None = None, parent: str | None = None) -> None:
    """Open the Add dialog. `tracker` puts the new thing in that tracker; `parent` files it under an umbrella."""
    for k in [k for k in st.session_state if str(k).startswith("ad_")]:
        del st.session_state[k]
    st.dialog("Add something to track", width="medium")(_body)(ctx, tracker, parent)


def _idea(kind: str) -> None:
    ss = st.session_state
    pick = ss.get(f"ad_idea_{kind}")
    if pick:
        ss.ad_name = pick
    ss[f"ad_idea_{kind}"] = None


def _body(ctx: Ctx, tracker: str | None, parent: str | None) -> None:
    items = ctx.items()
    h = logic.build_hierarchy(items)
    trackers = ctx.trackers()
    kind = st.segmented_control("What is it?", list(KINDS), format_func=KINDS.get, default="Check off",
                                required=True, key="ad_kind")
    st.caption({"Check off": "Something you do, once or a few times a day or week. One tap each time.",
                "Skill": "Something you train: reps, time, weight, distance or effort, set by set if you like.",
                "Notice": "Something to be aware of. Logging it never costs XP; it helps Guide me steer you."}[kind])
    st.pills("Ideas", IDEAS[kind], key=f"ad_idea_{kind}", on_change=_idea, args=(kind,),
             label_visibility="collapsed")
    name = st.text_input("Name", key="ad_name", max_chars=60, placeholder="e.g. " + IDEAS[kind][0])

    groups = [g for g in sorted(items, key=lambda g: g.row) if g.kind == "Group" and g.active]
    goals = [g for g in sorted(items, key=lambda g: g.row) if g.kind == "Goal" and g.active]
    values: dict = {"Kind": "Good", "XP": 5, "Active": True, "Target": 0, "Period": "Daily"}
    parents: list[str] = []

    if kind == "Check off":
        c1, c2 = st.columns(2)
        times = c1.number_input("How many times", 1, 50, 1, key="ad_times")
        often = c2.segmented_control("Per", ["Day", "Week"], default="Day", required=True, key="ad_often")
        blocks = list(dict.fromkeys(it.block for it in sorted(items, key=lambda it: it.row)
                                    if it.good and it.pinned and it.period == "Daily" and it.block))
        when = st.pills("When", blocks + (["Anytime"] if "Anytime" not in blocks else []), default="Anytime",
                        key="ad_when", help="Groups it with other things at that time of day on Today")
        importance = st.segmented_control("How important", list(IMPORTANCE), default="Nice to do", required=True,
                                          key="ad_imp", help="Non-negotiable = part of your Floor for the day")
        values |= {"Target": int(times), "Period": "Daily" if often == "Day" else "Weekly", "Unit": "Logs",
                   "Block": (when or "Anytime") if often == "Day" else "This week", "Pinned": True,
                   "Priority": IMPORTANCE[importance], "Measure": "Check", "Inputs": ""}
    elif kind == "Skill":
        inputs = st.pills("When you log it, enter", logic.INPUTS, selection_mode="multi", default=["Reps"],
                          key="ad_inputs")
        c1, c2 = st.columns(2)
        sets = c1.toggle("Log set by set", value=True, key="ad_sets")
        today = c2.toggle("Show on Today", value=False, key="ad_pin")
        default_parent = h.items[parent].name if parent in h.items and h.items[parent].kind == "Group" else None
        under = st.selectbox("Under", [g.name for g in groups], index=[g.name for g in groups].index(default_parent)
                             if default_parent else None, placeholder="No umbrella", key="ad_under")
        variants = st.multiselect("Variants (same level, different ways)", [], accept_new_options=True,
                                  placeholder="Type one and press Enter", key="ad_vars")
        c1, c2 = st.columns(2)
        target = c1.number_input("Weekly goal (0 = none)", 0, 100000, 0, key="ad_target")
        unit = c2.selectbox("Counted in", logic.UNITS, key="ad_unit")
        parents = [under] if under else []
        values |= {"Period": "Weekly", "Target": int(target), "Unit": unit, "Pinned": today,
                   "Inputs": logic.inputs_text(inputs or [], sets), "Measure": logic.measure_of(inputs or []),
                   "Variants": ", ".join(v.strip().replace(",", " /") for v in variants if v.strip()),
                   "Block": "Anytime"}
    else:
        values |= {"Kind": "Unideal", "XP": 0, "Priority": "Low", "Block": "Noticed", "Pinned": True}

    if not parents:
        domain = st.pills("Area", logic.DOMAINS, default="Physical", key="ad_domain", required=True)
        values["Domain"] = domain
    if goals and kind != "Notice":
        picked = st.multiselect("Part of a goal (optional)", [g.name for g in goals], key="ad_goals")
        parents += picked
    names = list(trackers) + [NEW_TRACKER]
    put = st.selectbox("Add it to a tracker (optional)", names, key="ad_tracker", placeholder="No tracker",
                       index=names.index(tracker) if tracker in trackers else None)
    if put == NEW_TRACKER:
        put = st.text_input("New tracker name", key="ad_new_tracker", placeholder="e.g. Evening").strip() or None

    if st.button("Add", type="primary", icon=":material/add:", width="stretch", key="ad_go"):
        name = name.strip()
        problem = ("Give it a name." if not name else
                   "Names can't contain commas or semicolons. Try / or &." if "," in name or ";" in name else
                   f"There's already something called {name}." if h.find(name) else None)
        if problem:
            st.error(problem)
            return
        df = ctx.store.read("Items", fresh=True)
        nums = [logic.to_int(str(i).strip()[1:], 0) for i in df["ID"] if str(i).strip().startswith("I")]
        iid = f"I{max(nums, default=0) + 1:03d}"
        ctx.store.append_dicts("Items", [values | {"ID": iid, "Item": name, "Parents": ", ".join(parents)}])
        if put:
            ctx.store.append_dicts("Trackers", [{"Tracker": put, "Column": name, "Maps to": name, "Show": "Auto"}])
        celebrate.queue("log")
        st.toast(f"Added {name}" + (f" to {put}" if put else ""), icon="🌱")
        st.rerun()
