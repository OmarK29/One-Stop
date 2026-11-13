"""Timers: as many stopwatches, countdowns, intervals and rep counters as you like, at once. Each can belong to
a skill, and Log records its time and reps. Boards start a saved set together. Timers live in the sheet, so they
keep running with the tab closed. Countdowns run into overtime instead of stopping."""
from __future__ import annotations

import time

import streamlit as st

import logic
from views.common import Ctx, add_skill, log_item, start_timer, timer_history

PRESETS = {"30s": 30, "1 min": 60, "2 min": 120, "5 min": 300, "10 min": 600}
DELAYS = {"Now": 0, "5s": 5, "10s": 10, "30s": 30, "1 min": 60}
HIDDEN = (logic.LADDER_MODE, logic.SESSION_MODE)  # shown by their own pages, not as timer cards

_CLOCK_JS = """
export default function(component) {
  const { data, parentElement } = component;
  let el = parentElement.querySelector('.clock');
  if (!el) { el = document.createElement('div'); parentElement.appendChild(el); }
  const t0 = performance.now();
  let beeped = data.finished, lastPhase = null, lastN = null;
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
    let text, cls = '';
    if (s < 0) {
      text = 'in ' + fmt(Math.ceil(-s)); cls = 'waiting';
    } else if (data.mode === 'Countdown' && data.length > 0 && data.repeat) {
      const n = Math.floor(s / data.length);
      text = fmt(Math.ceil(data.length - (s % data.length))) + (n ? ' ×' + n : '');
      if (lastN !== null && n !== lastN && data.running) beep();
      lastN = n;
    } else if (data.mode === 'Countdown' && data.length > 0) {
      const left = data.length - s;
      if (left > 0) { text = fmt(Math.ceil(left)); }
      else {
        text = '+' + fmt(-left); cls = 'over';  // overtime: keeps counting instead of stopping
        if (!beeped && data.running) {
          beeped = true; beep();
          if (data.notify) component.setTriggerValue('expired', true);
        }
      }
    } else if (data.mode === 'Interval') {
      const w = data.work, r = data.rest, n = data.rounds, cyc = Math.max(1, w + r);
      if (n && s >= cyc * n - r) {
        text = 'Done'; cls = 'over';
        if (!beeped && data.running) { beeped = true; beep(); }
      } else {
        const k = Math.floor(s / cyc), into = s % cyc, work = into < w;
        text = (work ? 'Work ' : 'Rest ') + fmt(Math.ceil(work ? w - into : cyc - into)) + ' · ' + (k + 1) + '/' + (n || '∞');
        cls = work ? 'work' : 'rest';
        const ph = k * 2 + (work ? 0 : 1);
        if (lastPhase !== null && ph !== lastPhase && data.running) beep();
        lastPhase = ph;
      }
    } else {
      text = fmt(s);
    }
    el.textContent = text;
    el.className = 'clock' + (data.small ? ' small' : '') + (cls ? ' ' + cls : '') + (data.running ? '' : ' paused');
  };
  tick();
  const id = setInterval(tick, 250);
  return () => clearInterval(id);
}
"""
_CLOCK_CSS = """
.clock { font-size: 3rem; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
.clock.work, .clock.rest { font-size: 2rem; }
.clock.small { font-size: 1.15rem; font-weight: 600; }
.clock.paused, .clock.waiting { opacity: .5; }
.clock.over, .clock.rest { color: var(--st-primary-color, #1F5C50); }
"""
_clock = st.components.v2.component("one_stop_clock", js=_CLOCK_JS, css=_CLOCK_CSS)


def clock(t: logic.Timer, small: bool = False) -> None:
    """A clock that ticks in the browser, so the page doesn't have to rerun every second."""
    now = time.time()
    o = t.options
    # The key changes whenever the timer's state does, so the clock restarts from the new numbers.
    _clock(data={"secs": now - t.started + t.elapsed if t.started is not None else t.elapsed,
                 "running": t.running, "mode": t.mode, "length": t.length, "finished": t.finished(now),
                 "small": small, "repeat": bool(o.get("repeat")), "work": o.get("work", 0), "rest": o.get("rest", 0),
                 "rounds": o.get("rounds", 0)},
           key=f"clk_{t.id}_{t.started}_{t.elapsed}_{t.length}_{int(small)}")


def countdown(key: str, into: float, window: int, small: bool = False) -> None:
    """Counts down a ladder step's window, beeps at zero, then reruns the page so the next step shows."""
    _clock(data={"secs": into, "running": True, "mode": "Countdown", "length": window, "finished": False,
                 "small": small, "notify": True},
           key=f"cd_{key}_{int(window)}_{int(into)}_{int(small)}", on_expired_change=lambda: None)


def page(ctx: Ctx) -> None:
    from views import ladder  # ladder imports this module for its clock

    st.subheader("Timers")
    h = logic.build_hierarchy(ctx.items())
    ladder.section(ctx, h)
    timers = [t for t in ctx.timers() if t.mode not in HIDDEN]
    _boards(ctx, h, timers)
    _new(ctx, h, expanded=not timers)
    if not timers:
        st.caption("No timers running. Start as many as you like; they keep going with the app closed.")
    groups: dict[str, list[logic.Timer]] = {}
    for t in timers:
        groups.setdefault(t.board, []).append(t)
    for board, ts in groups.items():
        if board:
            head = st.container(horizontal=True, vertical_alignment="center")
            head.markdown(f"##### {board}")
            if head.button("Stop all", key=f"tm_stopall_{board}", type="tertiary", icon=":material/stop:"):
                for t in ts:
                    _discard(ctx, t)
                st.rerun()
        for t in ts:
            _card(ctx, h, t.id)
    _history(ctx)


# ---------- boards ----------

def _boards(ctx: Ctx, h: logic.Hierarchy, running: list[logic.Timer]) -> None:
    boards = ctx.boards()
    with st.expander("Boards", icon=":material/dashboard:"):
        st.caption("A board is a set of timers you start together, like Gym or Morning.")
        if boards:
            name = st.pills("Board", list(boards), key="tm_board", label_visibility="collapsed")
            if name:
                st.markdown("\n".join(f"- {_board_line(b)}" for b in boards[name]))
                if st.button(f"Start {name}", type="primary", icon=":material/play_arrow:", key="tm_board_go"):
                    for b in boards[name]:
                        item = h.find(b["Item"]) if b["Item"] else None
                        start_timer(ctx, item, b["Mode"], b["Length"], b["Options"], board=name,
                                    label=b["Label"])
                    st.rerun()
        if running:
            c = st.container(horizontal=True, vertical_alignment="bottom")
            new = c.text_input("Save what's running as a board", placeholder="e.g. Gym", key="tm_board_new")
            if c.button("Save", key="tm_board_save", disabled=not new.strip()):
                _save_board(ctx, h, new.strip(), running)
        st.caption("Change boards on Manage → Boards.")


def _board_line(b: dict) -> str:
    o = logic.timer_options(b["Options"])
    what = {"Countdown": logic.fmt_secs(b["Length"]) if b["Length"] else "Countdown",
            "Interval": f"{o.get('work', 0)}s on / {o.get('rest', 0)}s off × {o.get('rounds', 0) or '∞'}"
            }.get(b["Mode"], b["Mode"])
    return f"**{b['Label']}** · {what}" + (f" · {b['Item']}" if b["Item"] and b["Item"] != b["Label"] else "")


def _save_board(ctx: Ctx, h: logic.Hierarchy, name: str, running: list[logic.Timer]) -> None:
    import pandas as pd
    df = ctx.store.read("Boards")
    df = df[df["Board"].astype(str).str.strip() != name]  # saving over a board replaces it
    rows = pd.DataFrame([{"Board": name, "Label": t.label, "Mode": t.mode, "Length": t.length or "",
                          "Item": h.items[t.item_id].name if t.item_id in h.items else "",
                          "Options": logic.options_text({k: v for k, v in t.options.items() if k != "delay"})}
                         for t in running])
    ctx.store.replace("Boards", pd.concat([df, rows], ignore_index=True))
    st.toast(f"Saved board {name}", icon="💾")
    st.rerun()


# ---------- new timer ----------

def _new(ctx: Ctx, h: logic.Hierarchy, expanded: bool) -> None:
    ss = st.session_state
    if "tm_item_pending" in ss:  # a skill just added below; select it before the selectbox exists
        ss.tm_item = ss.pop("tm_item_pending")
    pool = [it.id for it in sorted(h.items.values(), key=lambda it: it.row) if it.active and it.good]
    with st.expander("New timer or counter", icon=":material/add_alarm:", expanded=expanded):
        row = st.container(horizontal=True, vertical_alignment="bottom")
        iid = row.selectbox("Skill (optional)", pool, index=None, key="tm_item", placeholder="Just a timer",
                            format_func=lambda i: " · ".join(b for b in (h.items[i].name, h.path(i)) if b))
        with row.popover("", icon=":material/add:", help="New skill"):
            new_id = quick_skill_form(ctx, h, "tm_ns")
            if new_id:
                ss.tm_item_pending = new_id
                st.rerun()
        item = h.items.get(iid) if iid else None
        default = "Counter" if item and item.inputs == ["Reps"] else "Stopwatch"
        mode = st.segmented_control("Mode", logic.TIMER_MODES, default=default, key=f"tm_mode_{iid}",
                                    required=True)
        length, opts = 0, {}
        if mode == "Countdown":
            preset = st.pills("Length", list(PRESETS) + ["Custom"], default="1 min", key="tm_preset")
            if preset == "Custom":
                c1, c2 = st.columns(2)
                length = (c1.number_input("Minutes", 0, 600, 3, key="tm_min") * 60
                          + c2.number_input("Seconds", 0, 59, 0, step=5, key="tm_sec"))
            else:
                length = PRESETS.get(preset or "1 min", 60)
            opts["repeat"] = st.toggle("Repeat", key="tm_repeat", help="Starts over at zero, counting rounds")
        elif mode == "Interval":
            c1, c2, c3 = st.columns(3)
            opts["work"] = int(c1.number_input("Work (s)", 1, 3600, 40, step=5, key="tm_work"))
            opts["rest"] = int(c2.number_input("Rest (s)", 0, 3600, 20, step=5, key="tm_rest"))
            opts["rounds"] = int(c3.number_input("Rounds", 1, 100, 8, key="tm_rounds"))
        label = st.text_input("Label (optional)", key="tm_label", placeholder=item.name if item else mode)
        c1, c2 = st.columns(2)
        with c1:
            delay = st.pills("Start", list(DELAYS), default="Now", key="tm_delay")
        with c2:
            color = st.pills("Colour", logic.TIMER_COLORS, key="tm_color",
                             format_func=lambda c: f":{c}[●]")
        if delay and DELAYS.get(delay):
            opts["delay"] = DELAYS[delay]
        if color:
            opts["color"] = color
        st.caption({"Stopwatch": "Counts up. Pause any time; Log records the time.",
                    "Countdown": "Counts down and beeps at zero, then keeps counting overtime. Log records what you did.",
                    "Interval": "Work and rest for a number of rounds, beeping at each change. Log records the work.",
                    "Counter": "Tap to count reps. Log records the count."}[mode])
        if st.button("Start", type="primary", icon=":material/play_arrow:", width="stretch", key="tm_start",
                     disabled=mode == "Countdown" and not length):
            start_timer(ctx, item, mode, length, logic.options_text(opts), label=label.strip())
            for k in ("tm_item", "tm_label"):
                ss.pop(k, None)
            st.rerun()


def quick_skill_form(ctx: Ctx, h: logic.Hierarchy, key: str) -> str | None:
    """Add a skill without leaving what you're doing. Returns the new ID once saved."""
    groups = [g for g in sorted(h.items.values(), key=lambda g: g.row) if g.kind == "Group" and g.active]
    with st.form(key, border=False):
        name = st.text_input("New skill", placeholder="e.g. Archer push-ups")
        under = st.selectbox("Under", [g.name for g in groups], index=None, placeholder="No umbrella")
        inputs = st.pills("You enter", logic.INPUTS, selection_mode="multi", default=["Reps"])
        sets = st.toggle("Log set by set", value=True)
        if st.form_submit_button("Add skill", type="primary"):
            return add_skill(ctx, name, [under] if under else [], inputs, sets)
    return None


# ---------- running timers ----------

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
    counts_reps = t.mode == "Counter" or (item is not None and "Reps" in item.inputs)
    now = time.time()
    color = t.options.get("color")
    name = t.label or (item.name if item else t.mode)

    with st.container(border=True):
        top = st.container(horizontal=True, wrap=False, vertical_alignment="top")
        with top.container(gap=None):
            st.markdown(f":{color}[**{name}**]" if color in logic.TIMER_COLORS else f"**{name}**")
            what = {"Countdown": f"Countdown {logic.fmt_secs(t.length)}" + (" · repeats" if t.options.get("repeat")
                                                                               else ""),
                    "Interval": f"Interval {t.options.get('work', 0)}/{t.options.get('rest', 0)}s"}.get(t.mode, t.mode)
            st.caption(" · ".join(b for b in (what, item.name if item and item.name != name else "",
                                              h.path(item.id) if item else "") if b))
        if top.button("", icon=":material/close:", type="tertiary", key=f"tm_x_{t.id}", help="Discard",
                      width="content"):
            _discard(ctx, t)
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
        rest = item is None and t.board == "Workout" and t.label == "Rest"  # a workout's rest timer logs nothing
        if item is None and not rest:
            pool = [it.id for it in sorted(h.items.values(), key=lambda it: it.row) if it.active and it.good]
            pick = st.selectbox("Log to", pool, index=None, key=f"tm_to_{t.id}", placeholder="Pick a skill to log to",
                                format_func=lambda i: h.items[i].name)
            target = h.items.get(pick) if pick else None

        row = st.container(horizontal=True, wrap=False)
        if t.mode != "Counter":
            if t.running:
                if row.button("", icon=":material/pause:", width="stretch", key=f"tm_p_{t.id}", help="Pause"):
                    _update(ctx, t, Started="", Elapsed=round(max(0, t.seconds(now)), 1), Reps=ss[reps_key])
            elif row.button("", icon=":material/play_arrow:", width="stretch", key=f"tm_r_{t.id}", help="Resume",
                            disabled=t.finished(now)):
                _update(ctx, t, Started=round(now, 1), Reps=ss[reps_key])
        if t.mode == "Countdown" and row.button("+1 min", width="stretch", key=f"tm_add_{t.id}",
                                                help="Add a minute"):
            _update(ctx, t, Length=t.length + 60, Reps=ss[reps_key])
        if row.button("", icon=":material/restart_alt:", width="stretch", key=f"tm_z_{t.id}", help="Reset"):
            ss[reps_key] = 0
            _update(ctx, t, Started=round(now, 1) if t.running else "", Elapsed=0, Reps=0)
        secs, reps = t.logged_secs(now), ss[reps_key] if counts_reps else 0
        if not rest and row.button("Log", type="primary", icon=":material/check:", width="stretch",
                                   key=f"tm_log_{t.id}", disabled=target is None or not (secs or reps)):
            if "Time" not in target.inputs and reps:
                secs = 0  # a reps-only skill keeps the count; the time is just how long the set took
            log_item(ctx, target, "Timer", reps=reps, secs=secs, variant=variant)
            timer_history(ctx, t, "Logged", secs, reps)
            row_n = _fresh_row(ctx, t.id)
            if row_n:
                ctx.store.delete_row("Timers", row_n)
            ss.pop(reps_key, None)
            st.rerun()


def _discard(ctx: Ctx, t: logic.Timer) -> None:
    timer_history(ctx, t, "Discarded", max(0, t.seconds(time.time())), st.session_state.get(f"tm_reps_{t.id}", 0))
    row = _fresh_row(ctx, t.id)
    if row:
        ctx.store.delete_row("Timers", row)


def _update(ctx: Ctx, t: logic.Timer, **values) -> None:
    row = _fresh_row(ctx, t.id)
    if row:
        ctx.store.update_row("Timers", row, values)
    st.rerun()


def _history(ctx: Ctx) -> None:
    try:
        df = ctx.store.read("Timer history")
    except Exception:
        return
    if df.empty:
        return
    with st.expander("History", icon=":material/history:"):
        recent = df.sort_values("_row", ascending=False).head(25)
        recent = recent.assign(When=recent["Timestamp"].astype(str).str[5:16],
                               Time=recent["Seconds"].map(lambda v: logic.fmt_secs(logic.to_int(v, 0))))
        st.dataframe(recent[["When", "Label", "Mode", "Time", "Reps", "Outcome"]].astype(str), hide_index=True,
                     width="stretch")


def strip(ctx: Ctx) -> None:
    """Running timers in one line each, for the top of Today."""
    timers = [t for t in ctx.timers() if t.mode != logic.SESSION_MODE]
    if not timers:
        return
    h_items = {it.id: it for it in ctx.items()}
    with st.container(border=True, gap=None):
        for t in timers:
            row = st.container(horizontal=True, wrap=False, vertical_alignment="center")
            if t.mode == logic.LADDER_MODE:
                from views import ladder
                ladder.strip_line(ctx, t, row)
                continue
            name = t.label or (h_items[t.item_id].name if t.item_id in h_items else t.mode)
            row.markdown(f"**{name}**" + (f" · {st.session_state.get(f'tm_reps_{t.id}', t.reps)} reps"
                                           if t.mode == "Counter" else ""))
            if t.mode != "Counter":
                with row.container(width=150 if t.mode == "Interval" else 90, horizontal_alignment="right"):
                    clock(t, small=True)
        if "timers" in ctx.pages:
            st.page_link(ctx.pages["timers"], label="Open timers", icon=":material/timer:")
