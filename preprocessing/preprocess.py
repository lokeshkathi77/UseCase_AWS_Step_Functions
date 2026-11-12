#!/usr/bin/env python3
"""Validate and clean transaction CSV files for the ECS processing step."""

import argparse
import csv
import io
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, TextIO, Tuple

try:
    import boto3
except ImportError:  # Allows local validation without AWS dependencies.
    boto3 = None

REQUIRED_COLUMNS = ("tid", "amount", "status", "date")
DEFAULT_STATUSES = frozenset(("SUCCESS", "FAILED", "PENDING"))


def open_input(uri: str) -> Tuple[TextIO, bool]:
    if uri.startswith("s3://"):
        if boto3 is None:
            raise RuntimeError("boto3 is required for S3 input")
        bucket, key = uri[5:].split("/", 1)
        body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
        return io.StringIO(body.decode("utf-8-sig")), True
    return Path(uri).open("r", encoding="utf-8-sig", newline=""), True


def open_output(uri: str) -> TextIO:
    if uri.startswith("s3://"):
        raise ValueError("Use a local output path for preprocessing; upload it separately or use --output-bucket/--output-key")
    path = Path(uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("w", encoding="utf-8", newline="")


def parse_date(value: str) -> str:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_row(row: Dict[str, str], allowed_statuses: Iterable[str]) -> Dict[str, str]:
    if any(not row.get(column, "").strip() for column in REQUIRED_COLUMNS):
        raise ValueError("missing required value")

    tid = row["tid"].strip()
    status = row["status"].strip().upper()
    if status not in allowed_statuses:
        raise ValueError(f"unsupported status: {status}")

    try:
        amount = Decimal(row["amount"].strip())
    except InvalidOperation as exc:
        raise ValueError("amount must be numeric") from exc
    if amount < 0:
        raise ValueError("amount cannot be negative")

    return {
        "tid": tid,
        "amount": format(amount, "f"),
        "status": status,
        "date": parse_date(row["date"]),
    }


def preprocess(input_uri: str, output_path: str, rejected_path: str, allowed_statuses: Iterable[str]) -> Tuple[int, int]:
    seen = set()
    valid_count = rejected_count = 0
    with open_input(input_uri)[0] as source, open_output(output_path) as valid_file, open_output(rejected_path) as rejected_file:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or not set(REQUIRED_COLUMNS).issubset(reader.fieldnames):
            raise ValueError(f"CSV must contain columns: {', '.join(REQUIRED_COLUMNS)}")

        valid_writer = csv.DictWriter(valid_file, fieldnames=REQUIRED_COLUMNS)
        rejected_writer = csv.DictWriter(rejected_file, fieldnames=(*REQUIRED_COLUMNS, "error"))
        valid_writer.writeheader()
        rejected_writer.writeheader()

        for row in reader:
            try:
                cleaned = validate_row(row, allowed_statuses)
                if cleaned["tid"] in seen:
                    raise ValueError("duplicate tid")
                seen.add(cleaned["tid"])
                valid_writer.writerow(cleaned)
                valid_count += 1
            except (ValueError, TypeError) as exc:
                rejected_writer.writerow({column: row.get(column, "") for column in REQUIRED_COLUMNS} | {"error": str(exc)})
                rejected_count += 1

    return valid_count, rejected_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=os.getenv("INPUT_CSV", "input/transactions.csv"))
    parser.add_argument("--output", default=os.getenv("OUTPUT_CSV", "processed/transactions_cleaned.csv"))
    parser.add_argument("--rejected", default=os.getenv("REJECTED_CSV", "errors/rejected_transactions.csv"))
    parser.add_argument("--allowed-statuses", default=os.getenv("ALLOWED_STATUSES", ",".join(sorted(DEFAULT_STATUSES))))
    args = parser.parse_args()

    try:
        valid, rejected = preprocess(args.input, args.output, args.rejected, {s.strip().upper() for s in args.allowed_statuses.split(",") if s.strip()})
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Preprocessing failed: {exc}", file=sys.stderr)
        return 1
    print(f"Preprocessing complete: valid={valid}, rejected={rejected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
