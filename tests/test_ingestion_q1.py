"""Unit tests for Q1 defensive CSV reading and bounds validation."""

import logging
from pathlib import Path
import tempfile
import unittest

from src.ingestion import DEFAULT_RAW_DATA_PATH, EXPECTED_COLUMNS, read_and_audit_csv

HEADER = ",".join(EXPECTED_COLUMNS)


class TestIngestionQ1(unittest.TestCase):
    """Test suite for Q1 bounds checking, malformed row handling, and logging."""

    def _write_csv(self, directory: Path, filename: str, lines: list[str]) -> Path:
        path = directory / filename
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_actual_raw_dataset_passes_q1_bounds(self) -> None:
        result = read_and_audit_csv(DEFAULT_RAW_DATA_PATH)
        self.assertEqual(result["total_rows"], 708)
        self.assertEqual(result["accepted_count"], 708)
        self.assertEqual(result["rejected_count"], 0)
        self.assertEqual(tuple(result["valid_records"][0].keys()), EXPECTED_COLUMNS)

    def test_inclusive_boundary_values_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = self._write_csv(
                Path(tmpdir),
                "boundaries.csv",
                [
                    HEADER,
                    "S001,Male,0,0,0,High School,No,No,0,Fail",
                    "S002,Female,60,100,100,PhD,Yes,Yes,100,Pass",
                ],
            )
            result = read_and_audit_csv(csv_path)
            self.assertEqual(result["accepted_count"], 2)
            self.assertEqual(result["rejected_count"], 0)

    def test_out_of_range_values_rejected_and_logged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = self._write_csv(
                Path(tmpdir),
                "out_of_range.csv",
                [
                    HEADER,
                    "S010,Male,-1,80,70,High School,Yes,No,65,Pass",
                    "S011,Female,61,80,70,High School,Yes,No,65,Pass",
                    "S012,Male,20,-0.5,70,High School,Yes,No,65,Pass",
                    "S013,Female,20,100.1,70,High School,Yes,No,65,Pass",
                    "S014,Male,20,80,-5,High School,Yes,No,65,Pass",
                    "S015,Female,20,80,101,High School,Yes,No,65,Pass",
                    "S016,Male,20,80,70,High School,Yes,No,-1,Fail",
                    "S017,Female,20,80,70,High School,Yes,No,105,Pass",
                ],
            )
            with self.assertLogs("src.ingestion", level=logging.WARNING) as logs:
                result = read_and_audit_csv(csv_path)

            self.assertEqual(result["total_rows"], 8)
            self.assertEqual(result["accepted_count"], 0)
            self.assertEqual(result["rejected_count"], 8)
            self.assertEqual(len(logs.output), 8)
            self.assertIn("Study_Hours_per_Week=-1", result["rejected_records"][0]["reason"])
            self.assertIn("Study_Hours_per_Week=61", result["rejected_records"][1]["reason"])
            self.assertIn("Attendance_Rate=-0.5", result["rejected_records"][2]["reason"])
            self.assertIn("Attendance_Rate=100.1", result["rejected_records"][3]["reason"])
            self.assertIn("Past_Exam_Scores=-5", result["rejected_records"][4]["reason"])
            self.assertIn("Past_Exam_Scores=101", result["rejected_records"][5]["reason"])
            self.assertIn("Final_Exam_Score=-1", result["rejected_records"][6]["reason"])
            self.assertIn("Final_Exam_Score=105", result["rejected_records"][7]["reason"])

    def test_malformed_non_numeric_and_missing_id_rows_handled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = self._write_csv(
                Path(tmpdir),
                "malformed.csv",
                [
                    HEADER,
                    "S100,Male,25,85.5,78,Bachelors,Yes,No,72,Pass",
                    "S101,Female,abc,80,75,Masters,Yes,Yes,70,Pass",
                    "S102,Male,20,NaN,75,Masters,Yes,Yes,70,Pass",
                    "S103,Female,20,80,75",
                    "S104,Male,20,80,75,PhD,Yes,No,70,Pass,EXTRA",
                    ",Female,20,80,75,PhD,Yes,No,70,Pass",
                    "   ",
                ],
            )
            result = read_and_audit_csv(csv_path)

            self.assertEqual(result["total_rows"], 7)
            self.assertEqual(result["accepted_count"], 1)
            self.assertEqual(result["rejected_count"], 6)
            self.assertEqual(result["valid_records"][0]["Student_ID"], "S100")
            self.assertIn("could not convert string to float", result["rejected_records"][0]["reason"])
            self.assertIn("non-finite", result["rejected_records"][1]["reason"])
            self.assertIn("Expected 10 columns, found 5", result["rejected_records"][2]["reason"])
            self.assertIn("Expected 10 columns, found 11", result["rejected_records"][3]["reason"])
            self.assertIn("Student_ID is missing or empty", result["rejected_records"][4]["reason"])
            self.assertIn("Empty or blank line", result["rejected_records"][5]["reason"])

    def test_missing_file_raises_and_logs_error(self) -> None:
        missing_path = Path("data/raw/does_not_exist.csv")
        with self.assertLogs("src.ingestion", level=logging.ERROR):
            with self.assertRaises(FileNotFoundError):
                read_and_audit_csv(missing_path)

    def test_missing_required_column_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = self._write_csv(
                Path(tmpdir),
                "bad_header.csv",
                [
                    "student_id,attendance,exam_score",
                    "S001,85,75",
                ],
            )
            with self.assertRaises(ValueError):
                read_and_audit_csv(csv_path)


if __name__ == "__main__":
    unittest.main()
