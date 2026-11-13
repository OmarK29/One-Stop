"""Import and export: your log as a simple CSV, and a template so any AI assistant can turn what you say
("3 sets of 12 push-ups, plank 90 seconds") into rows you paste here."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

import logic
from views.common import Ctx, add_skill, add_variant

EXPORT_RANGES = ["This month", "Last 30 days", "This year", "Everything"]


def section(ctx: Ctx) -> None:
    items = ctx.items()
    today = ctx.clock.today()
    st.markdown("#### Log by voice with any AI")
    st.caption("1. Copy the template into ChatGPT, Claude or any assistant (once per chat). 2. Tell it what you did, "
               "by voice or typing. 3. Paste its reply below, check the preview, and import.")
    with st.expander("Template for your AI", icon=":material/content_copy:"):
        st.code(logic.ai_template(items, today), language=None)
        st.caption("It lists your items, their inputs and variants, so names come back spelled the way the app "
                   "knows them. Copy it again after adding skills.")
    _import(ctx, items, today)
    _export(ctx, today)


def _import(ctx: Ctx, items: list[logic.Item], today: dt.date) -> None:
    ss = st.session_state
    st.markdown("#### Import")
    text = st.text_area("Paste CSV rows", height=170, key=f"io_text_{ss.get('io_n', 0)}",
                        placeholder=",".join(logic.CSV_COLUMNS) + f"\n{today.isoformat()},07:10,Push-ups,,1,15,,,,,")
    up = st.file_uploader("…or upload a CSV file", type=["csv", "txt"], key=f"io_file_{ss.get('io_n', 0)}")
    if up is not None:
        text = up.getvalue().decode("utf-8", "replace")
    if not text.strip():
        return
    rows = logic.parse_import(text, items, today)
    seen = _existing(ctx)
    preview = []
    for r in rows:
        dup = r.item is not None and r.day is not None and _key(r) in seen
        status = r.problem or ("Already in your log; skipped" if dup else
                               f"Adds variant {r.variant}" if r.new_variant else "OK")
        preview.append({"Row": r.line, "Date": r.day.isoformat() if r.day else "", "Item": r.item.name if r.item
                        else r.raw_item, "Variant": r.variant, "Set": str(r.set_no or ""), "What": logic.fmt_set(
                            {"reps": r.reps, "secs": r.secs, "weight": r.weight, "dist": r.dist, "effort": r.effort}),
                        "Status": status})
    st.dataframe(pd.DataFrame(preview), hide_index=True, width="stretch")
    unknown = sorted({r.raw_item for r in rows if r.item is None and r.raw_item})
    create = bool(unknown) and st.toggle(f"Add {len(unknown)} new skill{'s' * (len(unknown) != 1)}: "
                                         + ", ".join(unknown), key="io_create",
                                         help="Each gets the inputs its rows use; file it under an umbrella later "
                                              "on Manage → Skills")
    ready = [r for r in rows if (r.item or (create and r.raw_item)) and r.day and not r.problem.startswith("Can't")
             and not (r.item and _key(r) in seen)]
    if not st.button(f"Import {len(ready)} row{'s' * (len(ready) != 1)}", type="primary", key="io_go",
                     disabled=not ready, icon=":material/upload:"):
        return
    if create:
        for name in unknown:
            used = [r for r in rows if r.raw_item == name]
            inputs = [i for i, f in (("Reps", "reps"), ("Time", "secs"), ("Weight", "weight"), ("Distance", "dist"),
                                     ("Effort", "effort")) if any(getattr(r, f) for r in used)]
            add_skill(ctx, name, [], inputs, any(r.set_no for r in used),
                      sorted({r.variant for r in used if r.variant}))
        items = ctx.items()
        rows = logic.parse_import(text, items, today)
        ready = [r for r in rows if r.item and r.day and not r.problem and _key(r) not in seen]
    for r in ready:
        if r.new_variant:
            add_variant(ctx, r.item, r.variant)
    ctx.store.append_dicts("Log", [{
        "Timestamp": f"{r.day.isoformat()} {r.time or '12:00'}:00"[:19], "Day": r.day.isoformat(), "Item ID": r.item.id,
        "Item": r.item.name, "Domain": r.item.domain, "Kind": r.item.kind,
        "XP": r.item.xp if r.set_no <= 1 else 0, "Source": "Import", "Note": r.note, "Reps": r.reps or "",
        "Seconds": r.secs or "", "Variant": r.variant, "Weight": r.weight or "", "Distance": r.dist or "",
        "Effort": r.effort or "", "Set": r.set_no or "", "Session": ""} for r in ready])
    st.toast(f"Imported {len(ready)} row{'s' * (len(ready) != 1)}", icon="✅")
    ss.io_n = ss.get("io_n", 0) + 1  # fresh, empty box
    st.rerun()


def _key(r: logic.ImportRow) -> tuple:
    return (r.day.isoformat(), r.item.id, r.reps, r.secs, round(r.weight, 2), round(r.dist, 2), r.set_no)


def _existing(ctx: Ctx) -> set[tuple]:
    """What's already logged, so pasting the same rows twice doesn't double them."""
    f = logic.log_frame(ctx.log(), ctx.clock)
    log = ctx.log()
    sets = dict(zip(log["_row"], log["Set"])) if "Set" in log else {}
    return {(r.day.isoformat(), r.id, r.reps, r.secs, round(r.weight, 2), round(r.dist, 2),
             logic.to_int(sets.get(r.row), 0)) for r in f.itertuples()}


def _export(ctx: Ctx, today: dt.date) -> None:
    st.markdown("#### Export")
    which = st.pills("Range", EXPORT_RANGES, default="This month", key="io_range", required=True)
    start = {"This month": today.replace(day=1), "Last 30 days": today - dt.timedelta(days=29),
             "This year": today.replace(month=1, day=1)}.get(which)
    df = logic.export_rows(ctx.log(), ctx.clock, start, today if start else None)
    st.caption(f"{len(df)} rows, in the same format the import reads.")
    st.download_button("Download CSV", df.to_csv(index=False), file_name=f"one-stop-{which.lower().replace(' ', '-')}"
                       f"-{today.isoformat()}.csv", mime="text/csv", icon=":material/download:", key="io_dl",
                       disabled=df.empty)
    if not df.empty:
        st.dataframe(df.tail(8).astype(str), hide_index=True, width="stretch")
