# UseCase AWS Step Functions

First version for processing transaction CSV files with four columns:

```text
tid,amount,status,date
```

## Flow

1. Run `preprocessing/preprocess.py` on EC2 to validate, normalize, deduplicate, and split valid/rejected records.
2. Store the cleaned CSV in S3.
3. Run the ECS container from `ecs_processor/` with the cleaned CSV as input.
4. Store the JSON summary in S3.

## Preprocessing on EC2

```bash
python preprocessing/preprocess.py \\
  --input input/transactions.csv \\
  --output processed/transactions_cleaned.csv \\
  --rejected errors/rejected_transactions.csv
```

Optional environment variables are available: `INPUT_CSV`, `OUTPUT_CSV`, `REJECTED_CSV`, and `ALLOWED_STATUSES`.

## Run the ECS processor locally

```bash
python ecs_processor/processor.py \\
  --input processed/transactions_cleaned.csv \\
  --output output/transaction_summary.json
```

For AWS, use S3 URIs such as `s3://bucket/processed/transactions_cleaned.csv` and `s3://bucket/output/transaction_summary.json`. The ECS task role needs `s3:GetObject` and `s3:PutObject` permissions for the configured prefixes.

The implementation is parameter-driven; bucket names, keys, paths, and allowed statuses are supplied at runtime rather than hardcoded.
