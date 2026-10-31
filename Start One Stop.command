#!/bin/bash
# Same as double-clicking One Stop.app, but shows a Terminal window (handy if something goes wrong).
"$(cd "$(dirname "$0")" && pwd)/launch.sh"
tail -n 30 "$HOME/.one-stop/launcher.log"
