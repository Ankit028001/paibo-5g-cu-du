#!/bin/bash
set -e
BIN=/opt/ns3/ns-3-dev/build/contrib/nr/examples/ns3.48-cu-du-bearer-latency-study-default
LOCALBASE=/root/baseline_bearer_latency
LEVELS="1 25 50 150 200"
SIMTIME=30

mkdir -p "$LOCALBASE"

for N in $LEVELS; do
  LDIR="$LOCALBASE/ue_${N}"
  mkdir -p "$LDIR"
  echo "=== Running ueNum=$N ==="
  cd "$LDIR"
  FULLTRACES=true
  if [ "$N" -eq 200 ]; then
    FULLTRACES=false
  fi
  START=$(date +%s.%N)
  set +e
  LD_LIBRARY_PATH=/opt/ns3/ns-3-dev/build/lib "$BIN" --ueNum=$N --simTime=$SIMTIME --outputDir="$LDIR" --simTag=blat${N} --fullTraces=$FULLTRACES > "$LDIR/stdout.log" 2> "$LDIR/stderr.log"
  RC=$?
  set -e
  END=$(date +%s.%N)
  WALL=$(awk -v s="$START" -v e="$END" 'BEGIN{print e-s}')
  echo "exitCode=$RC wallSecondsOuter=$WALL" > "$LDIR/exit_status.txt"
  echo "LEVEL $N exit=$RC wall=${WALL}s" | tee -a "$LOCALBASE/LADDER_STATUS.txt"
done
echo "=== BASELINE BEARER LATENCY LADDER DONE ==="
