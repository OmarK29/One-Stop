"""Celebration sounds: a small one for each log, a bigger one for finishing a goal, a new best, a workout or
starting a ladder step. Pick the sounds (or Off) and the volume on Manage → Settings → Sounds. Sounds are
made in the browser, so there are no files; the first tap on the page unlocks audio on phones."""
from __future__ import annotations

import streamlit as st

SOUNDS = ["Pop", "Chime", "Bell", "Coins", "Fanfare", "Off"]
BIG = ("goal", "best", "workout", "ladder")  # events that get the big sound

_JS = """
export default function(component) {
  const { data } = component;
  // One shared audio context, unlocked by the first tap (phones only allow sound after a touch).
  if (!window.__osAudioArmed) {
    window.__osAudioArmed = true;
    const unlock = () => {
      try {
        window.__osAudio = window.__osAudio || new (window.AudioContext || window.webkitAudioContext)();
        if (window.__osAudio.state === 'suspended') window.__osAudio.resume();
      } catch (e) {}
    };
    ['pointerdown', 'touchstart', 'keydown'].forEach((ev) => document.addEventListener(ev, unlock, { passive: true }));
  }
  if (!data || !data.sound || data.sound === 'Off') return;
  let ctx;
  try {
    ctx = window.__osAudio || (window.__osAudio = new (window.AudioContext || window.webkitAudioContext)());
    if (ctx.state === 'suspended') ctx.resume();
  } catch (e) { return; }
  const vol = Math.max(0, Math.min(1, (data.volume ?? 60) / 100)) * 0.35;
  const note = (freq, at, dur, type = 'sine', peak = 1, slideTo = null) => {
    const o = ctx.createOscillator(), g = ctx.createGain(), t = ctx.currentTime + at;
    o.type = type; o.frequency.setValueAtTime(freq, t);
    if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol * peak, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(ctx.destination); o.start(t); o.stop(t + dur + 0.02);
  };
  const play = {
    Pop:     () => note(520, 0, 0.12, 'sine', 1, 980),
    Chime:   () => [1047, 1319, 1568].forEach((f, i) => note(f, i * 0.09, 0.5, 'sine', 0.8)),
    Bell:    () => { note(880, 0, 1.4, 'sine', 0.9); note(1760, 0, 0.9, 'sine', 0.35); note(2640, 0, 0.5, 'sine', 0.15); },
    Coins:   () => { note(988, 0, 0.09, 'square', 0.45); note(1319, 0.08, 0.35, 'square', 0.45); },
    Fanfare: () => [[784, 0], [1047, 0.12], [1319, 0.24], [1568, 0.36]].forEach(([f, at], i) =>
               note(f, at, i === 3 ? 0.7 : 0.16, 'triangle', 0.9)),
  };
  (play[data.sound] || play.Pop)();
  if (data.big && data.sound !== 'Fanfare') {  // big moments add a rising flourish to any sound
    [1319, 1568, 2093].forEach((f, i) => note(f, 0.35 + i * 0.08, 0.35, 'sine', 0.6));
  }
}
"""
_player = st.components.v2.component("one_stop_sound", js=_JS)


def queue(kind: str) -> None:
    """Ask for a sound on the next render. A big event wins over a small one queued in the same moment."""
    ss = st.session_state
    current = ss.get("celebrate")
    if current is None or (kind in BIG and current not in BIG):
        ss.celebrate = kind


def play(settings: dict, where: str = "page") -> None:
    """Play what's queued, once. Also arms the tap-to-unlock audio on every page (renders nothing visible)."""
    ss = st.session_state
    kind = ss.pop("celebrate", None)
    n = ss["celebrate_n"] = ss.get("celebrate_n", 0) + (1 if kind else 0)
    big = kind in BIG or kind == "test_big"
    sound = str(settings.get("sound_big" if big else "sound_log") or ("Fanfare" if big else "Pop"))
    if kind is None or sound not in SOUNDS:
        sound = "Off"
    with st.container(height=1, border=False):
        _player(data={"sound": sound, "big": big, "volume": int(float(settings.get("sound_volume") or 60))},
                key=f"snd_{where}_{n}")
