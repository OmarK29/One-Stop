"""Trackers: your printed weekly grids. Days down the side, your columns across, a weekly total at the bottom.
Tap a cell to log to that column for that day."""
from __future__ import annotations

import datetime as dt
import html

import pandas as pd
import streamlit as st

import logic
from views import log as log_view
from views.common import Ctx, refresh_button

TOTAL = "Weekly total"


def page(ctx: Ctx) -> None:
    ss = st.session_state
    trackers = ctx.trackers()
    st.subheader("Trackers")
    if not trackers:
        st.info("No trackers yet. Add rows on Edit → Trackers.")
        return
    name = st.selectbox("Tracker", list(trackers), key="t", bind="query-params", label_visibility="collapsed")
    cols = trackers[name]

    today = ctx.clock.today()
    ss.setdefault("tr_week", 0)
    week0 = ctx.clock.week_start(today) + dt.timedelta(weeks=ss.tr_week)
    c1, c2, c3 = st.columns([1, 3, 1], vertical_alignment="center")
    if c1.button("", icon=":material/chevron_left:", key="tr_prev", help="Previous week"):
        ss.tr_week -= 1
        st.rerun()
    c2.markdown(f"<div style='text-align:center'><b>{_week_label(week0)}</b></div>", unsafe_allow_html=True)
    if c3.button("", icon=":material/chevron_right:", key="tr_next", disabled=ss.tr_week >= 0, help="Next week"):
        ss.tr_week += 1
        st.rerun()

    h = logic.build_hierarchy(ctx.items())
    frame = logic.log_frame(ctx.log(), ctx.clock)
    days, grid = logic.tracker_grid(h, cols, frame, week0)
    show = {c.column: c.show for c in cols}
    table = pd.DataFrame(
        [[d.strftime("%a %-m/%-d")] + [logic.fmt_totals(grid.get((d, c.column)), show[c.column]) for c in cols]
         for d in days]
        + [[TOTAL] + [logic.fmt_totals(grid.get(("week", c.column)), show[c.column]) for c in cols]],
        columns=["Day"] + [c.column for c in cols])

    ss.setdefault("tr_grid", 0)
    grid_key = f"tr_grid_{ss.tr_grid}"
    st.dataframe(table, hide_index=True, key=grid_key, on_select=lambda: _tapped(grid_key),
                 selection_mode="single-cell", row_height=44,
                 column_config={"Day": st.column_config.TextColumn(pinned=True)})
    st.caption("Tap a cell to log for that day.")

    pending = ss.pop("tr_open", None)
    if pending:
        row, column = pending
        col = next((c for c in cols if c.column == column), None)
        day = days[row] if row < len(days) else (today if week0 <= today <= days[-1] else None)
        if col is None:
            pass
        elif day is None:
            st.toast("Pick a day to log for a past week.")
        elif day > today:
            st.toast("That day hasn't come yet.")
        else:
            scope = [it.id for t in col.maps_to if (it := h.find(t))]
            if not scope:
                st.toast(f"'{col.column}' doesn't map to any item yet. Fix it on Edit → Trackers.")
            else:
                log_view.open_dialog(ctx, f"{col.column} · {day.strftime('%a %b %-d')}", scope=scope, day=day)

    with st.expander("Print week"):
        blank = st.toggle("Blank sheet to fill in by hand", key="tr_blank")
        _print_view(name, cols, days, grid, show, blank)
    refresh_button(ctx, "trackers_refresh")


def _tapped(grid_key: str) -> None:
    """Remember the tapped cell and reset the grid so the same cell can be tapped again."""
    ss = st.session_state
    try:
        cells = ss[grid_key]["selection"]["cells"]
    except (KeyError, TypeError):
        cells = []
    if cells:
        ss.tr_open = tuple(cells[0])
        ss.tr_grid += 1


def _week_label(week0: dt.date) -> str:
    end = week0 + dt.timedelta(days=6)
    return f"{week0.strftime('%b %-d')} – {end.strftime('%b %-d' if end.month != week0.month else '%-d')}"


def _print_view(name: str, cols, days, grid, show, blank: bool) -> None:
    def cell(key, col) -> str:
        return "" if blank else html.escape(logic.fmt_totals(grid.get(key), show[col.column]))

    head = "".join(f"<th>{html.escape(c.column)}</th>" for c in cols)
    body = "".join(f"<tr><th class='d'>{d.strftime('%A, %B %-d, %Y')}</th>"
                   + "".join(f"<td>{cell((d, c.column), c)}</td>" for c in cols) + "</tr>" for d in days)
    body += ("<tr class='t'><th class='d'>Weekly Total:</th>"
             + "".join(f"<td>{cell(('week', c.column), c)}</td>" for c in cols) + "</tr>")
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
<h2>{html.escape(name)} · {_week_label(days[0])}</h2>
<table><tr><th class='d'>Dates:</th>{head}</tr>{body}</table>"""
    st.iframe(page_html, height=110 + 60 * 8)
