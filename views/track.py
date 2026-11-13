"""Track: everything you log, three ways. **Trackers** are your printed grids, **Goals** is the tree from who
you're becoming down to the skills, **Skills** is the umbrella tree. Each opens on Today; Week, Month and
Year show more. Tap anything to log it. The view, period and tracker live in the link (?v=, ?p=, ?t=)."""
from __future__ import annotations

import datetime as dt
import html

import pandas as pd
import streamlit as st

import logic
from views import log as log_view
from views.common import Ctx, refresh_button

VIEWS = ["Trackers", "Goals", "Skills"]
TILE = 185  # px: two tracker tiles per row on a phone


def page(ctx: Ctx) -> None:
    ss = st.session_state
    head = st.container(horizontal=True, vertical_alignment="center")
    head.subheader("Track")
    if head.button("Log something", icon=":material/add:", type="primary", key="tr_log_any"):
        log_view.open_dialog(ctx, "Log something")

    view = st.segmented_control("View", VIEWS, default="Trackers", required=True, key="v", bind="query-params",
                                label_visibility="collapsed")
    period = st.segmented_control("Period", logic.PERIODS_VIEW, default="Today", required=True, key="p",
                                  bind="query-params", label_visibility="collapsed")
    off_key = f"tr_off_{period}"
    ss.setdefault(off_key, 0)
    start, end, label = logic.period_range(ctx.clock, period, ss[off_key])
    nav = st.container(horizontal=True, wrap=False, vertical_alignment="center")
    if nav.button("", icon=":material/chevron_left:", key="tr_prev", help="Earlier"):
        ss[off_key] -= 1
        st.rerun()
    nav.markdown(f"<div style='text-align:center;flex:1'><b>{html.escape(label)}</b></div>", unsafe_allow_html=True)
    if nav.button("", icon=":material/chevron_right:", key="tr_next", disabled=ss[off_key] >= 0, help="Later"):
        ss[off_key] += 1
        st.rerun()

    h = logic.build_hierarchy(ctx.items())
    frame = logic.log_frame(ctx.log(), ctx.clock)
    if view == "Trackers":
        _trackers(ctx, h, frame, period, start, end)
    else:
        _tree(ctx, h, frame, view, period, start, end)
    _open_pending(ctx, h)
    refresh_button(ctx, "track_refresh")


def _open_pending(ctx: Ctx, h: logic.Hierarchy) -> None:
    """A tap stored by a callback: open the log dialog for it now (dialogs can't open from callbacks)."""
    pending = st.session_state.pop("tr_open", None)
    if not pending:
        return
    title, scope, day = pending
    today = ctx.clock.today()
    if day is not None and day > today:
        st.toast("That day hasn't come yet.")
    elif not [i for i in scope if i in h.items]:
        st.toast("That doesn't map to any item yet. Fix it on Edit → Trackers.")
    else:
        log_view.open_dialog(ctx, title, scope=scope, day=None if day == today else day)


# ---------- trackers ----------

def _trackers(ctx: Ctx, h, frame, period: str, start: dt.date, end: dt.date) -> None:
    trackers = ctx.trackers()
    if not trackers:
        st.info("No trackers yet. Add rows on Edit → Trackers.")
        return
    name = st.pills("Tracker", list(trackers), default=list(trackers)[0], required=True, key="t",
                    bind="query-params", label_visibility="collapsed")
    if name not in trackers:
        name = list(trackers)[0]
    cols = trackers[name]
    if period == "Today":
        _tiles(ctx, h, frame, cols, start)
    elif period == "Week":
        _week(ctx, h, frame, name, cols, start)
    else:
        _progress_table(ctx, h, frame, cols, period, start, end)


def _tiles(ctx: Ctx, h, frame, cols, day: dt.date) -> None:
    """Today as a grid of tiles: each column with today's amount. Tap to log."""
    _, grid = logic.tracker_grid(h, cols, frame, day)
    with st.container(horizontal=True, wrap=True, gap="small"):
        for c in cols:
            amount = logic.fmt_totals(grid.get((day, c.column)), c.show)
            if st.button(f"{c.column}" + (f" · {amount}" if amount else ""), key=f"tile_{c.column}", width=TILE,
                         icon=":material/check_circle:" if amount else ":material/add:",
                         type="secondary"):
                scope = [it.id for t in c.maps_to if (it := h.find(t))]
                st.session_state.tr_open = (f"{c.column} · {day.strftime('%a %b %-d')}", scope, day)
    st.caption("Tap a tile to log. Week shows the full grid.")


def _week(ctx: Ctx, h, frame, name: str, cols, week0: dt.date) -> None:
    ss = st.session_state
    days, grid = logic.tracker_grid(h, cols, frame, week0)
    show = {c.column: c.show for c in cols}
    table = pd.DataFrame(
        [[d.strftime("%a %-m/%-d")] + [logic.fmt_totals(grid.get((d, c.column)), show[c.column]) for c in cols]
         for d in days]
        + [["Weekly total"] + [logic.fmt_totals(grid.get(("week", c.column)), show[c.column]) for c in cols]],
        columns=["Day"] + [c.column for c in cols])
    ss.setdefault("tr_grid", 0)
    grid_key = f"tr_grid_{ss.tr_grid}"
    st.dataframe(table, hide_index=True, key=grid_key, on_select=lambda: _tapped_cell(h, cols, days, grid_key),
                 selection_mode="single-cell", row_height=44,
                 column_config={"Day": st.column_config.TextColumn(pinned=True)})
    st.caption("Tap a cell to log for that day.")
    with st.expander("Print week"):
        blank = st.toggle("Blank sheet to fill in by hand", key="tr_blank")
        _print_view(name, cols, days, grid, show, blank)


def _tapped_cell(h, cols, days, grid_key: str) -> None:
    """Remember the tapped cell, and reset the grid so the same cell can be tapped again."""
    ss = st.session_state
    try:
        cells = ss[grid_key]["selection"]["cells"]
    except (KeyError, TypeError):
        cells = []
    if not cells:
        return
    ss.tr_grid += 1
    row, column = cells[0]
    col = next((c for c in cols if c.column == column), None)
    if col is None or row >= len(days):
        return
    day = days[row]
    ss.tr_open = (f"{col.column} · {day.strftime('%a %b %-d')}", [it.id for t in col.maps_to if (it := h.find(t))],
                  day)


def _progress_table(ctx: Ctx, h, frame, cols, period: str, start: dt.date, end: dt.date) -> None:
    """Month or Year: progress only. Days you did each column, the total, and the shape over time."""
    today = ctx.clock.today()
    so_far = (min(end, today) - start).days + 1
    by = "day" if period == "Month" else "month"
    rows = []
    for c in cols:
        ids = logic.column_leaves(h, c)
        t = logic.leaf_totals(frame[frame["id"].isin(ids)] if not frame.empty else frame, start, end)
        total = logic.Totals()
        for v in t.values():
            total += v
        rows.append({"Column": c.column, "Days": f"{logic.days_active(frame, ids, start, end)}/{so_far}",
                     "Total": logic.fmt_totals(total, c.show) or "—",
                     "Activity": logic.activity(frame, ids, start, end, by)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
        "Column": st.column_config.TextColumn(pinned=True, width="medium"),
        "Days": st.column_config.TextColumn(width="small", help="Days you did it"),
        "Total": st.column_config.TextColumn(width="small"),
        "Activity": st.column_config.BarChartColumn("By day" if by == "day" else "By month", y_min=0,
                                                    width="small")})
    st.caption("Days = days you did it, out of the days so far.")


def _print_view(name: str, cols, days, grid, show, blank: bool) -> None:
    def cell(key, col) -> str:
        return "" if blank else html.escape(logic.fmt_totals(grid.get(key), show[col.column]))

    head = "".join(f"<th>{html.escape(c.column)}</th>" for c in cols)
    body = "".join(f"<tr><th class='d'>{d.strftime('%A, %B %-d, %Y')}</th>"
                   + "".join(f"<td>{cell((d, c.column), c)}</td>" for c in cols) + "</tr>" for d in days)
    body += ("<tr class='t'><th class='d'>Weekly Total:</th>"
             + "".join(f"<td>{cell(('week', c.column), c)}</td>" for c in cols) + "</tr>")
    end = days[-1]
    label = f"{days[0].strftime('%b %-d')} – {end.strftime('%b %-d' if end.month != days[0].month else '%-d')}"
    page_html = f"""
<style>
  body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 0; color: #111; }}
  h2 {{ font-size: 16px; margin: 0 0 8px; }}
  button {{ font: inherit; padding: 6px 14px; border-radius: 8px; border: 1px solid #1F5C50;
           background: #1F5C50; color: #fff; margin-bottom: 10px; cursor: pointer; }}
  table {{ border-collapse: collapse; width: 100%; table-layout: fixed; font-size: 11px; }}
  th, td {{ border: 1px solid #555; padding: 4px; text-align: center; vertical-align: middle; word-wrap: break-word; }}
  th.d {{ text-align: left; width: 16%; font-weight: 600; }}
  td {{ height: 56px; }}
  tr.t td, tr.t th {{ height: 40px; background: #f2f2f2; }}
  @media print {{ button {{ display: none; }} @page {{ size: landscape; margin: 12mm; }} td {{ height: 70px; }} }}
</style>
<button onclick="window.print()">Print</button>
<h2>{html.escape(name)} · {label}</h2>
<table><tr><th class='d'>Dates:</th>{head}</tr>{body}</table>"""
    st.iframe(page_html, height=110 + 60 * 8)


# ---------- trees ----------

def _tree(ctx: Ctx, h, frame, view: str, period: str, start: dt.date, end: dt.date) -> None:
    """Goals: identity → goal → skills. Skills: your umbrellas. Amounts for the period at every level."""
    if view == "Goals":
        roots = [it for it in h.items.values() if it.kind == "Identity" and it.active]
        roots += [it for it in h.items.values() if it.kind == "Goal" and it.active
                  and not any(h.items[p].kind == "Identity" for p in h.parents.get(it.id, []))]
        if not roots:
            st.info("No identities or goals yet. Add them on Edit → Skills (➕ New identity or ➕ New goal).")
            return
    else:
        roots = [it for it in h.skill_roots() if it.active]
    roots.sort(key=lambda it: it.row)
    t = logic.totals(h, frame, start, end)
    today = ctx.clock.today()
    so_far = (min(end, today) - start).days + 1
    can_log = start <= today <= end or period == "Today"
    log_day = start if period == "Today" else today  # Today can be stepped back to yesterday
    for g in roots:
        rows = []
        for depth, iid in _once(h, g.id):
            it = h.items[iid]
            row = {"_id": iid, "Name": " " * depth + it.name + (" ▸" if it.group else ""),
                   "Total": logic.fmt_totals(t.get(iid)) or ""}
            if period != "Today":
                leaves = h.leaves(iid) if it.group else [iid]
                row["Days"] = f"{logic.days_active(frame, leaves, start, end)}/{so_far}"
            rows.append(row)
        table = pd.DataFrame(rows)
        total = logic.fmt_totals(t.get(g.id)) or "nothing yet"
        kind = {"Identity": "🌱 ", "Goal": "🎯 "}.get(g.kind, "")
        with st.expander(f"{kind}{g.name} · {total}", expanded=True):
            key = f"tree_{view}_{g.id}_{st.session_state.get('tr_tree', 0)}"
            config = {"_id": None, "Name": st.column_config.TextColumn(width="medium"),
                      "Total": st.column_config.TextColumn(width="small"),
                      "Days": st.column_config.TextColumn(width="small", help="Days you did it, out of the days so far")}
            st.dataframe(table, hide_index=True, width="stretch", key=key, selection_mode="single-row",
                         on_select=(lambda k=key, tb=table: _tapped_row(h, k, tb, log_day)) if can_log else "ignore",
                         column_config=config, height=36 * (len(table) + 1) + 4)
    st.caption("Tap a row to log to it." if can_log else "Go back to this period to log; past periods are for looking.")


def _once(h, root: str):
    """The tree under `root`, each item once: a skill that sits under the goal and under an umbrella inside it
    shows at the shallower place."""
    nodes = [(0, root)] + [(d + 1, i) for d, i in logic.walk(h, root)]
    depth_of: dict[str, int] = {}
    for d, i in nodes:
        depth_of[i] = min(d, depth_of.get(i, d))
    out, seen, skip_under = [], set(), None
    for d, i in nodes:
        if skip_under is not None and d > skip_under:
            continue  # inside a repeat we skipped
        skip_under = None
        if i in seen or d != depth_of[i]:
            skip_under = d
            continue
        seen.add(i)
        out.append((d, i))
    return out


def _tapped_row(h, key: str, table: pd.DataFrame, day: dt.date) -> None:
    ss = st.session_state
    try:
        picked = ss[key]["selection"]["rows"]
    except (KeyError, TypeError):
        picked = []
    if not picked:
        return
    ss.tr_tree = ss.get("tr_tree", 0) + 1  # new key next run, so the same row can be tapped again
    iid = table["_id"].iloc[picked[0]]
    ss.tr_open = (h.items[iid].name, [iid], day)
