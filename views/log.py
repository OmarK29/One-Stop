"""Log: pick a skill, enter reps and/or time, log it. Its own page, and the dialog Today and Trackers open."""
from __future__ import annotations

import datetime as dt

import streamlit as st

import logic
from views.common import Ctx, log_item

OTHER = "__other__"


def page(ctx: Ctx) -> None:
    st.subheader("Log")
    panel(ctx, key="lp")


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
        st.info("Nothing to log here yet. Add skills under this umbrella on the Edit page.")
        return

    sel = ss.get(f"{key}_sel")
    if sel not in pool:
        sel = None if ss.get(f"{key}_choosing") else _auto_pick(h, roots, pool, frame)
    if sel is None:
        _choose(h, roots, pool, frame, key, in_dialog)
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


def _choose(h: logic.Hierarchy, roots: list[str] | None, pool: list[str], frame, key: str, in_dialog: bool) -> None:
    ss = st.session_state
    in_pool = set(pool)
    quick = [i for i in logic.recent_ids(frame, 30) if i in in_pool][:6]
    if roots is None:  # pinned skills (things with an umbrella or reps/time), not every pinned habit
        quick += [i for i in pool if i not in quick and h.items[i].pinned
                  and (h.parents.get(i) or h.items[i].measure != "Check")][:10 - len(quick)]
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
    if it.notes:
        st.caption(it.notes)

    gid = h.ladder_of(it.id)
    if gid:
        rungs = h.ladder(gid)
        pos = rungs.index(it) + 1
        nxt = f" · next: {rungs[pos].name}" if pos < len(rungs) else " · top rung"
        with st.expander(f"{h.items[gid].name}: rung {pos} of {len(rungs)}{nxt}"):
            st.pills("All progressions", [r.id for r in rungs], key=f"{key}_rung",
                     format_func=lambda i: h.items[i].name, on_change=_select, args=(key, f"{key}_rung"))

    last = logic.last_log(frame, it.id)
    variant = ""
    if it.variants:
        default = last["variant"] if last and last["variant"] in it.variants else None
        variant = st.pills("Variant", it.variants, default=default, key=f"{key}_var_{it.id}") or ""

    reps = secs = 0
    if it.measure in ("Reps", "Both"):
        reps = st.number_input("Reps", 0, 100000, value=None, step=1, placeholder="0", key=f"{key}_reps_{it.id}") or 0
    if it.measure in ("Time", "Both"):
        c1, c2 = st.columns(2)
        mins = c1.number_input("Minutes", 0, 1440, value=None, step=1, placeholder="0", key=f"{key}_min_{it.id}") or 0
        sec = c2.number_input("Seconds", 0, 59, value=None, step=5, placeholder="0", key=f"{key}_sec_{it.id}") or 0
        secs = int(mins) * 60 + int(sec)

    c1, c2 = st.columns(2)
    if c1.button("Log", type="primary", icon=":material/add:", width="stretch", key=f"{key}_log"):
        log_item(ctx, it, "Log", reps=int(reps), secs=secs, variant=variant, day=day)
        _rerun(in_dialog)
    if last and it.measure != "Check":
        again = " · ".join(b for b in (logic.fmt_totals(logic.Totals(1, last["reps"], last["secs"])),
                                       last["variant"]) if b and b != "✓")
        if c2.button(f"Same again{' · ' + again if again else ''}", width="stretch", key=f"{key}_again"):
            log_item(ctx, it, "Log", reps=last["reps"], secs=last["secs"], variant=last["variant"], day=day)
            _rerun(in_dialog)

    c1, c2 = st.columns(2)
    if can_change and c1.button("Change skill", icon=":material/swap_horiz:", type="tertiary", key=f"{key}_change"):
        ss[f"{key}_sel"], ss[f"{key}_choosing"] = None, True
        _rerun(in_dialog)
    if in_dialog and c2.button("Done", icon=":material/check:", type="tertiary", key=f"{key}_done"):
        st.rerun()
