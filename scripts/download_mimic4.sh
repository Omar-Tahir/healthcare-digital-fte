#!/usr/bin/env bash
# Download MIMIC-IV tables needed for the accuracy benchmark.
#
# Prerequisites:
#   1. PhysioNet account with credentialed researcher status
#      https://physionet.org/register/
#   2. Complete CITI training and sign the MIMIC-IV DUA
#      https://physionet.org/content/mimiciv/2.2/
#   3. wget installed (sudo apt install wget)
#
# Usage:
#   bash scripts/download_mimic4.sh <physionet_username>
#
# What this downloads (~300 MB total):
#   data/mimic/raw/diagnoses_icd.csv  (~17 MB) — ICD codes per admission
#   data/mimic/raw/discharge.csv      (~280 MB) — discharge summaries
#
# The data directory is gitignored. Never commit MIMIC data.
#
# Spec: specs/07-mimic-benchmark.md
# ADR:  docs/adr/ADR-013-mimic-benchmark-design.md

set -euo pipefail

PHYSIONET_USER="${1:-}"
if [[ -z "$PHYSIONET_USER" ]]; then
    echo "Usage: bash scripts/download_mimic4.sh <physionet_username>"
    exit 1
fi

MIMIC_IV_BASE="https://physionet.org/files/mimiciv/2.2"
MIMIC_NOTE_BASE="https://physionet.org/files/mimic-iv-note/2.2"
DATA_DIR="data/mimic/raw"

mkdir -p "$DATA_DIR"

echo "=== MIMIC-IV Download ==="
echo "User: $PHYSIONET_USER"
echo "Target: $DATA_DIR"
echo ""
echo "You will be prompted for your PhysioNet password."
echo ""

# diagnoses_icd.csv — ICD codes per admission (hosp module)
echo "[1/2] Downloading diagnoses_icd.csv..."
wget \
    --user="$PHYSIONET_USER" \
    --ask-password \
    -O "$DATA_DIR/diagnoses_icd.csv" \
    "$MIMIC_IV_BASE/hosp/diagnoses_icd.csv.gz" && \
    gunzip -f "$DATA_DIR/diagnoses_icd.csv.gz" 2>/dev/null || \
wget \
    --user="$PHYSIONET_USER" \
    --ask-password \
    -O "$DATA_DIR/diagnoses_icd.csv" \
    "$MIMIC_IV_BASE/hosp/diagnoses_icd.csv"

# discharge.csv — discharge summaries (MIMIC-IV-Note module)
echo "[2/2] Downloading discharge.csv..."
wget \
    --user="$PHYSIONET_USER" \
    --ask-password \
    -O "$DATA_DIR/discharge.csv.gz" \
    "$MIMIC_NOTE_BASE/note/discharge.csv.gz" && \
    gunzip -f "$DATA_DIR/discharge.csv.gz" || \
wget \
    --user="$PHYSIONET_USER" \
    --ask-password \
    -O "$DATA_DIR/discharge.csv" \
    "$MIMIC_NOTE_BASE/note/discharge.csv"

echo ""
echo "=== Download Complete ==="
echo ""
echo "Files:"
ls -lh "$DATA_DIR/"
echo ""
echo "Next steps:"
echo "  # Run benchmark (100 admissions, ~\$1.50 in LLM cost):"
echo "  uv run python -m src.benchmarks.mimic_benchmark --sample 100"
echo ""
echo "  # Run MIMIC accuracy tests:"
echo "  uv run pytest tests/clinical/test_coding_accuracy_mimic.py -m mimic -v"
echo ""
echo "IMPORTANT: data/mimic/ is gitignored. Never commit MIMIC data."
