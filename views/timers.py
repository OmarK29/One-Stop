"""Timers: several stopwatches, countdowns and rep counters at once. Each can belong to a skill, and Log
records its time and reps. They're kept in the sheet, so they keep running with the tab closed."""
from __future__ import annotations

import time

import streamlit as st

import logic
from views.common import Ctx, log_item, start_timer

PRESETS = {"30s": 30, "1 min": 60, "2 min": 120, "5 min": 300, "10 min": 600}

_CLOCK_JS = """
export default function(component) {
  const { data, parentElement } = component;
  let el = parentElement.querySelector('.clock');
  if (!el) { el = document.createElement('div'); parentElement.appendChild(el); }
  el.className = 'clock' + (data.small ? ' small' : '');
  const t0 = performance.now();
  let beeped = data.finished;
  const fmt = (s) => {
    s = Math.max(0, Math.floor(s));
    const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
    return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(x).padStart(2, '0');
  };
  const beep = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      [0, 0.3, 0.6].forEach((at) => {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.frequency.value = 880; o.connect(g); g.connect(ctx.destination);
        g.gain.setValueAtTime(0.2, ctx.currentTime + at);
        o.start(ctx.currentTime + at); o.stop(ctx.currentTime + at + 0.18);
      });
    } catch (e) {}
    if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 200]);
  };
  const tick = () => {
    const s = data.secs + (data.running ? (performance.now() - t0) / 1000 : 0);
    if (data.mode === 'Countdown' && data.length > 0) {
      const left = data.length - s;
      el.textContent = left > 0 ? fmt(Math.ceil(left)) : 'Done';
      el.classList.toggle('done', left <= 0);
      if (left <= 0 && !beeped && data.running) { beeped = true; beep(); }
    } else {
      el.textContent = fmt(s);
    }
    el.classList.toggle('paused', !data.running);
  };
  tick();
  const id = setInterval(tick, 250);
  return () => clearInterval(id);
}
"""
_CLOCK_CSS = """
.clock { font-size: 3rem; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
.clock.small { font-size: 1.15rem; font-weight: 600; }
.clock.paused { opacity: .5; }
.clock.done { color: var(--st-primary-color, #1F5C50); }
"""
_clock = st.components.v2.component("one_stop_clock", js=_CLOCK_JS, css=_CLOCK_CSS)


def clock(t: logic.Timer, small: bool = False) -> None:
    """A clock that ticks in the browser, so the page doesn't have to rerun every second."""
    now = time.time()
    # The key changes whenever the timer's state does, so the clock restarts from the new numbers.
    _clock(data={"secs": t.seconds(now), "running": t.running, "mode": t.mode, "length": t.length,
                 "finished": t.finished(now), "small": small},
           key=f"clk_{t.id}_{t.started}_{t.elapsed}_{int(small)}")


def page(ctx: Ctx) -> None:
    st.subheader("Timers")
    h = logic.build_hierarchy(ctx.items())
    _new(ctx, h)
    timers = ctx.timers()
    if not timers:
        st.caption("No timers running. Start as many as you like; they keep going with the app closed.")
    for t in timers:
        _card(ctx, h, t.id)


def _new(ctx: Ctx, h: logic.Hierarchy) -> None:
    pool = [it.id for it in sorted(h.items.values(), key=lambda it: it.row) if it.active and it.good]
    with st.expander("New timer or counter", icon=":material/add_alarm:", expanded=not ctx.timers()):
        iid = st.selectbox("Skill (optional)", pool, index=None, key="tm_item", placeholder="Just a timer",
                           format_func=lambda i: " · ".join(b for b in (h.items[i].name, h.path(i)) if b))
        item = h.items.get(iid) if iid else None
        default = "Counter" if item and item.measure == "Reps" else "Stopwatch"
        mode = st.segmented_control("Mode", logic.TIMER_MODES, default=default, key=f"tm_mode_{iid}") or default
        length = 0
        if mode == "Countdown":
            preset = st.pills("Length", list(PRESETS) + ["Custom"], default="1 min", key="tm_preset")
            if preset == "Custom":
                c1, c2 = st.columns(2)
                length = (c1.number_input("Minutes", 0, 600, 3, key="tm_min") * 60
                          + c2.number_input("Seconds", 0, 59, 0, step=5, key="tm_sec"))
            else:
                length = PRESETS.get(preset or "1 min", 60)
        caption = {"Stopwatch": "Counts up. Pause any time; Log records the time.",
                   "Countdown": "Counts down and beeps at zero. Log records the time you did.",
                   "Counter": "Tap to count reps. Log records the count."}[mode]
        st.caption(caption)
        if st.button("Start", type="primary", icon=":material/play_arrow:", width="stretch", key="tm_start",
                     disabled=mode == "Countdown" and not length):
            start_timer(ctx, item, mode, length)
            st.session_state.pop("tm_item", None)
            st.rerun()


def _fresh_row(ctx: Ctx, tid: str) -> int | None:
    """The timer's row right now, in case another device added or removed timers since the last read."""
    df = ctx.store.read("Timers", fresh=True)
    match = df[df["ID"].astype(str).str.strip() == tid]
    return int(match["_row"].iloc[0]) if not match.empty else None


def _bump(key: str, by: int) -> None:
    st.session_state[key] = max(0, st.session_state.get(key, 0) + by)


@st.fragment
def _card(ctx: Ctx, h: logic.Hierarchy, tid: str) -> None:
    # Look the timer up each run: a fragment rerun reuses its arguments, which would be stale after Pause.
    t = next((x for x in ctx.timers() if x.id == tid), None)
    if t is None:
        return
    ss = st.session_state
    item = h.items.get(t.item_id)
    reps_key = f"tm_reps_{t.id}"
    ss.setdefault(reps_key, t.reps)
    counts_reps = t.mode == "Counter" or (item is not None and item.measure in ("Reps", "Both"))
    now = time.time()

    with st.container(border=True):
        top = st.container(horizontal=True, wrap=False, vertical_alignment="top")
        with top.container(gap=None):
            st.markdown(f"**{item.name if item else t.label}**")
            st.caption(" · ".join(b for b in (t.mode + (f" {logic.fmt_secs(t.length)}" if t.mode == "Countdown"
                                                        else ""), h.path(item.id) if item else "") if b))
        if top.button("", icon=":material/close:", type="tertiary", key=f"tm_x_{t.id}", help="Discard",
                      width="content"):
            row = _fresh_row(ctx, t.id)
            if row:
                ctx.store.delete_row("Timers", row)
            st.rerun()

        if t.mode != "Counter":
            clock(t)
        if counts_reps:
            st.markdown(f"<div class='rep-count'>{ss[reps_key]} <span>reps</span></div>", unsafe_allow_html=True)
            row = st.container(horizontal=True, wrap=False)
            for by in (-1, 5, 10):
                row.button(f"{by:+d}", key=f"tm_{by}_{t.id}", width="stretch", on_click=_bump, args=(reps_key, by))
            row.button("+1", type="primary", key=f"tm_1_{t.id}", width="stretch", on_click=_bump,
                       args=(reps_key, 1))

        variant = ""
        if item and item.variants:
            variant = st.pills("Variant", item.variants, key=f"tm_var_{t.id}") or ""
        target = item
        if item is None:
            pool = [it.id for it in sorted(h.items.values(), key=lambda it: it.row) if it.active and it.good]
            pick = st.selectbox("Log to", pool, index=None, key=f"tm_to_{t.id}", placeholder="Pick a skill to log to",
                                format_func=lambda i: h.items[i].name)
            target = h.items.get(pick) if pick else None

        c1 = c2 = c3 = st.container(horizontal=True, wrap=False)
        if t.mode != "Counter":
            if t.running:
                if c1.button("Pause", icon=":material/pause:", width="stretch", key=f"tm_p_{t.id}"):
                    _update(ctx, t, Started="", Elapsed=round(t.seconds(now), 1), Reps=ss[reps_key])
            elif c1.button("Resume", icon=":material/play_arrow:", width="stretch", key=f"tm_r_{t.id}",
                           disabled=t.finished(now)):
                _update(ctx, t, Started=round(now, 1), Reps=ss[reps_key])
        if c2.button("Reset", icon=":material/restart_alt:", width="stretch", key=f"tm_z_{t.id}"):
            ss[reps_key] = 0
            _update(ctx, t, Started=round(now, 1) if t.running else "", Elapsed=0, Reps=0)
        secs, reps = t.logged_secs(now), ss[reps_key] if counts_reps else 0
        if c3.button("Log", type="primary", icon=":material/check:", width="stretch", key=f"tm_log_{t.id}",
                     disabled=target is None or not (secs or reps)):
            if target.measure == "Reps":
                secs = 0  # a reps-only skill keeps the count; the time is just how long the set took
            log_item(ctx, target, "Timer", reps=reps, secs=secs, variant=variant)
            row = _fresh_row(ctx, t.id)
            if row:
                ctx.store.delete_row("Timers", row)
            ss.pop(reps_key, None)
            st.rerun()


def _update(ctx: Ctx, t: logic.Timer, **values) -> None:
    row = _fresh_row(ctx, t.id)
    if row:
        ctx.store.update_row("Timers", row, values)
    st.rerun()


def strip(ctx: Ctx) -> None:
    """Running timers in one line each, for the top of Today."""
    timers = ctx.timers()
    if not timers:
        return
    h_items = {it.id: it for it in ctx.items()}
    with st.container(border=True, gap=None):
        for t in timers:
            row = st.container(horizontal=True, wrap=False, vertical_alignment="center")
            name = h_items[t.item_id].name if t.item_id in h_items else t.label
            row.markdown(f"**{name}**" + (f" · {st.session_state.get(f'tm_reps_{t.id}', t.reps)} reps"
                                           if t.mode == "Counter" else ""))
            if t.mode != "Counter":
                with row.container(width=90, horizontal_alignment="right"):
                    clock(t, small=True)
        if "timers" in ctx.pages:
            st.page_link(ctx.pages["timers"], label="Open timers", icon=":material/timer:")
