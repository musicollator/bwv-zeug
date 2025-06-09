#!/bin/bash

MSG="${1:-Rebuilt all}"

if git status --short | grep . > /dev/null; then
  git add . && git commit -m "$MSG" && git push
  exit $?  # preserve the status of the last command
else
  echo "No changes to commit"
  exit 0   # explicitly succeed
fi
