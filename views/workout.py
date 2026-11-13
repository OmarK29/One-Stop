"""Workout: a gym-style session. Add skills (or start from a tracker like Hypertrophy), tick off sets with last
time's numbers to beat, and a rest timer starts after each set. New bests are flagged as they happen. Quick
logging everywhere else is unchanged; this is the mode for the gym or a planned workout."""
from __future__ import annotations

import time

import streamlit as st

import logic
from views import log as log_view
from views.common import Ctx, log_item, start_timer
from views.timers import clock, quick_skill_form

REST_LABEL, BOARD = "Rest", "Workout"
WORKOUT_XP = 10


def running(ctx: Ctx) -> logic.Timer | None:
    return next((t for t in ctx.timers() if t.mode == logic.SESSION_MODE), None)


def session_id(s: logic.Timer) -> str:
    return f"W{int(s.started or 0)}"


def page(ctx: Ctx) -> None:
    st.subheader("Workout")
    flash = st.session_state.pop("wk_flash", None)
    if flash:
        st.success(flash, icon=":material/emoji_events:")
    h = logic.build_hierarchy(ctx.items())
    frame = logic.log_frame(ctx.log(), ctx.clock)
    s = running(ctx)
    if s is None:
        _start(ctx, h, frame)
    else:
        _session(ctx, h, frame, s)


def banner(ctx: Ctx) -> None:
    """On other pages while a workout runs: one line back to it."""
    s = running(ctx)
    if s and "workout" in ctx.pages:
        mins = int((time.time() - (s.started or time.time())) // 60)
        st.page_link(ctx.pages["workout"], label=f"{s.label} running · {mins} min · open", icon=":material/fitness_center:")


# ---------- starting ----------

def _start(ctx: Ctx, h: logic.Hierarchy, frame) -> None:
    st.caption("For the gym or a planned workout: add skills, tick off sets with last time's numbers to beat, and "
               "a rest timer starts after each set.")
    trackers = ctx.trackers()
    name = st.text_input("Name", placeholder="e.g. Gym, Hypertrophy A", key="wk_name")
    start_from = st.pills("Start with", ["Empty"] + list(trackers), default="Empty", key="wk_from", required=True,
                          help="A tracker brings its skills in, at your current rung")
    if st.button("Start workout", type="primary", icon=":material/play_arrow:", width="stretch", key="wk_go"):
        skills = []
        if start_from in trackers:
            skip = logic.off_rungs(h, frame)
            for col in trackers[start_from]:
                skills += [i for i in logic.column_leaves(h, col) if i not in skip and i not in skills
                           and h.items[i].active and h.items[i].good]
        start_timer(ctx, None, logic.SESSION_MODE, label=name.strip() or (start_from if start_from != "Empty"
                                                                         else "Workout"))
        s = running(ctx)
        if s and skills:
            _set_skills(ctx, s, skills)
        st.rerun()
    recent = frame[frame["id"] == logic.WORKOUT_ID].sort_values("row", ascending=False).head(5) \
        if not frame.empty else frame
    if not recent.empty:
        log = ctx.log()
        notes = dict(zip(log["_row"], log["Note"])) if "Note" in log else {}
        st.markdown("#### Recent workouts")
        for r in recent.itertuples():
            st.caption(f"{r.day.strftime('%a %b %-d')} · {logic.fmt_secs(r.secs)} · {notes.get(r.row, '')}")


# ---------- running ----------

def _session(ctx: Ctx, h: logic.Hierarchy, frame, s: logic.Timer) -> None:
    sid = session_id(s)
    done = frame[frame["session"] == sid] if not frame.empty else frame
    head = st.container(horizontal=True, wrap=False, vertical_alignment="center")
    with head.container(gap=None):
        st.markdown(f"**{s.label}**")
        vol = float((done["reps"] * done["weight"]).sum()) if not done.empty else 0
        st.caption(f"{len(done)} sets" + (f" · {int(done['reps'].sum())} reps" if not done.empty else "")
                   + (f" · {vol:,.0f} {logic.WEIGHT_UNIT} lifted" if vol else ""))
    with head.container(width=120, horizontal_alignment="right"):
        clock(logic.Timer(s.id, "", "", "Stopwatch", 0, s.started, 0, 0, 0))
    _rest(ctx)

    skills = [i for i in logic.split_list(s.item_id) if i in h.items]
    today = ctx.clock.today()
    focus = st.session_state.get("wk_focus") or (skills[-1] if skills else None)
    for iid in skills:
        it = h.items[iid]
        n = int((done["id"] == iid).sum()) if not done.empty else 0
        with st.expander(f"{it.name}" + (f" · {n} set{'s' * (n != 1)}" if n else ""), expanded=iid == focus):
            _swap(ctx, h, s, skills, it)
            log_view.entry(ctx, h, it, frame, today, f"wk_{iid}", rerun=st.rerun, session=sid,
                           on_set=lambda x: _after_set(ctx, x))
            if st.button("Remove from workout", type="tertiary", key=f"wk_rm_{iid}", icon=":material/remove:"):
                _set_skills(ctx, s, [i for i in skills if i != iid])
                st.rerun()

    _add(ctx, h, s, skills)
    st.divider()
    row = st.container(horizontal=True)
    if row.button("Finish workout", type="primary", icon=":material/flag:", key="wk_finish"):
        _finish(ctx, h, frame, s, done)
    if row.button("Cancel", type="tertiary", key="wk_cancel", help="Ends it without a summary; sets stay logged"):
        _end(ctx, s)
        st.rerun()


def _swap(ctx: Ctx, h: logic.Hierarchy, s: logic.Timer, skills: list[str], it: logic.Item) -> None:
    """Move up or down a progression without leaving the workout."""
    gid = h.ladder_of(it.id)
    if not gid:
        return
    rungs = [r.id for r in h.ladder(gid)]
    pick = st.pills(f"{h.items[gid].name} progression", rungs, default=it.id, key=f"wk_sw_{it.id}",
                    format_func=lambda i: h.items[i].name)
    if pick and pick != it.id:
        _set_skills(ctx, s, [pick if i == it.id else i for i in skills if i != pick or i == it.id])
        st.session_state.wk_focus = pick
        st.rerun()


def _add(ctx: Ctx, h: logic.Hierarchy, s: logic.Timer, skills: list[str]) -> None:
    ss = st.session_state
    pool = [it.id for it in sorted(h.items.values(), key=lambda it: it.row)
            if it.active and it.good and it.inputs and it.id not in skills]
    row = st.container(horizontal=True, vertical_alignment="bottom")
    pick = row.selectbox("Add a skill", pool, index=None, key=f"wk_add_{len(skills)}", placeholder="Search skills",
                         format_func=lambda i: " · ".join(b for b in (h.items[i].name, h.path(i)) if b))
    with row.popover("", icon=":material/add:", help="New skill"):
        new_id = quick_skill_form(ctx, h, "wk_ns")
    pick = new_id or pick
    if pick:
        _set_skills(ctx, s, skills + [pick])
        ss.wk_focus = pick
        st.rerun()


def _after_set(ctx: Ctx, it: logic.Item) -> None:
    st.session_state.wk_focus = it.id
    start_rest(ctx, it.rest or logic.to_int(ctx.settings.get("rest_seconds"), 90))


def start_rest(ctx: Ctx, secs: int) -> None:
    """One rest timer at a time: a new set restarts it."""
    for t in _rest_timers(ctx):
        _delete(ctx, t)
    if secs > 0:
        start_timer(ctx, None, "Countdown", secs, "color=orange", board=BOARD, label=REST_LABEL)


def _rest_timers(ctx: Ctx) -> list[logic.Timer]:
    return [t for t in ctx.timers() if t.board == BOARD and t.label == REST_LABEL]


def _rest(ctx: Ctx) -> None:
    rests = _rest_timers(ctx)
    if not rests:
        return
    t = rests[0]
    with st.container(border=True):
        row = st.container(horizontal=True, wrap=False, vertical_alignment="center")
        row.markdown(":orange[**Rest**]")
        with row.container(width=110):
            clock(t, small=False)
        if row.button("+30s", key="wk_rest_add"):
            _update(ctx, t, {"Length": t.length + 30})
        if row.button("Skip", key="wk_rest_skip", type="tertiary"):
            _delete(ctx, t)
            st.rerun()


def _finish(ctx: Ctx, h: logic.Hierarchy, frame, s: logic.Timer, done) -> None:
    secs = int(time.time() - (s.started or time.time()))
    names = [h.items[i].name for i in dict.fromkeys(done["id"]) if i in h.items] if not done.empty else []
    sid = session_id(s)
    before = frame[frame["session"] != sid] if not frame.empty else frame
    bests = []
    for iid in dict.fromkeys(done["id"]) if not done.empty else []:
        prev = logic.bests(before, iid)
        for r in done[done["id"] == iid].sort_values("row").itertuples():
            hit = logic.new_bests(prev, {"reps": r.reps, "secs": r.secs, "weight": r.weight, "dist": r.dist})
            if hit and iid in h.items:
                bests.append(f"{h.items[iid].name} ({', '.join(hit)})")
            prev = {k: max(prev.get(k, 0), v) for k, v in {"reps": r.reps, "secs": r.secs, "weight": r.weight,
                                                           "dist": r.dist, "volume": r.reps * r.weight}.items()} \
                if prev else prev
    summary = f"{len(done)} sets · {len(names)} skill{'s' * (len(names) != 1)}"
    workout = logic.Item(id=logic.WORKOUT_ID, name=s.label, domain="Physical", kind="Good", period="Daily", target=0,
                         xp=WORKOUT_XP, priority="Normal", block="", tags=[], counters=[], active=True, notes="",
                         row=10**6)
    log_item(ctx, workout, "Workout", note=summary, secs=secs, session=sid, frame=frame, check_bests=False)
    _end(ctx, s)
    st.session_state.wk_flash = (f"{s.label} done: {logic.fmt_secs(secs)} · {summary}"
                                 + (f" · new bests: {'; '.join(bests)}" if bests else "") + f". +{WORKOUT_XP} XP.")
    st.rerun()


def _end(ctx: Ctx, s: logic.Timer) -> None:
    for t in _rest_timers(ctx):
        _delete(ctx, t)
    _delete(ctx, s)
    st.session_state.pop("wk_focus", None)


def _set_skills(ctx: Ctx, s: logic.Timer, skills: list[str]) -> None:
    _update(ctx, s, {"Item ID": ", ".join(dict.fromkeys(skills))}, rerun=False)


def _row(ctx: Ctx, tid: str) -> int | None:
    df = ctx.store.read("Timers", fresh=True)
    match = df[df["ID"].astype(str).str.strip() == tid]
    return int(match["_row"].iloc[0]) if not match.empty else None


def _update(ctx: Ctx, t: logic.Timer, values: dict, rerun: bool = True) -> None:
    row = _row(ctx, t.id)
    if row:
        ctx.store.update_row("Timers", row, values)
    if rerun:
        st.rerun()


def _delete(ctx: Ctx, t: logic.Timer) -> None:
    row = _row(ctx, t.id)
    if row:
        ctx.store.delete_row("Timers", row)
