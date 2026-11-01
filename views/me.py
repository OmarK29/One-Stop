"""Me: your character (belt colour follows your level), six stats built from what you log, your pet,
and how you compare with common standards. Nothing here ever goes down because you missed a day."""
from __future__ import annotations

import datetime as dt
import html

import pandas as pd
import streamlit as st

import logic
from views.common import Ctx, dark, refresh_button

STAT_ICON = {"Strength": "💪", "Endurance": "🏃", "Mobility": "🤸", "Skill": "🥋", "Mind": "🧠", "Spirit": "🤲"}
SKIN = {"Light": "#f3d2b3", "Medium light": "#e0b48a", "Medium": "#c68e5f", "Medium dark": "#9a6440",
        "Dark": "#6b4429"}
HAIR = {"Black": "#1f1b18", "Brown": "#5a3a22", "Blonde": "#d9b25f", "Red": "#a8462a", "Grey": "#9a9a9a",
        "None": ""}
PET_COLOR = "#f0a35e"
FACE = "#2b3331"  # eyes and mouths stay dark on skin and fur, whatever the theme


def page(ctx: Ctx) -> None:
    items = ctx.items()
    log = ctx.log()
    frame = logic.log_frame(log, ctx.clock)
    xp = logic.xp_summary(log, ctx.clock, ctx.per_level)
    since = logic.days_since_good_log(log, ctx.clock)

    st.subheader("Me")
    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True):
        _character(ctx, xp)
    with c2, st.container(border=True):
        _pet(ctx, xp.total, since)

    st.markdown("#### Stats")
    st.caption("Each stat is the XP from the logs that feed it, so one workout can raise two. Stats only go up.")
    _stats(logic.stats(items, log, ctx.clock, ctx.settings))

    st.markdown("#### How you compare")
    _compare(ctx, items, frame)
    refresh_button(ctx, "me_refresh")


# ---------- character ----------

def _character(ctx: Ctx, xp: logic.XPSummary) -> None:
    name, color, title, next_at = logic.belt(xp.level)
    skin = SKIN.get(ctx.settings.get("avatar_skin", ""), SKIN["Medium light"])
    hair = HAIR.get(ctx.settings.get("avatar_hair", ""), HAIR["Black"])
    _center(avatar_svg(color, skin, hair, dark()))
    st.markdown(f"<div class='me-name'>Level {xp.level} · {title}</div>"
                f"<div class='me-sub'>{name} belt · {xp.total:,} XP</div>", unsafe_allow_html=True)
    st.progress(xp.into_level / xp.per_level, text=f"{xp.per_level - xp.into_level} XP to level {xp.level + 1}"
                + (f" · next belt at level {next_at}" if next_at else ""))


def avatar_svg(belt: str, skin: str, hair: str, is_dark: bool) -> str:
    """A front-facing figure in a gi. Only the belt changes with level."""
    line = "#d9dedd" if is_dark else "#2b3331"
    gi = "#f7f7f5"
    hair_path = (f"<path d='M56 44 Q56 18 80 18 Q104 18 104 44 Q98 30 80 31 Q62 30 56 44 Z' fill='{hair}'/>"
                 if hair else "")
    belt_line = line if belt in ("#f4f4f2",) else "none"
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 210" width="150" role="img" aria-label="Your character">
  <ellipse cx="80" cy="200" rx="42" ry="6" fill="{line}" opacity=".15"/>
  <rect x="60" y="128" width="18" height="62" rx="8" fill="{gi}" stroke="{line}" stroke-width="2"/>
  <rect x="82" y="128" width="18" height="62" rx="8" fill="{gi}" stroke="{line}" stroke-width="2"/>
  <ellipse cx="68" cy="193" rx="11" ry="5" fill="{skin}" stroke="{line}" stroke-width="1.5"/>
  <ellipse cx="92" cy="193" rx="11" ry="5" fill="{skin}" stroke="{line}" stroke-width="1.5"/>
  <path d="M50 76 L34 118" stroke="{line}" stroke-width="18" stroke-linecap="round"/>
  <path d="M50 76 L34 118" stroke="{gi}" stroke-width="14" stroke-linecap="round"/>
  <path d="M110 76 L126 118" stroke="{line}" stroke-width="18" stroke-linecap="round"/>
  <path d="M110 76 L126 118" stroke="{gi}" stroke-width="14" stroke-linecap="round"/>
  <circle cx="33" cy="124" r="8" fill="{skin}" stroke="{line}" stroke-width="1.5"/>
  <circle cx="127" cy="124" r="8" fill="{skin}" stroke="{line}" stroke-width="1.5"/>
  <path d="M52 70 Q80 62 108 70 L112 136 Q80 142 48 136 Z" fill="{gi}" stroke="{line}" stroke-width="2"
        stroke-linejoin="round"/>
  <path d="M68 68 L84 112 M92 68 L76 112" stroke="{line}" stroke-width="1.6" fill="none"/>
  <rect x="48" y="112" width="64" height="11" rx="2" fill="{belt}" stroke="{belt_line}" stroke-width="1"/>
  <path d="M77 122 L70 140 L75 141 L80 125 Z M83 122 L90 140 L85 141 L80 125 Z" fill="{belt}"
        stroke="{belt_line}" stroke-width="1"/>
  <rect x="75" y="110" width="10" height="15" rx="2" fill="{belt}" stroke="{belt_line}" stroke-width="1"/>
  <rect x="73" y="58" width="14" height="12" fill="{skin}"/>
  <circle cx="80" cy="42" r="24" fill="{skin}" stroke="{line}" stroke-width="2"/>
  {hair_path}
  <circle cx="71" cy="44" r="2.6" fill="{FACE}"/>
  <circle cx="89" cy="44" r="2.6" fill="{FACE}"/>
  <path d="M72 53 Q80 59 88 53" stroke="{FACE}" stroke-width="2" fill="none" stroke-linecap="round"/>
</svg>"""


# ---------- pet ----------

def _pet(ctx: Ctx, total_xp: int, since: int | None) -> None:
    name = str(ctx.settings.get("pet_name") or "Pip").strip() or "Pip"
    pet = logic.pet_state(name, total_xp, since)
    _center(pet_svg(pet, dark()))
    st.markdown(f"<div class='me-name'>{html.escape(pet.name)}</div>"
                f"<div class='me-sub'>{pet.stage} · {pet.mood}</div>", unsafe_allow_html=True)
    if pet.next_at:
        start = logic.PET_STAGES[pet.stage_index][0]
        st.progress((total_xp - start) / (pet.next_at - start),
                    text=f"{pet.next_at - total_xp:,} XP until it's {logic.PET_STAGES[pet.stage_index + 1][1].lower()}")
    st.caption(html.escape(pet.line))


def pet_svg(pet: logic.Pet, is_dark: bool) -> str:
    line = "#d9dedd" if is_dark else "#2b3331"
    if pet.stage == "Egg":
        wobble = "rotate(-6 80 120)" if pet.mood == "Happy" else ""
        return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 210" width="150" role="img" aria-label="Your pet, still an egg">
  <ellipse cx="80" cy="196" rx="38" ry="6" fill="{line}" opacity=".15"/>
  <g transform="{wobble}">
    <path d="M80 70 C112 70 124 130 118 160 C112 188 48 188 42 160 C36 130 48 70 80 70 Z"
          fill="#fbf3e4" stroke="{line}" stroke-width="2"/>
    <circle cx="66" cy="120" r="7" fill="{PET_COLOR}" opacity=".7"/>
    <circle cx="96" cy="140" r="9" fill="{PET_COLOR}" opacity=".7"/>
    <circle cx="80" cy="100" r="5" fill="{PET_COLOR}" opacity=".7"/>
  </g>
</svg>"""
    scale = [0, .62, .78, .92, 1.0][pet.stage_index]
    asleep = pet.mood in ("Sleepy", "Hibernating")
    if pet.mood == "Happy":
        eyes = (f"<path d='M64 112 Q70 104 76 112 M84 112 Q90 104 96 112' stroke='{FACE}' stroke-width='3' "
                f"fill='none' stroke-linecap='round'/>")
        mouth = f"<path d='M72 124 Q80 134 88 124 Z' fill='{FACE}'/>"
    elif pet.mood == "Content":
        eyes = f"<circle cx='70' cy='110' r='4' fill='{FACE}'/><circle cx='90' cy='110' r='4' fill='{FACE}'/>"
        mouth = f"<path d='M74 123 Q80 128 86 123' stroke='{FACE}' stroke-width='2.4' fill='none' stroke-linecap='round'/>"
    else:
        eyes = (f"<path d='M64 112 Q70 117 76 112 M84 112 Q90 117 96 112' stroke='{FACE}' stroke-width='3' "
                f"fill='none' stroke-linecap='round'/>")
        mouth = f"<path d='M76 125 Q80 127 84 125' stroke='{FACE}' stroke-width='2' fill='none' stroke-linecap='round'/>"
    zs = ""
    if asleep:
        n = 3 if pet.mood == "Hibernating" else 1
        zs = "".join(f"<text x='{112 + i * 10}' y='{80 - i * 12}' font-size='{14 + i * 3}' fill='{line}' "
                     f"opacity='.7' font-family='sans-serif'>z</text>" for i in range(n))
    crown = (f"<path d='M70 66 L74 56 L80 64 L86 56 L90 66 Z' fill='#f2c53d' stroke='{line}' stroke-width='1.5'/>"
             if pet.stage == "Elder" else "")
    squash = "translate(80 170) scale(1 .86) translate(-80 -170)" if pet.mood == "Hibernating" else ""
    return f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 210" width="150" role="img" aria-label="Your pet, {pet.stage.lower()}, {pet.mood.lower()}">
  <ellipse cx="80" cy="196" rx="{44 * scale:.0f}" ry="6" fill="{line}" opacity=".15"/>
  <g transform="translate(80 196) scale({scale}) translate(-80 -196)">
    <g transform="{squash}">
      <path d="M48 92 L52 58 L72 80 Z M112 92 L108 58 L88 80 Z" fill="{PET_COLOR}" stroke="{line}"
            stroke-width="2" stroke-linejoin="round"/>
      <path d="M118 170 Q146 160 140 132" stroke="{PET_COLOR}" stroke-width="12" fill="none" stroke-linecap="round"/>
      <ellipse cx="80" cy="140" rx="44" ry="52" fill="{PET_COLOR}" stroke="{line}" stroke-width="2"/>
      <ellipse cx="80" cy="152" rx="26" ry="28" fill="#fff4e6"/>
      <circle cx="60" cy="122" r="5" fill="#f28a8a" opacity=".5"/>
      <circle cx="100" cy="122" r="5" fill="#f28a8a" opacity=".5"/>
      {eyes}{mouth}
      <ellipse cx="62" cy="190" rx="12" ry="6" fill="{PET_COLOR}" stroke="{line}" stroke-width="2"/>
      <ellipse cx="98" cy="190" rx="12" ry="6" fill="{PET_COLOR}" stroke="{line}" stroke-width="2"/>
      {crown}
    </g>
  </g>
  {zs}
</svg>"""


_drawing = st.components.v2.component(
    "one_stop_drawing", css=".d { display: flex; justify-content: center; } .d.row { justify-content: flex-start; }",
    js="""
export default function(component) {
  const { data, parentElement } = component;
  let el = parentElement.querySelector('.d');
  if (!el) { el = document.createElement('div'); parentElement.appendChild(el); }
  el.className = 'd' + (data.row ? ' row' : '');
  el.innerHTML = data.svg;
}
""")


def drawing(svg: str, width: int = 150, key: str = "", row: bool = False) -> None:
    """st.html strips SVG, so drawings (built here, never from typed text) go through a tiny component."""
    _drawing(data={"svg": svg.replace('width="150"', f'width="{width}"'), "row": row}, key=key or None)


def _center(svg: str) -> None:
    drawing(svg)


# ---------- stats ----------

def _stats(stats: list[logic.Stat]) -> None:
    fill = "#4FB39E" if dark() else "#1F5C50"
    track = "rgba(255,255,255,.12)" if dark() else "rgba(0,0,0,.08)"
    rows = []
    for s in stats:
        pct = 100 * s.into / s.span if s.span else 0
        week = f"+{s.week} this week" if s.week else "nothing this week"
        rows.append(f"""
<div class='stat'>
  <div class='stat-top'><span>{STAT_ICON[s.name]} <b>{s.name}</b></span><span class='stat-lv'>Lv {s.level}</span></div>
  <div class='stat-bar' style='background:{track}'><div style='width:{pct:.0f}%;background:{fill}'></div></div>
  <div class='stat-foot'>{s.into}/{s.span} to Lv {s.level + 1} · {week}</div>
</div>""")
    st.html(f"<div class='stat-grid'>{''.join(rows)}</div>" + """
<style>
.stat-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:.9rem 1.4rem; }
.stat-top { display:flex; justify-content:space-between; align-items:baseline; font-size:1rem; }
.stat-lv { font-weight:700; font-size:1.15rem; font-variant-numeric:tabular-nums; }
.stat-bar { height:8px; border-radius:4px; overflow:hidden; margin:.3rem 0 .25rem; }
.stat-bar div { height:100%; border-radius:4px; }
.stat-foot { font-size:.8rem; opacity:.65; }
</style>""")
    with st.expander("What feeds each stat"):
        st.markdown("\n".join(f"- **{s}**: {logic.STAT_BLURB[s]}" for s in logic.STATS))
        st.caption("Change what feeds a stat with a Settings row such as `stat_strength` = `Hypertrophy, Isometrics` "
                   "(item names, umbrella names, domains or tags).")


# ---------- standards ----------

def _compare(ctx: Ctx, items: list[logic.Item], frame) -> None:
    sex = logic.pick(["Male", "Female"], ctx.settings.get("profile_sex"), "")
    age = logic.to_int(ctx.settings.get("profile_age"), 0)
    if not sex or not age:
        st.caption("Add your age and sex in **Edit → Settings → Profile** to compare against the right group. "
                   "Until then, these use the middle of the ranges.")
    t1, t2, t3 = st.tabs(["Strength & holds", "Cardio", "Daily habits"])
    with t1:
        _strength(items, frame, sex, age)
    with t2:
        _cardio(ctx, items, frame)
    with t3:
        _habits(ctx, items, frame)


def _fmt(n: int | None, metric: str) -> str:
    if n is None:
        return "—"
    return logic.fmt_secs(n) if metric == "secs" else str(n)


def _strength(items, frame, sex: str, age: int) -> None:
    rows = []
    for c in logic.compare_standards(items, frame, sex, age):
        nxt = next((cut for cut in c.cuts if c.best is None or c.best < cut), None)
        rows.append({"Exercise": c.name, "Your best": _fmt(c.best, c.metric), "Rating": c.tier or "Not logged yet",
                     "Next level at": _fmt(nxt, c.metric) if nxt is not None else "Top tier",
                     "Good from": _fmt(c.cuts[1], c.metric)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Your best is your biggest single log (one set). Ratings are rough guides from common norms "
               "(ACSM/CSEP push-ups by age and sex; widely used benchmarks for the rest), not test results.")


def _cardio(ctx: Ctx, items, frame) -> None:
    today = ctx.clock.today()
    week0 = ctx.clock.week_start(today)
    week = logic.active_minutes(items, frame, week0, today)
    four = [logic.active_minutes(items, frame, week0 - dt.timedelta(weeks=i), week0 - dt.timedelta(weeks=i) +
                                 dt.timedelta(days=6)) for i in range(1, 5)]
    avg = sum(four) / 4
    st.progress(min(1.0, week / 150), text=f"Active minutes this week: {week} of 150")
    verdict = ("above the guideline's upper range" if avg >= 300 else "meets the guideline" if avg >= 150
               else "under the guideline")
    st.markdown(f"Last 4 weeks: **{avg:.0f} min a week** on average, {verdict}.")
    days = logic.stat_days(items, frame, ctx.settings, "Strength", week0, today)
    st.progress(min(1.0, days / 2), text=f"Strength days this week: {days} of 2")
    st.caption("WHO guideline for adults: 150–300 minutes of moderate activity a week (or 75–150 vigorous), plus "
               "muscle-strengthening on 2 or more days. Active minutes are the time you log on Physical skills. "
               "Run pace needs distance, which the app doesn't record yet.")


def _habits(ctx: Ctx, items, frame) -> None:
    today = ctx.clock.today()
    last7 = [today - dt.timedelta(days=i) for i in range(7)]
    nums = {n.key: n for n in logic.daily_numbers(ctx.settings)}
    rows = []
    if "sleep" in nums:
        v = logic.number_values(frame, "SLEEP")
        got = [v[d] for d in last7 if d in v]
        avg = sum(got) / len(got) if got else None
        rows.append({"Habit": "Sleep", "Your 7-day average": logic.fmt_hm(avg) if avg is not None else "—",
                     "Your goal": logic.fmt_hm(nums["sleep"].goal_min), "Reference": "7–9h (CDC, adults)",
                     "How you're doing": "—" if avg is None else "In range" if 420 <= avg <= 540
                     else "Short" if avg < 420 else "Long"})
    if "screen" in nums:
        v = logic.number_values(frame, "SCREEN")
        got = [v[d] for d in last7 if d in v]
        avg = sum(got) / len(got) if got else None
        rows.append({"Habit": "Screen time (phone)", "Your 7-day average": logic.fmt_hm(avg) if avg is not None else "—",
                     "Your goal": f"under {logic.fmt_hm(nums['screen'].goal_min)}",
                     "Reference": "≈4–5h, typical US adult",
                     "How you're doing": "—" if avg is None else "Under your limit" if avg <= nums["screen"].goal_min
                     else "Over your limit" + (", under typical" if avg < 270 else "")})
    h = logic.build_hierarchy(items)
    water = h.find("Water")
    if water:
        counts = logic.leaf_totals(frame, last7[-1], today)
        per_day = counts[water.id].count / 7 if water.id in counts else 0.0
        rows.append({"Habit": "Water", "Your 7-day average": f"{per_day:.1f} glasses",
                     "Your goal": f"{water.target} glasses" if water.target else "—",
                     "Reference": "≈8 glasses from drinks (NASEM total water 2.7–3.7 L incl. food)",
                     "How you're doing": "On track" if per_day >= 8 else "Below"})
    if not rows:
        st.caption("Turn on sleep or screen time in Edit → Settings to compare them here.")
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Enter sleep and screen time on Today. Screen time comes from your phone's Settings → Screen Time. "
               "The typical-adult figure is a rough average from public surveys.")
