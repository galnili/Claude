#!/bin/bash
cd /tmp/claude-0/-home-user-Claude/f12d1f33-7b52-536c-b8e3-fa63bafcb91a/scratchpad
for s in hero detail dance longtable side overview; do
  ./bl/bin/python viz/render_shot.py viz/hall.blend $s viz/out/$s.png 1920 1080 112 2>&1 | grep -E "RENDER|rror"
  ./bl/bin/python viz/bloom.py viz/out/$s.png /home/user/Claude/event-hall-3d/renders/palace-$s.jpg && echo "done $s $(date +%T)"
done
