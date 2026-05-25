#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${1:-/home/elton/rs-demo/data/experiments/qwen3_mmeb_v2_results/Qwen3-VL-Embedding-2B}"

declare -A TOTALS=(
  [image]=36
  [video]=18
  [visdoc]=24
)

completed_count() {
  local modality="$1"
  local dir="$BASE_DIR/$modality"
  if [[ -d "$dir" ]]; then
    find "$dir" -maxdepth 1 -name '*_score.json' -type f | wc -l
  else
    echo 0
  fi
}

latest_task() {
  local modality="$1"
  local dir="$BASE_DIR/$modality"
  if [[ -d "$dir" ]]; then
    find "$dir" -maxdepth 1 -name '*_score.json' -type f -printf '%T@ %f\n' \
      | sort -n \
      | tail -n 1 \
      | sed -E 's/^[0-9.]+ //; s/_score\.json$//'
  fi
}

echo "Qwen3-VL-Embedding-2B MMEB-V2 progress"
echo "Output: $BASE_DIR"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo

overall_done=0
overall_total=0
for modality in image video visdoc; do
  done_count="$(completed_count "$modality" | tr -d ' ')"
  total_count="${TOTALS[$modality]}"
  latest="$(latest_task "$modality" || true)"
  overall_done=$((overall_done + done_count))
  overall_total=$((overall_total + total_count))

  printf '%-6s %2d/%-2d' "$modality:" "$done_count" "$total_count"
  if [[ -n "${latest:-}" ]]; then
    printf ' latest=%s' "$latest"
  fi
  echo
done

echo
printf 'overall %2d/%-2d (%d%%)\n' "$overall_done" "$overall_total" $((overall_done * 100 / overall_total))

echo
echo "Recent score files:"
find "$BASE_DIR" -path '*_score.json' -type f -printf '%TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null \
  | sort \
  | tail -n 8 \
  | sed "s# $BASE_DIR/# #"

echo
echo "Qwen eval workers:"
pgrep -af 'src.evaluation.mmeb_v2.eval_embedding' || echo "No active eval workers found"

echo
echo "GPU memory:"
nvidia-smi --query-compute-apps=pid,gpu_name,used_memory --format=csv,noheader 2>/dev/null \
  || echo "nvidia-smi unavailable"
