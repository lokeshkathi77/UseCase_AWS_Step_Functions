#!/usr/bin/env python3
"""Create a transaction summary from a cleaned CSV stored locally or in S3."""

import argparse
import csv
import io
import json
import os
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, TextIO

import boto3
from botocore.exceptions import BotoCoreError, ClientError

REQUIRED_COLUMNS = ("tid", "amount", "status", "date")


def read_input(uri: str) -> TextIO:
    if uri.startswith("s3://"):
        bucket, key = uri[5:].split("/", 1)
        body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
        return io.StringIO(body.decode("utf-8-sig"))
    return Path(uri).open("r", encoding="utf-8-sig", newline="")


def write_output(uri: str, result: Dict[str, object]) -> None:
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if uri.startswith("s3://"):
        bucket, key = uri[5:].split("/", 1)
        boto3.client("s3").put_object(
            Bucket=bucket,
            Key=key,
            Body=payload.encode("utf-8"),
            ContentType="application/json",
        )
        return
    path = Path(uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def summarize(input_uri: str) -> Dict[str, object]:
    status_counts = Counter()
    total_amount = Decimal("0")
    total = 0
    dates = []

    with read_input(input_uri) as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None or not set(REQUIRED_COLUMNS).issubset(reader.fieldnames):
            raise ValueError(f"CSV must contain columns: {', '.join(REQUIRED_COLUMNS)}")
        for row in reader:
            try:
                amount = Decimal(row["amount"])
                parsed_date = datetime.fromisoformat(row["date"].replace("Z", "+00:00"))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValueError(f"invalid cleaned row for tid={row.get('tid', '')}") from exc
            total += 1
            total_amount += amount
            status_counts[row["status"].strip().upper()] += 1
            dates.append(parsed_date)

    return {
        "total_transactions": total,
        "total_amount": float(total_amount),
        "status_counts": dict(sorted(status_counts.items())),
        "first_transaction_date": min(dates).isoformat().replace("+00:00", "Z") if dates else None,
        "last_transaction_date": max(dates).isoformat().replace("+00:00", "Z") if dates else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=os.getenv("INPUT_URI"), required=os.getenv("INPUT_URI") is None)
    parser.add_argument("--output", default=os.getenv("OUTPUT_URI", "output/transaction_summary.json"))
    args = parser.parse_args()

    try:
        result = summarize(args.input)
        write_output(args.output, result)
    except (OSError, ValueError, BotoCoreError, ClientError) as exc:
        print(f"ECS processing failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
