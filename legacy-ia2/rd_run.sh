#!/bin/sh
# usage: sh rd_run.sh <steps.json> <expected-out-file> [max_attempts]
cd "D:/Technique Support/Claude Code Learning/Hot-Fix/【feature01-企业微信自动化办公】" || exit 1
STEPS="$1"
OUT="$2"
MAX="${3:-8}"
rm -f "$OUT"
i=1
while [ "$i" -le "$MAX" ]; do
  echo "=== attempt $i $(date +%H:%M:%S)"
  python wmcp_probe.py chain "$STEPS" 2>&1 | grep -E "STEP|INIT"
  if [ -s "$OUT" ]; then
    echo "GOT $OUT"
    exit 0
  fi
  i=$((i+1))
  sleep 11
done
echo "FAILED all attempts"
exit 1
