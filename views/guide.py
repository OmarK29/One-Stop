"""Guide me: walk the decision tree one question at a time, end on one action."""
from __future__ import annotations

import streamlit as st

import logic
from views import log as log_view
from views.common import DOMAIN_ICON, Ctx, log_checkin, log_item


def _reset() -> None:
    for k in ("g_node", "g_path", "g_offset"):
        st.session_state.pop(k, None)


def page(ctx: Ctx) -> None:
    tree = logic.build_tree(ctx.store.read("Questions"), ctx.store.read("Actions"))
    ss = st.session_state
    if tree.start is None:
        st.info("There are no questions yet. Add some on the Edit page.")
        return
    ss.setdefault("g_node", tree.start)
    ss.setdefault("g_path", [])
    ss.setdefault("g_offset", 0)
    node = ss.g_node

    st.subheader("Guide me")
    if ss.g_path:
        st.caption(" → ".join(choice for _, choice in ss.g_path))

    if node in tree.questions:
        _question(tree.questions[node])
    elif node in tree.actions:
        _action(ctx, tree.actions[node])
    else:
        st.error(f"The tree points to '{node}', which isn't a question or an action. Fix it on the Edit page.")

    if ss.g_path:
        st.write("")
        c1, c2 = st.columns(2)
        if c1.button("Back", icon=":material/arrow_back:", width="stretch", key="g_back"):
            ss.g_node = ss.g_path.pop()[0]
            ss.g_offset = 0
            st.rerun()
        if c2.button("Start over", icon=":material/restart_alt:", width="stretch", key="g_restart"):
            _reset()
            st.rerun()


def _question(q: logic.Question) -> None:
    st.markdown(f"### {q.text}")
    for i, (label, nxt) in enumerate(q.choices):
        if st.button(label, key=f"g_{q.node}_{i}", width="stretch"):
            st.session_state.g_path.append((q.node, label))
            st.session_state.g_node = nxt
            st.session_state.g_offset = 0
            st.rerun()


def _action(ctx: Ctx, action: logic.Action) -> None:
    ss = st.session_state
    items = ctx.items()
    log = ctx.log()
    counts = logic.period_counts(items, log, ctx.clock)
    boosts = logic.counter_boosts(items, counts)
    frame = logic.log_frame(log, ctx.clock)
    today = ctx.clock.today()
    week = {i: t.count for i, t in logic.leaf_totals(frame, ctx.clock.week_start(today), today).items()}
    skip = logic.off_rungs(logic.build_hierarchy(items), frame)
    ranked = logic.recommend(action.picks_from, items, counts, boosts, week_logs=week, skip=skip)
    path = " → ".join(f"{n}: {c}" for n, c in ss.g_path)

    with st.container(border=True):
        st.caption(action.title.upper())
        if not ranked:
            st.markdown(f"### {action.fallback or 'Everything here is done.'}")
            if st.button("Got it", type="primary", width="stretch", key="g_fallback"):
                log_checkin(ctx, path, action.fallback, "Fallback")
                _reset()
                st.rerun()
            return
        pick = ranked[ss.g_offset % len(ranked)]
        st.markdown(f"## {DOMAIN_ICON.get(pick.domain, '')} {pick.name}")
        st.caption(logic.why(pick, counts, boosts))
        if pick.notes:
            st.write(pick.notes)
        if st.button("Did it", type="primary", icon=":material/check:", width="stretch", key="g_did"):
            log_checkin(ctx, path, pick.name, "Did it")
            _reset()
            if pick.measure != "Check" or pick.variants:  # ask for reps/time/variant
                log_view.open_dialog(ctx, pick.name, scope=[pick.id])
                return
            log_item(ctx, pick, "Guide")
            st.rerun()

    c1, c2 = st.columns(2)
    if len(ranked) > 1 and c1.button(f"Another option ({len(ranked) - 1} more)", width="stretch", key="g_another"):
        ss.g_offset += 1
        st.rerun()
    if c2.button("Not now", width="stretch", key="g_skip"):
        log_checkin(ctx, path, pick.name, "Skipped")
        _reset()
        st.rerun()
