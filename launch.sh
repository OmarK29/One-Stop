#!/bin/bash
# Starts One Stop on this Mac: finds Python, pulls the latest code from GitHub,
# installs packages when they change, runs the app and opens it in the browser.
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE="$HOME/.one-stop"
PORT=8502
URL="http://localhost:$PORT"
mkdir -p "$STATE"
exec >>"$STATE/launcher.log" 2>&1
echo "--- $(date) ---"

say() { osascript -e "display dialog \"$1\" with title \"One Stop\" buttons {\"OK\"} default button 1" >/dev/null 2>&1 || echo "$1"; }

# Already running? Just open it.
if curl -fs "$URL/_stcore/health" >/dev/null 2>&1; then open "$URL"; exit 0; fi

# Find Python 3.10+ (explicit paths first: apps don't get your Terminal's PATH).
PY=""
for c in /Library/Frameworks/Python.framework/Versions/3.{14,13,12,11,10}/bin/python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3 \
         "$HOME"/anaconda3/bin/python3 "$HOME"/opt/anaconda3/bin/python3 /opt/anaconda3/bin/python3 \
         "$(command -v python3 2>/dev/null)" /usr/bin/python3; do
  [ -x "$c" ] || continue
  if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then say "One Stop needs Python 3.10 or newer. Install it from python.org, then open One Stop again."; open "https://www.python.org/downloads/"; exit 1; fi
echo "python: $PY ($("$PY" --version))"

# Pull the latest code (never prompts; skips quietly if offline or you have local edits).
if [ -d "$APP_DIR/.git" ]; then
  (cd "$APP_DIR" && GIT_TERMINAL_PROMPT=0 git pull --ff-only --quiet) || echo "git pull skipped"
fi

# Private environment; reinstall only when requirements.txt changes or Python changes.
VENV="$STATE/venv"
STAMP="$("$PY" --version) $(shasum "$APP_DIR/requirements.txt" | cut -d' ' -f1)"
if [ ! -x "$VENV/bin/python" ] || [ "$(cat "$STATE/installed" 2>/dev/null)" != "$STAMP" ]; then
  osascript -e 'display notification "Setting up (first launch takes about a minute)…" with title "One Stop"' 2>/dev/null
  rm -rf "$VENV"
  "$PY" -m venv "$VENV" && "$VENV/bin/pip" install -q --upgrade pip && "$VENV/bin/pip" install -q -r "$APP_DIR/requirements.txt" \
    || { say "Couldn't install One Stop's packages. Check your internet connection and try again."; exit 1; }
  echo "$STAMP" > "$STATE/installed"
fi

cd "$APP_DIR"
nohup "$VENV/bin/python" -m streamlit run app.py --server.port $PORT --server.headless true \
  --browser.gatherUsageStats false >>"$STATE/app.log" 2>&1 &

for i in $(seq 1 60); do
  if curl -fs "$URL/_stcore/health" >/dev/null 2>&1; then open "$URL"; exit 0; fi
  sleep 1
done
say "One Stop didn't start. The details are in ~/.one-stop/app.log."
exit 1
