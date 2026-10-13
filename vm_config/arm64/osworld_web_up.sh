#!/opt/homebrew/bin/bash
# Build and start the OSWorld-web services needed by osworld-v2.1 tasks on Colima,
# one image at a time to bound memory; overleaf/overleaf-collab are skipped (the
# sharelatex image is amd64-only).
set -u
cd /Users/qiushisun/Git-Repos/OSWorld-web
export HOST_SUFFIX=172.16.120.1.nip.io
mapfile -t ALL < <(docker compose config --services | sort)
NEEDED=()
for s in "${ALL[@]}"; do case "$s" in overleaf*) ;; *) NEEDED+=("$s");; esac; done
echo "services to build/start (${#NEEDED[@]}): ${NEEDED[*]}"
t0=$(date +%s)
for s in "${NEEDED[@]}"; do
  printf '=== %s: ' "$s"
  if docker compose build "$s" > "/tmp/build-$s.log" 2>&1; then echo "ok ($(( $(date +%s) - t0 ))s)"; else echo "FAILED"; grep -iE 'error' "/tmp/build-$s.log" | tail -3; fi
done
echo "build phase elapsed=$(( $(date +%s) - t0 ))s"
docker compose up -d "${NEEDED[@]}" 2>&1 | grep -iE 'error' | tail -5
sleep 30
docker compose ps --format 'table {{.Service}}\t{{.Status}}' | head -45
echo "--- reachability through Caddy"
for h in dinogame mailhub streamview studio.streamview teamchat calendar visaapplication insurance-claim expenseflow formcraft careerlink budgetwise eventix cloudcrm interfacinglinux travelhubpro reviewsphere slidepuzzle glbviewer; do curl -s -m 10 -o /dev/null -w "$h http=%{http_code}\n" "http://$h.$HOST_SUFFIX/"; done
echo OSWORLD_WEB_UP3_DONE
