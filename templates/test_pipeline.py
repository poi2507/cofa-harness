"""파이프라인 테스트 뼈대. 실행: python3 -m unittest tests/test_pipeline.py -v
정상 1 + 예외 4(빈 입력, 필수 컬럼 없음, 타입 오류, 키 중복). 과제에 맞게 SCHEMA/KEY를 바꿔 쓴다."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pipeline  # noqa: E402

SCHEMA = {"id": ("str", True), "amount": ("float", True), "date": ("date", False)}


class ValidateTests(unittest.TestCase):
    def test_normal(self):
        rows = [{"id": "a", "amount": "1,200", "date": "2026-10-31"}, {"id": "b", "amount": "3", "date": ""}]
        ok, warn = pipeline.validate(rows, SCHEMA, key="id")
        self.assertEqual(len(ok), 2)
        self.assertEqual(ok[0]["amount"], 1200.0)
        self.assertIsNone(ok[1]["date"])
        self.assertEqual(warn, [])

    def test_empty_input(self):
        with self.assertRaises(pipeline.ValidationError):
            pipeline.validate([], SCHEMA)

    def test_missing_required_column(self):
        with self.assertRaises(pipeline.ValidationError):
            pipeline.validate([{"id": "a"}], SCHEMA)

    def test_type_error_is_warning_not_crash(self):
        rows = [{"id": "a", "amount": "x", "date": ""}, {"id": "b", "amount": "2", "date": ""}]
        ok, warn = pipeline.validate(rows, SCHEMA)
        self.assertEqual(len(ok), 1)
        self.assertEqual(len(warn), 1)

    def test_duplicate_key_skipped(self):
        rows = [{"id": "a", "amount": "1", "date": ""}, {"id": "a", "amount": "2", "date": ""}]
        ok, warn = pipeline.validate(rows, SCHEMA, key="id")
        self.assertEqual(len(ok), 1)
        self.assertIn("중복", warn[0])


if __name__ == "__main__":
    unittest.main()
