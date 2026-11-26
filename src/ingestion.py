"""Data ingestion and Q1 bounds-validation utilities for student analytics."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import logging
import math
from pathlib import Path
from typing import Any

DEFAULT_RAW_DATA_PATH = Path("data/raw/student_performance_dataset.csv")

EXPECTED_COLUMNS: tuple[str, ...] = (
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

# Valid inclusive bounds specified in Project 21 Q1.
NUMERIC_BOUNDS: dict[str, tuple[float, float]] = {
    "Study_Hours_per_Week": (0.0, 60.0),
    "Attendance_Rate": (0.0, 100.0),
    "Past_Exam_Scores": (0.0, 100.0),
    "Final_Exam_Score": (0.0, 100.0),
}

INTEGER_DISPLAY_COLUMNS: frozenset[str] = frozenset(
    {"Study_Hours_per_Week", "Past_Exam_Scores", "Final_Exam_Score"}
)


@dataclass(frozen=True)
class RejectedRecord:
    """Represents a single CSV row rejected during ingestion validation."""

    line_number: int
    raw_line: str
    reason: str
    student_id: str | None = None


@dataclass
class IngestionAuditResult:
    """Holds valid records and rejection details from a raw CSV audit."""

    input_path: str
    total_rows: int
    valid_records: list[dict[str, Any]]
    rejected_records: list[RejectedRecord]

    @property
    def accepted_count(self) -> int:
        """Return the number of records that passed Q1 validation."""
        return len(self.valid_records)

    @property
    def rejected_count(self) -> int:
        """Return the number of records rejected during Q1 validation."""
        return len(self.rejected_records)


def _get_logger(logger: logging.Logger | None = None) -> logging.Logger:
    """Return the supplied logger or a configured module logger."""
    if logger is not None:
        return logger
    module_logger = logging.getLogger(__name__)
    if not module_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s | %(name)s | %(message)s")
        handler.setFormatter(formatter)
        module_logger.addHandler(handler)
        module_logger.setLevel(logging.INFO)
    return module_logger


def _parse_csv_line(raw_line: str) -> list[str]:
    """Parse a single CSV line defensively using Python's csv.reader."""
    try:
        parsed_rows = list(csv.reader([raw_line]))
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV syntax: {exc}") from exc

    if len(parsed_rows) != 1:
        raise ValueError("Malformed CSV line: expected a single record.")
    return parsed_rows[0]


def parse_bounded_float(
    raw_value: str,
    field_name: str,
    min_val: float,
    max_val: float,
) -> float:
    """Parse a numeric field and validate that it is finite and within [min_val, max_val]."""
    text = raw_value.strip()
    if not text:
        raise ValueError(f"{field_name} is missing or empty")

    try:
        numeric_value = float(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} has non-numeric value {raw_value!r}") from exc

    if not math.isfinite(numeric_value):
        raise ValueError(f"{field_name} has non-finite value {raw_value!r}")

    if numeric_value < min_val or numeric_value > max_val:
        raise ValueError(
            f"{field_name}={numeric_value:g} is outside [{min_val:g}, {max_val:g}]"
        )

    return numeric_value


def validate_record(raw_record: dict[str, str]) -> dict[str, Any]:
    """Validate required fields and numeric bounds for a single student record.

    Raises ValueError summarizing all validation failures when a record is invalid.
    """
    errors: list[str] = []
    validated: dict[str, Any] = dict(raw_record)

    student_id = raw_record.get("Student_ID", "").strip()
    if not student_id:
        errors.append("Student_ID is missing or empty")
    validated["Student_ID"] = student_id

    for field_name, (min_val, max_val) in NUMERIC_BOUNDS.items():
        raw_value = raw_record.get(field_name, "")
        try:
            numeric_value = parse_bounded_float(raw_value, field_name, min_val, max_val)
            if field_name in INTEGER_DISPLAY_COLUMNS and numeric_value.is_integer():
                validated[field_name] = int(numeric_value)
            else:
                validated[field_name] = numeric_value
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        raise ValueError("; ".join(errors))

    return validated


def _validate_header(header_line: str) -> list[str]:
    """Parse and verify that the CSV header contains all expected columns."""
    header = [col.strip().lstrip("\ufeff") for col in _parse_csv_line(header_line)]
    missing_columns = [col for col in EXPECTED_COLUMNS if col not in header]
    if missing_columns:
        raise ValueError(
            f"Missing required CSV column(s): {', '.join(missing_columns)}"
        )
    return header


def read_and_audit_csv(
    input_path: str | Path,
    logger: logging.Logger | None = None,
) -> IngestionAuditResult:
    """Read raw CSV lines via open(), validate Q1 bounds, and log rejected rows."""
    active_logger = _get_logger(logger)
    path = Path(input_path)

    valid_records: list[dict[str, Any]] = []
    rejected_records: list[RejectedRecord] = []
    total_rows = 0

    try:
        with open(path, mode="r", encoding="utf-8", newline="") as file_handle:
            header_line = file_handle.readline()
            if not header_line:
                raise ValueError(f"Input CSV file is empty: {path}")

            header = _validate_header(header_line.rstrip("\r\n"))

            for line_number, raw_line in enumerate(file_handle, start=2):
                total_rows += 1
                clean_line = raw_line.rstrip("\r\n")

                if not clean_line.strip():
                    reason = "Empty or blank line"
                    rejected = RejectedRecord(
                        line_number=line_number,
                        raw_line=clean_line,
                        reason=reason,
                    )
                    rejected_records.append(rejected)
                    active_logger.warning("Line %d rejected: %s", line_number, reason)
                    continue

                try:
                    fields = _parse_csv_line(clean_line)
                except ValueError as exc:
                    reason = str(exc)
                    rejected = RejectedRecord(
                        line_number=line_number,
                        raw_line=clean_line,
                        reason=reason,
                    )
                    rejected_records.append(rejected)
                    active_logger.warning("Line %d rejected: %s", line_number, reason)
                    continue

                if len(fields) != len(header):
                    reason = (
                        f"Malformed row: expected {len(header)} columns, "
                        f"found {len(fields)}"
                    )
                    candidate_id = fields[0].strip() if fields else None
                    rejected = RejectedRecord(
                        line_number=line_number,
                        raw_line=clean_line,
                        reason=reason,
                        student_id=candidate_id or None,
                    )
                    rejected_records.append(rejected)
                    active_logger.warning("Line %d rejected: %s", line_number, reason)
                    continue

                raw_record = {
                    col: value.strip() for col, value in zip(header, fields)
                }
                student_id = raw_record.get("Student_ID") or None

                try:
                    validated = validate_record(raw_record)
                except ValueError as exc:
                    reason = str(exc)
                    rejected = RejectedRecord(
                        line_number=line_number,
                        raw_line=clean_line,
                        reason=reason,
                        student_id=student_id,
                    )
                    rejected_records.append(rejected)
                    active_logger.warning(
                        "Line %d rejected (Student_ID=%s): %s",
                        line_number,
                        student_id or "<missing>",
                        reason,
                    )
                    continue

                valid_records.append(validated)

    except FileNotFoundError as exc:
        active_logger.error("Input CSV file not found: %s", path)
        raise FileNotFoundError(f"Input CSV file not found: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        active_logger.error("Failed to read input CSV %s: %s", path, exc)
        raise

    active_logger.info(
        "Q1 audit complete for %s | total_rows=%d | accepted=%d | rejected=%d",
        path,
        total_rows,
        len(valid_records),
        len(rejected_records),
    )

    return IngestionAuditResult(
        input_path=str(path),
        total_rows=total_rows,
        valid_records=valid_records,
        rejected_records=rejected_records,
    )


def audit_raw_csv(
    input_path: str | Path = DEFAULT_RAW_DATA_PATH,
    logger: logging.Logger | None = None,
) -> IngestionAuditResult | None:
    """Run Q1 audit and handle missing/corrupt input files without crashing."""
    active_logger = _get_logger(logger)
    try:
        return read_and_audit_csv(input_path=input_path, logger=active_logger)
    except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError) as exc:
        active_logger.error("Audit aborted: %s", exc)
        return None


if __name__ == "__main__":
    audit_result = audit_raw_csv()
    if audit_result is not None:
        print(
            f"Audited {audit_result.total_rows} rows: "
            f"{audit_result.accepted_count} valid, "
            f"{audit_result.rejected_count} rejected."
        )
