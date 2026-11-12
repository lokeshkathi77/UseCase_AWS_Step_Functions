#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv
source .venv/bin/activate
pip install --quiet -r preprocessing/requirements.txt

rm -rf test_output
mkdir -p test_output/processed test_output/errors test_output/output

python preprocessing/preprocess.py \
  --input test_data/transactions_test.csv \
  --output test_output/processed/transactions_cleaned.csv \
  --rejected test_output/errors/rejected_transactions.csv

python ecs_processor/processor.py \
  --input test_output/processed/transactions_cleaned.csv \
  --output test_output/output/transaction_summary.json

printf '\nGenerated files:\n'
find test_output -type f -print
printf '\nSummary:\n'
cat test_output/output/transaction_summary.json
