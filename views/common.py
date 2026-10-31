"""Shared helpers for the pages."""
from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

import logic
from store import Store

DOMAIN_ICON = {"Physical": "💪", "Mental": "🧠", "Spiritual": "🤲"}


@dataclass
class Ctx:
    store: Store
    clock: logic.Clock
    settings: dict
    cloud: bool

    @property
    def per_level(self) -> int:
        return logic.to_int(self.settings.get("xp_per_level"), 250)

    def items(self) -> list[logic.Item]:
        return logic.parse_items(self.store.read("Items"))

    def log(self):
        return self.store.read("Log")


def log_item(ctx: Ctx, item: logic.Item, source: str, note: str = "") -> None:
    ctx.store.append("Log", [ctx.clock.stamp(), ctx.clock.today().isoformat(), item.id, item.name,
                             item.domain, item.kind, item.xp if item.good else 0, source, note])
    if item.good:
        st.toast(f"+{item.xp} XP · {item.name}", icon="✅")
    else:
        st.toast(f"Noted: {item.name}. No XP lost.", icon="📝")


def log_checkin(ctx: Ctx, path: str, recommended: str, outcome: str) -> None:
    ctx.store.append("Checkins", [ctx.clock.stamp(), ctx.clock.today().isoformat(), path, recommended, outcome])


def refresh_button(ctx: Ctx, key: str) -> None:
    if st.button("Refresh from sheet", key=key, icon=":material/refresh:", type="tertiary"):
        ctx.store.refresh()
        st.rerun()
