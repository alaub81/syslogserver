#!/usr/bin/env bash
# Scan each image once; derive both the SARIF report and gate from that JSON.
set -euo pipefail
if (( $# < 2 )); then
  echo "Usage: scan-images.sh REPORT_DIRECTORY NAME=IMAGE|archive:/path/image.tar [...]" >&2
  exit 2
fi
REPORT_DIR=$1
shift
mkdir -p -- "$REPORT_DIR"
status=0
for specification in "$@"; do
  name=${specification%%=*}
  image=${specification#*=}
  if [[ ! "$name" =~ ^[a-z0-9-]+$ || "$image" == "$specification" || -z "$image" ]]; then
    echo "Invalid image specification: $specification" >&2
    exit 2
  fi
  target=("$image")
  if [[ "$image" == archive:* ]]; then
    target=(--input "${image#archive:}")
  fi
  if ! trivy image --scanners vuln --ignore-unfixed --severity MEDIUM,HIGH,CRITICAL \
    --timeout 10m --format json --output "$REPORT_DIR/$name.json" "${target[@]}"; then
    status=1
    continue
  fi
  if ! trivy convert --ignorefile .trivyignore.yaml --format sarif --severity MEDIUM,HIGH,CRITICAL \
    --output "$REPORT_DIR/$name.sarif" "$REPORT_DIR/$name.json"; then
    status=1
  else
    # Code scanning needs a distinct analysis category for every image and arch.
    jq --arg category "$name-${SCAN_CATEGORY:-default}/" \
      '.runs[].automationDetails.id = $category' "$REPORT_DIR/$name.sarif" > "$REPORT_DIR/$name.sarif.tmp"
    mv -- "$REPORT_DIR/$name.sarif.tmp" "$REPORT_DIR/$name.sarif"
  fi
  if ! trivy convert --ignorefile .trivyignore.yaml --scanners vuln --format table \
    --severity HIGH,CRITICAL --exit-code 1 "$REPORT_DIR/$name.json"; then
    status=1
  fi
done
exit "$status"
