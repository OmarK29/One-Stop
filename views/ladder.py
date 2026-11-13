"""Ease ladders: when a goal is hard to start, get a few minutes to start it. If you don't, the step gets
easier (run an hour → elliptical for 30 → just get on it → go downstairs → change → 5 squats → stand up).
Starting any step counts, and once you're going you can always do more."""
from __future__ import annotations

import html
import time

import pandas as pd
import streamlit as st

import logic
from views import timers
from views.common import Ctx, log_item, start_ladder, start_timer


def running(ctx: Ctx) -> logic.Timer | None:
    return next((t for t in ctx.timers() if t.mode == logic.LADDER_MODE), None)


def section(ctx: Ctx, h: logic.Hierarchy) -> None:
    """The running ladder if there is one, otherwise a way to start one. Top of the Timers page."""
    flash = st.session_state.pop("ladder_flash", None)
    if flash:
        st.success(flash, icon=":material/rocket_launch:")
    ladders = ctx.ladders()
    run = running(ctx)
    if run:
        _card(ctx, h, run, ladders)
    else:
        _picker(ctx, ladders)


def _card(ctx: Ctx, h: logic.Hierarchy, run: logic.Timer, ladders: dict[str, list[logic.Rung]]) -> None:
    rungs = ladders.get(run.label)
    with st.container(border=True):
        top = st.container(horizontal=True, wrap=False, vertical_alignment="top")
        if not rungs:
            top.markdown(f"**{run.label}** isn't in your Ladders tab any more.")
            if top.button("Stop", key="ld_stop_missing"):
                _remove(ctx, run)
                st.rerun()
            return
        now = time.time()
        spot = logic.ladder_spot(rungs, run.reps, run.started or now, now)
        r, n = rungs[spot.index], len(rungs)
        with top.container(gap=None):
            st.caption(f"EASE LADDER · {run.label.upper()}")
            st.markdown(f"Step **{spot.index + 1}** of {n}")
        if top.button("", icon=":material/close:", type="tertiary", key="ld_x", help="Stop this ladder",
                      width="content"):
            _remove(ctx, run)
            st.rerun()
        st.markdown(f"<div class='ladder-do'>{html.escape(r.do)}</div>", unsafe_allow_html=True)

        if spot.ran_out:
            st.info("The easiest step's time ran out too. That tells you something about today, and it isn't a "
                    "failure. Rest, eat, or drink some water, then try again.", icon=":material/self_improvement:")
            row = st.container(horizontal=True)
            if row.button("I started anyway", type="primary", key="ld_anyway", icon=":material/check:"):
                _started(ctx, h, run, rungs, spot.index)
            if row.button("Try again from the top", key="ld_again", icon=":material/restart_alt:"):
                _move(ctx, run, 0)
            if row.button("Try the easiest step", key="ld_easiest"):
                _move(ctx, run, n - 1)
            return

        row = st.container(horizontal=True, wrap=False, vertical_alignment="center")
        row.caption("Start within")
        with row.container(width=150):
            timers.countdown(f"ld_{run.id}_{spot.index}", spot.into, spot.window)
        if spot.index + 1 < n:
            st.caption(f"If not, it gets easier: {rungs[spot.index + 1].do}")
        else:
            st.caption("This is the easiest step.")
        row = st.container(horizontal=True, wrap=False)
        if row.button("I'm starting", type="primary", icon=":material/play_arrow:", width="stretch",
                      key="ld_start"):
            _started(ctx, h, run, rungs, spot.index)
        if row.button("Easier now", icon=":material/south:", width="stretch", key="ld_easier",
                      disabled=spot.index + 1 >= n):
            _move(ctx, run, spot.index + 1)
        if spot.index > 0 and st.button(f"Harder: {rungs[spot.index - 1].do}", icon=":material/north:",
                                        type="tertiary", key="ld_harder"):
            _move(ctx, run, spot.index - 1)
        with st.expander("All steps"):
            st.markdown("\n".join(f"{i + 1}. {'**' + x.do + '**' if i == spot.index else x.do} · {x.minutes} min"
                                  for i, x in enumerate(rungs)))


def _started(ctx: Ctx, h: logic.Hierarchy, run: logic.Timer, rungs: list[logic.Rung], i: int) -> None:
    """Starting is the win: log it, then time or log the skill it maps to."""
    r = rungs[i]
    ctx.store.append("Log", [ctx.clock.stamp(), ctx.clock.today().isoformat(), logic.LADDER_ID, f"Started: {r.do}",
                             "Mental", "Good", logic.LADDER_XP, "Ladder", f"{run.label} · step {i + 1} of {len(rungs)}",
                             "", "", ""])
    _remove(ctx, run)
    item = h.find(r.logs_as) if r.logs_as else None
    follow = ""
    if item and item.good:
        if not item.inputs and not item.variants:
            log_item(ctx, item, "Ladder")
        else:
            start_timer(ctx, item, "Counter" if item.inputs == ["Reps"] else "Stopwatch")
            follow = f" A {'counter' if item.inputs == ['Reps'] else 'timer'} for {item.name} is running below."
    more = f" Once you're going, “{rungs[i - 1].do}” is fair game, but you don't owe it." if i > 0 else ""
    st.session_state.ladder_flash = f"You started: {r.do}. That was the hard part. +{logic.LADDER_XP} XP.{follow}{more}"
    st.rerun()


def _move(ctx: Ctx, run: logic.Timer, index: int) -> None:
    row = _row(ctx, run.id)
    if row:
        ctx.store.update_row("Timers", row, {"Reps": index, "Started": round(time.time(), 1)})
    st.rerun()


def _remove(ctx: Ctx, run: logic.Timer) -> None:
    row = _row(ctx, run.id)
    if row:
        ctx.store.delete_row("Timers", row)


def _row(ctx: Ctx, tid: str) -> int | None:
    df = ctx.store.read("Timers", fresh=True)
    match = df[df["ID"].astype(str).str.strip() == tid]
    return int(match["_row"].iloc[0]) if not match.empty else None


def _picker(ctx: Ctx, ladders: dict[str, list[logic.Rung]]) -> None:
    with st.expander("Hard to start? Ease ladder", icon=":material/stairs:"):
        st.caption("Pick a goal and get a few minutes to start it. If you don't, the step gets easier, all the "
                   "way down to something tiny. Starting any step counts.")
        if st.session_state.get("ld_pending") in ladders:
            st.session_state.ld_pick = st.session_state.pop("ld_pending")
        if ladders:
            name = st.selectbox("Ladder", list(ladders), key="ld_pick")
            rungs = ladders[name]
            at = st.selectbox("Start at", range(len(rungs)), key=f"ld_at_{name}",
                              format_func=lambda i: f"{i + 1}. {rungs[i].do} · {rungs[i].minutes} min")
            if st.button("Start", type="primary", icon=":material/play_arrow:", width="stretch", key="ld_go"):
                start_ladder(ctx, name, at)
                st.rerun()
        with st.popover("New ladder", icon=":material/add:"):
            _new_ladder(ctx, ladders)


def _new_ladder(ctx: Ctx, ladders: dict[str, list[logic.Rung]]) -> None:
    with st.form("ld_new", border=False):
        name = st.text_input("Goal", placeholder="e.g. Study Arabic for an hour", max_chars=60)
        steps = st.text_area("Easier steps, one per line, hardest first",
                             placeholder="Study for an hour\nStudy for 15 minutes\nOpen the book\nSit at the desk",
                             height=150)
        minutes = st.number_input("Minutes to start each step", 1, 120,
                                  logic.to_int(ctx.settings.get("ladder_minutes"), 5))
        if not st.form_submit_button("Create", type="primary"):
            return
    name = name.strip()
    lines = [x.strip(" -•\t") for x in steps.splitlines() if x.strip(" -•\t")]
    if not name or len(lines) < 2:
        st.error("Give it a goal and at least two steps.")
        return
    if name in ladders:
        st.error(f"There's already a ladder called {name}. Edit it on Manage → Ladders.")
        return
    df = ctx.store.read("Ladders")
    new = pd.DataFrame({"Ladder": name, "Step": range(1, len(lines) + 1), "Do": lines, "Minutes": int(minutes),
                        "Logs as": ""})
    ctx.store.replace("Ladders", pd.concat([df, new], ignore_index=True))
    st.session_state.ld_pending = name  # selected next run, before the selectbox exists
    st.rerun()


def strip_line(ctx: Ctx, run: logic.Timer, row) -> None:
    """One line for Today's timer strip."""
    rungs = ctx.ladders().get(run.label)
    if not rungs:
        return
    now = time.time()
    spot = logic.ladder_spot(rungs, run.reps, run.started or now, now)
    row.markdown(f"**{html.escape(rungs[spot.index].do)}**" + (" · time's up" if spot.ran_out else ""))
    if not spot.ran_out:
        with row.container(width=90, horizontal_alignment="right"):
            timers.countdown(f"strip_{run.id}_{spot.index}", spot.into, spot.window, small=True)


def offer(ctx: Ctx, h: logic.Hierarchy, item: logic.Item, key: str) -> None:
    """'Hard to start?' for an item that has a ladder. Starts at the step that logs as it."""
    ladders = ctx.ladders()
    names = logic.ladders_for(ladders, h, item.id)
    if not names:
        return
    name = names[0]
    targets = {item.id, *h.ancestors(item.id)}
    at = next((i for i, r in enumerate(ladders[name]) if (x := h.find(r.logs_as)) and x.id in targets), 0)
    if st.button("Hard to start? Ease into it", icon=":material/stairs:", type="tertiary", key=key,
                 help=f"Starts the {name} ladder"):
        start_ladder(ctx, name, at)
        if "timers" in ctx.pages:
            st.switch_page(ctx.pages["timers"])
        st.rerun()
