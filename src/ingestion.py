"""Data ingestion and Q1 bounds-validation utilities for student analytics."""

import csv
import logging
import math
from pathlib import Path

DEFAULT_RAW_DATA_PATH = Path("data/raw/student_performance_dataset.csv")

EXPECTED_COLUMNS = (
    "Student_ID",
    "Gender",
    "Study_Hours_per_Week",
    "Attendance_Rate",
    "Past_Exam_Scores",
    "Parental_Education_Level",
    "Internet_Access_at_Home",
    "Extracurricular_Activities",
    "Final_Exam_Score",
    "Pass_Fail",
)

NUMERIC_BOUNDS = {
    "Study_Hours_per_Week": (0.0, 60.0),
    "Attendance_Rate": (0.0, 100.0),
    "Past_Exam_Scores": (0.0, 100.0),
    "Final_Exam_Score": (0.0, 100.0),
}

logger = logging.getLogger(__name__)


def validate_record(record: dict[str, str]) -> dict:
    """Validate Student_ID and numeric bounds for a single CSV row."""
    cleaned = {col: value.strip() for col, value in record.items()}
    if not cleaned.get("Student_ID"):
        raise ValueError("Student_ID is missing or empty")

    for col, (low, high) in NUMERIC_BOUNDS.items():
        val = float(cleaned[col])
        if not math.isfinite(val):
            raise ValueError(f"{col} has non-finite value {cleaned[col]!r}")
        if not (low <= val <= high):
            raise ValueError(f"{col}={val:g} is outside [{low:g}, {high:g}]")
        cleaned[col] = val

    return cleaned


def read_and_audit_csv(input_path: str | Path = DEFAULT_RAW_DATA_PATH) -> dict:
    """Read raw CSV line by line using open(), validate Q1 bounds, and log corrupt rows."""
    valid_records = []
    rejected_records = []
    total_rows = 0

    try:
        with open(input_path, mode="r", encoding="utf-8", newline="") as file_handle:
            header_line = file_handle.readline()
            if not header_line.strip():
                raise ValueError(f"Input CSV file is empty: {input_path}")

            header = [
                col.strip().lstrip("\ufeff")
                for col in next(csv.reader([header_line]))
            ]
            missing = [col for col in EXPECTED_COLUMNS if col not in header]
            if missing:
                raise ValueError(f"Missing required column(s): {', '.join(missing)}")

            for line_num, raw_line in enumerate(file_handle, start=2):
                total_rows += 1
                line = raw_line.rstrip("\r\n")
                try:
                    if not line.strip():
                        raise ValueError("Empty or blank line")
                    fields = next(csv.reader([line]))
                    if len(fields) != len(header):
                        raise ValueError(
                            f"Expected {len(header)} columns, found {len(fields)}"
                        )
                    valid_records.append(validate_record(dict(zip(header, fields))))
                except (ValueError, csv.Error) as exc:
                    logger.warning("Line %d rejected: %s", line_num, exc)
                    rejected_records.append(
                        {"line_number": line_num, "raw_line": line, "reason": str(exc)}
                    )
    except FileNotFoundError:
        logger.error("Input CSV file not found: %s", input_path)
        raise

    logger.info(
        "Q1 audit complete for %s | total=%d | accepted=%d | rejected=%d",
        input_path,
        total_rows,
        len(valid_records),
        len(rejected_records),
    )
    return {
        "total_rows": total_rows,
        "accepted_count": len(valid_records),
        "rejected_count": len(rejected_records),
        "valid_records": valid_records,
        "rejected_records": rejected_records,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    try:
        summary = read_and_audit_csv()
        print(
            f"Audited {summary['total_rows']} rows: "
            f"{summary['accepted_count']} valid, {summary['rejected_count']} rejected."
        )
    except (FileNotFoundError, ValueError) as err:
        print(f"Audit aborted: {err}")
