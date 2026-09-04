#!/bin/bash
set -e
BIN=/opt/ns3/ns-3-dev/build/contrib/nr/examples/ns3.48-cu-du-scaling-study-default
LOCALBASE=/root/ns3_cudu_phase
OUTBASE=/mnt/c/Users/Common/Downloads/Siya/ns3_cudu_phase
LEVELS="1 10 25 50 100 150 200"
SIMTIME=30

mkdir -p "$LOCALBASE" "$OUTBASE"

for N in $LEVELS; do
  LDIR="$LOCALBASE/ue_${N}"
  WDIR="$OUTBASE/ue_${N}"
  mkdir -p "$LDIR" "$WDIR"
  echo "=== Running ueNum=$N (local fs: $LDIR) ==="
  cd "$LDIR"
  FULLTRACES=true
  if [ "$N" -eq 200 ]; then
    FULLTRACES=false
  fi
  START=$(date +%s.%N)
  set +e
  LD_LIBRARY_PATH=/opt/ns3/ns-3-dev/build/lib "$BIN" --ueNum=$N --simTime=$SIMTIME --outputDir="$LDIR" --simTag=cudu${N} --fullTraces=$FULLTRACES > "$LDIR/stdout.log" 2> "$LDIR/stderr.log"
  RC=$?
  set -e
  END=$(date +%s.%N)
  WALL=$(awk -v s="$START" -v e="$END" 'BEGIN{print e-s}')
  echo "exitCode=$RC wallSecondsOuter=$WALL" > "$LDIR/exit_status.txt"
  echo "=== ueNum=$N exit=$RC wall=${WALL}s ==="
  if [ $RC -ne 0 ]; then
    echo "LEVEL $N FAILED with exit code $RC" | tee -a "$LOCALBASE/LADDER_STATUS.txt"
    tail -80 "$LDIR/stderr.log"
    cp -r "$LDIR"/* "$WDIR"/
    break
  fi
  echo "LEVEL $N completed exit 0 wall=${WALL}s" | tee -a "$LOCALBASE/LADDER_STATUS.txt"

  echo "Post-processing: CSV + plots for ueNum=$N"
  python3 /root/parse_ns3_kpis.py --run-dir "$LDIR" --traces-dir "$LDIR" --tag cudu${N} >> "$LDIR/postprocess.log" 2>&1 || echo "postprocess FAILED for N=$N" | tee -a "$LOCALBASE/LADDER_STATUS.txt"

  echo "Copying results to Windows-mounted output dir..."
  cp -r "$LDIR"/* "$WDIR"/
done
echo "=== CU-DU LADDER DONE ==="
