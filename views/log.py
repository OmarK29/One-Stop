"""Log: pick a skill, enter reps and/or time, log it. Its own page, and the dialog Today and Trackers open."""
from __future__ import annotations

import datetime as dt
import time

import streamlit as st

import logic
from views.common import Ctx, add_variant, log_item, start_timer

OTHER = "__other__"


def open_dialog(ctx: Ctx, title: str, scope: list[str] | None = None, day: dt.date | None = None) -> None:
    """Open the log screen in a dialog, starting fresh. Closing it refreshes the page behind."""
    for k in [k for k in st.session_state if str(k).startswith("ld_")]:
        del st.session_state[k]
    st.dialog(title, width="medium", on_dismiss="rerun")(_dialog_body)(ctx, scope, day)


def _dialog_body(ctx: Ctx, scope: list[str] | None, day: dt.date | None) -> None:
    panel(ctx, scope=scope, day=day, key="ld", in_dialog=True)


def panel(ctx: Ctx, scope: list[str] | None = None, day: dt.date | None = None, key: str = "lp",
          in_dialog: bool = False) -> None:
    """`scope` limits the picker to these items/umbrellas; `day` logs for an earlier day."""
    ss = st.session_state
    h = logic.build_hierarchy(ctx.items())
    frame = logic.log_frame(ctx.log(), ctx.clock)
    roots = [i for i in (scope or []) if i in h.items] or None
    pool = _pool(h, roots)
    if not pool:
        st.info("Nothing to log here yet. Add skills under this umbrella on the Manage page.")
        return

    sel = ss.get(f"{key}_sel")
    if sel not in pool and not (sel in h.items and h.items[sel].good):  # a skill just added may sit outside scope
        sel = None if ss.get(f"{key}_choosing") else _auto_pick(h, roots, pool, frame)
    if sel is None:
        _choose(ctx, h, roots, pool, frame, key, in_dialog)
    else:
        _form(ctx, h, h.items[sel], frame, day or ctx.clock.today(), key, in_dialog, can_change=len(pool) > 1)


def _pool(h: logic.Hierarchy, roots: list[str] | None) -> list[str]:
    ids = [i for r in roots for i in h.leaves(r)] if roots else list(h.items)
    out = []
    for i in ids:
        it = h.items[i]
        if it.active and it.good and i not in out:
            out.append(i)
    return out


def _auto_pick(h: logic.Hierarchy, roots: list[str] | None, pool: list[str], frame) -> str | None:
    """One item in scope: pick it. A progression: pick your current rung."""
    if len(pool) == 1:
        return pool[0]
    if roots and len(roots) == 1 and h.ladder(roots[0]):
        cur = logic.current_rung(h, roots[0], frame)
        return cur.id if cur and cur.id in pool else None
    return None


def _select(key: str, widget: str) -> None:
    """Pills/search callback: open the chosen item (or umbrella), then clear the widget."""
    ss = st.session_state
    v = ss.get(widget)
    ss[widget] = None
    if v == OTHER:
        ss[f"{key}_other"] = True
    elif v and v.startswith("g:"):
        ss.setdefault(f"{key}_browse", []).append(v[2:])
    elif v:
        ss[f"{key}_sel"], ss[f"{key}_choosing"] = v, False


def _rerun(in_dialog: bool) -> None:
    st.rerun(scope="fragment") if in_dialog else st.rerun()


def _choose(ctx: Ctx, h: logic.Hierarchy, roots: list[str] | None, pool: list[str], frame, key: str,
            in_dialog: bool) -> None:
    ss = st.session_state
    with st.popover("New skill", icon=":material/add:"):
        from views.timers import quick_skill_form  # timers imports this module's neighbours
        new_id = quick_skill_form(ctx, h, f"{key}_ns")
        if new_id:
            ss[f"{key}_sel"], ss[f"{key}_choosing"] = new_id, False
            _rerun(in_dialog)
    in_pool = set(pool)
    quick = [i for i in logic.recent_ids(frame, 30) if i in in_pool][:6]
    if roots is None:  # pinned skills (things with an umbrella or reps/time), not every pinned habit
        quick += [i for i in pool if i not in quick and h.items[i].pinned
                  and (h.parents.get(i) or h.items[i].inputs)][:10 - len(quick)]
    options = quick + ([OTHER] if roots is None and not ss.get(f"{key}_other") else [])
    if options:
        st.pills("Recent and pinned" if roots is None else "Recent", options, key=f"{key}_quick",
                 format_func=lambda i: "Other…" if i == OTHER else h.items[i].name,
                 on_change=_select, args=(key, f"{key}_quick"))
    if roots is None and not ss.get(f"{key}_other") and quick:
        return

    st.selectbox("Search", pool, index=None, key=f"{key}_search", placeholder="Type to search",
                 format_func=lambda i: " · ".join(b for b in (h.items[i].name, h.path(i)) if b),
                 on_change=_select, args=(key, f"{key}_search"))
    _browse(h, roots, frame, key, in_dialog)


def _browse(h: logic.Hierarchy, roots: list[str] | None, frame, key: str, in_dialog: bool) -> None:
    """Drill down umbrella → skill → rung. Progressions show your current rung; the rest are one tap away."""
    ss = st.session_state
    stack = ss.setdefault(f"{key}_browse", [])
    if stack:
        node = stack[-1]
        kids = h.children.get(node, [])
    elif roots and len(roots) == 1 and h.items[roots[0]].group:
        node, kids = roots[0], h.children.get(roots[0], [])
    else:
        node, kids = None, roots or [it.id for it in h.roots() if it.group]
    kids = [k for k in kids if h.items[k].active and (h.items[k].group or h.items[k].good)]

    cur = logic.current_rung(h, node, frame) if node and h.ladder(node) else None
    show_all = ss.get(f"{key}_all_{node}", False)
    if cur and not show_all:
        kids = [k for k in kids if not h.items[k].step or k == cur.id]

    if stack:
        c1, c2 = st.columns([1, 3], vertical_alignment="center")
        if c1.button("Back", icon=":material/arrow_back:", type="tertiary", key=f"{key}_back"):
            stack.pop()
            _rerun(in_dialog)
        c2.caption(" › ".join(h.items[g].name for g in stack))
    if not kids:
        st.caption("Nothing under here yet.")
        return

    def label(v: str) -> str:
        it = h.items[v[2:]] if v.startswith("g:") else h.items[v]
        if it.group:
            return f"{it.name} ▸"
        return f"{it.name} · current" if cur is not None and it is cur else it.name

    options = [f"g:{k}" if h.items[k].group else k for k in kids]
    st.pills("Browse" if node is None else h.items[node].name, options, format_func=label,
             key=f"{key}_tree_{node}", on_change=_select, args=(key, f"{key}_tree_{node}"))
    if cur:
        st.toggle("All progressions", key=f"{key}_all_{node}")


def _form(ctx: Ctx, h: logic.Hierarchy, it: logic.Item, frame, day: dt.date, key: str, in_dialog: bool,
          can_change: bool) -> None:
    ss = st.session_state
    today = ctx.clock.today()
    week0 = ctx.clock.week_start(day)
    t_day = logic.leaf_totals(frame, day, day).get(it.id)
    t_week = logic.leaf_totals(frame, week0, week0 + dt.timedelta(days=6)).get(it.id)
    when = "today" if day == today else day.strftime("%a %b %-d")

    st.markdown(f"### {it.name}")
    bits = [h.path(it.id)] + ([f"Logging for **{day.strftime('%A, %b %-d')}**"] if day != today else [])
    st.caption(" · ".join(b for b in bits if b) or " ")
    st.markdown(f"<div class='stat-line'><b>{logic.fmt_totals(t_day) or '—'}</b> {when} · "
                f"<b>{logic.fmt_totals(t_week) or '—'}</b> this week</div>", unsafe_allow_html=True)
    switch(h, it, key)
    entry(ctx, h, it, frame, day, key, rerun=lambda: _rerun(in_dialog))

    row = st.container(horizontal=True)
    if can_change and row.button("Change skill", icon=":material/swap_horiz:", type="tertiary", key=f"{key}_change"):
        ss[f"{key}_sel"], ss[f"{key}_choosing"] = None, True
        _rerun(in_dialog)
    if it.inputs and day == today and row.button(
            "Counter" if it.inputs == ["Reps"] else "Timer", icon=":material/timer:", type="tertiary",
            key=f"{key}_timer", help="Start one on the Timers page"):
        start_timer(ctx, it, "Counter" if it.inputs == ["Reps"] else "Stopwatch")
        if "timers" in ctx.pages:
            st.switch_page(ctx.pages["timers"])
        st.rerun()
    if in_dialog and row.button("Done", icon=":material/check:", type="tertiary", key=f"{key}_done"):
        st.rerun()


def switch(h: logic.Hierarchy, it: logic.Item, key: str) -> None:
    """Jump to a neighbour: other rungs of its progression, or other skills under the same umbrella."""
    gid = h.ladder_of(it.id)
    if gid:
        others, label = [r.id for r in h.ladder(gid)], f"{h.items[gid].name} progression"
    else:
        parent = next((p for p in h.parents.get(it.id, []) if h.items[p].kind == "Group"), None)
        others = [c for c in h.children.get(parent, []) if h.items[c].good and h.items[c].active] if parent else []
        label = f"Also in {h.items[parent].name}" if parent else ""
    if len(others) > 1:
        st.pills(label, others, default=it.id, key=f"{key}_sw_{it.id}", format_func=lambda i: h.items[i].name,
                 on_change=_select, args=(key, f"{key}_sw_{it.id}"))


def entry(ctx: Ctx, h: logic.Hierarchy, it: logic.Item, frame, day: dt.date, key: str, rerun,
          session: str = "", on_set=None) -> None:
    """Variants, last time, the item's inputs, and Log (or ✓ Set N). Used by the log dialog and workouts."""
    if it.notes:
        st.caption(f"📝 {it.notes}")
    last = logic.last_log(frame, it.id)
    previous = logic.last_sets(frame, it.id, before_session=session) if it.inputs else []
    if previous:
        st.caption("Last time: " + " · ".join(logic.fmt_set(x) for x in previous)
                   + (f" ({previous[-1]['variant']})" if previous[-1]["variant"] else ""))

    variant = _variant(ctx, it, key, last, rerun)
    values = inputs(it, key, previous[-1] if previous else None)

    done = frame[(frame["id"] == it.id) & ((frame["session"] == session) if session else (frame["day"] == day))] \
        if it.sets and not frame.empty else frame.iloc[0:0]
    if it.sets and not done.empty:
        st.caption(("This workout: " if session else "Today: ") + " · ".join(
            f"{n}) {logic.fmt_set({'reps': r.reps, 'secs': r.secs, 'weight': r.weight, 'dist': r.dist})}"
            for n, r in enumerate(done.sort_values("row").itertuples(), start=1)))

    row = st.container(horizontal=True, wrap=False)
    if it.sets:
        n = len(done) + 1
        label, xp = f"Set {n}", None if n == 1 else 0  # XP once per skill per day or workout, not per set
    else:
        n, label, xp = 0, "Log", None
    if row.button(label, type="primary", icon=":material/check:" if it.sets else ":material/add:", width="stretch",
                  key=f"{key}_log_{it.id}", help="Numbers are optional: log it as done"):
        log_item(ctx, it, "Workout" if session else "Log", reps=values["reps"], secs=values["secs"], variant=variant,
                 day=day, weight=values["weight"], dist=values["dist"], effort=values["effort"], set_no=n,
                 session=session, xp=xp, frame=frame)
        if on_set:
            on_set(it)
        rerun()
    if last and it.inputs and not it.sets:
        again = " · ".join(b for b in (logic.fmt_set(last), last["variant"]) if b and b != "✓")
        if row.button(f"Same again{' · ' + again if again else ''}", width="stretch", key=f"{key}_again_{it.id}"):
            log_item(ctx, it, "Log", reps=last["reps"], secs=last["secs"], variant=last["variant"], day=day,
                     weight=last["weight"], dist=last["dist"], effort=last["effort"], frame=frame)
            rerun()


def _variant(ctx: Ctx, it: logic.Item, key: str, last: dict | None, rerun) -> str:
    """Variant pills, plus ＋ to add one right here (trying something new mid-workout)."""
    ss = st.session_state
    vkey = f"{key}_var_{it.id}"
    pending = ss.pop(f"{vkey}_pending", None)
    if pending:
        ss[vkey] = pending
    row = st.container(horizontal=True, vertical_alignment="center")
    variant = ""
    if it.variants:
        default = last["variant"] if last and last["variant"] in it.variants else None
        with row:
            variant = st.pills("Variant", it.variants, default=default if vkey not in ss else None, key=vkey,
                               label_visibility="collapsed") or ""
    with row.popover("Variant" if not it.variants else "", icon=":material/add:", help="Add a variant"):
        with st.form(f"{vkey}_new", border=False):
            name = st.text_input("New variant", placeholder="e.g. Deficit, Paused, Left side")
            if st.form_submit_button("Add") and name.strip():
                ss[f"{vkey}_pending"] = add_variant(ctx, it, name)
                rerun()  # inside the log dialog this keeps it open
    return variant


def inputs(it: logic.Item, key: str, previous: dict | None) -> dict:
    """The item's inputs, in a fixed order. Placeholders show last time's numbers."""
    out = {"reps": 0, "secs": 0, "weight": 0.0, "dist": 0.0, "effort": 0}
    prev = previous or {}
    if "Reps" in it.inputs:
        reps_key = f"{key}_reps_{it.id}"
        out["reps"] = int(st.number_input("Reps", 0, 100000, value=None, step=1, key=reps_key,
                                          placeholder=str(prev.get("reps") or 0)) or 0)
        row = st.container(horizontal=True, wrap=False)
        for by in (-1, 5, 10, 1):
            row.button(f"{by:+d}", key=f"{key}_c{by}_{it.id}", width="stretch", on_click=_count, args=(reps_key, by))
    row = st.container(horizontal=True, wrap=False, vertical_alignment="bottom")
    if "Weight" in it.inputs:
        out["weight"] = float(row.number_input(f"Weight ({logic.WEIGHT_UNIT})", 0.0, 2000.0, value=None, step=2.5,
                                               key=f"{key}_wt_{it.id}", placeholder=f"{prev.get('weight') or 0:g}")
                              or 0)
    if "Distance" in it.inputs:
        out["dist"] = float(row.number_input(f"Distance ({logic.DIST_UNIT})", 0.0, 1000.0, value=None, step=0.1,
                                             key=f"{key}_dist_{it.id}", placeholder=f"{prev.get('dist') or 0:g}")
                            or 0)
    if "Time" in it.inputs:
        out["secs"] = _time_input(it, key, prev)
    if "Effort" in it.inputs:
        out["effort"] = int(st.pills("Effort (1 easy – 10 max)", list(range(1, 11)), key=f"{key}_eff_{it.id}") or 0)
    return out


def _time_input(it: logic.Item, key: str, prev: dict) -> int:
    """Minutes and seconds, typed in, or filled by the stopwatch next to them."""
    ss = st.session_state
    mk, sk, wk = f"{key}_min_{it.id}", f"{key}_sec_{it.id}", f"{key}_watch_{it.id}"
    row = st.container(horizontal=True, wrap=False, vertical_alignment="bottom")
    p_m, p_s = divmod(int(prev.get("secs") or 0), 60)
    mins = row.number_input("Minutes", 0, 1440, value=None, step=1, key=mk, placeholder=str(p_m))
    sec = row.number_input("Seconds", 0, 59, value=None, step=5, key=sk, placeholder=str(p_s))
    started = ss.get(wk)
    if started is None:
        row.button("", icon=":material/timer:", key=f"{wk}_go", help="Time it", on_click=_watch_start, args=(wk,))
    else:
        row.button("", icon=":material/stop:", type="primary", key=f"{wk}_stop", help="Stop and fill in",
                   on_click=_watch_stop, args=(wk, mk, sk))
        from views import timers
        timers.clock(logic.Timer(wk, "", "", "Stopwatch", 0, started, 0, 0, 0))
    return int(mins or 0) * 60 + int(sec or 0)


def _watch_start(wk: str) -> None:
    st.session_state[wk] = round(time.time(), 1)


def _watch_stop(wk: str, mk: str, sk: str) -> None:
    ss = st.session_state
    secs = int(time.time() - ss.pop(wk, time.time()))
    ss[mk], ss[sk] = divmod(secs, 60)


def _count(key: str, by: int) -> None:
    st.session_state[key] = max(0, (st.session_state.get(key) or 0) + by)
