#!/usr/bin/env python3
"""처리 파이프라인 뼈대: 읽기 → 검증 → 변환 → 집계 → 출력 → 로그. 표준 라이브러리만 사용.

  python3 src/pipeline.py --input data/ --out outputs/

입력이 바뀌면 고칠 곳: SCHEMA, KEY, transform(), aggregate()
같은 입력으로 두 번 실행해도 결과가 같아야 한다(멱등).
"""
import argparse
import csv
import json
import logging
import os
import sys
from datetime import datetime

# 컬럼 이름: (타입, 필수 여부)   타입: str | int | float | date
SCHEMA = {
    # "order_id": ("str", True),
    # "amount": ("float", True),
    # "order_date": ("date", False),
}
KEY = None          # 중복 검사할 키 컬럼. 예: "order_id"
DATE_FMT = "%Y-%m-%d"


class ValidationError(Exception):
    pass


def read_rows(path):
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            with open(path, newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise ValidationError(f"인코딩을 읽을 수 없음: {path}")


def cast(value, typ):
    v = (value or "").strip()
    if v == "":
        return None
    if typ == "int":
        return int(float(v.replace(",", "")))
    if typ == "float":
        return float(v.replace(",", ""))
    if typ == "date":
        return datetime.strptime(v, DATE_FMT).date()
    return v


def validate(rows, schema=None, key=None):
    """검증 통과한 행(타입 변환됨)과 경고 목록을 돌려준다. 치명적 문제는 ValidationError."""
    schema = SCHEMA if schema is None else schema
    key = KEY if key is None else key
    if not rows:
        raise ValidationError("입력이 비어 있음")
    missing_cols = [c for c in schema if c not in rows[0]]
    if missing_cols:
        raise ValidationError(f"필수 컬럼 없음: {missing_cols}")
    ok, warnings, seen = [], [], set()
    for i, r in enumerate(rows, start=2):   # 2 = 헤더 다음 줄
        out, bad = dict(r), None
        for col, (typ, required) in schema.items():
            try:
                out[col] = cast(r.get(col), typ)
            except (ValueError, TypeError):
                bad = f"{i}행 {col}: 타입 오류 '{r.get(col)}'"
                break
            if required and out[col] is None:
                bad = f"{i}행 {col}: 필수값 비어 있음"
                break
        if bad:
            warnings.append(bad)
            continue
        if key:
            k = out.get(key)
            if k in seen:
                warnings.append(f"{i}행 {key}={k}: 중복, 건너뜀")
                continue
            seen.add(k)
        ok.append(out)
    if not ok:
        raise ValidationError("검증을 통과한 행이 없음")
    return ok, warnings


def transform(rows):
    """행 단위 변환. 입력 요구가 바뀌면 여기를 고친다."""
    return rows


def aggregate(rows):
    """집계. 결과는 JSON으로 저장되는 dict."""
    return {"rows": len(rows)}


def write_outputs(rows, summary, out_dir, tag):
    os.makedirs(out_dir, exist_ok=True)
    if rows:
        path = os.path.join(out_dir, f"processed_{tag}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows({k: ("" if v is None else v) for k, v in r.items()} for r in rows)
    with open(os.path.join(out_dir, f"summary_{tag}.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)


def run(input_path, out_dir, tag):
    paths = ([os.path.join(input_path, x) for x in sorted(os.listdir(input_path)) if x.lower().endswith(".csv")]
             if os.path.isdir(input_path) else [input_path])
    all_rows, all_warn = [], []
    for p in paths:
        rows, warn = validate(read_rows(p))
        logging.info("읽음 %s: 통과 %d행, 경고 %d건", p, len(rows), len(warn))
        all_rows += rows
        all_warn += [f"{os.path.basename(p)} {w}" for w in warn]
    rows = transform(all_rows)
    summary = aggregate(rows)
    summary.update(input_files=[os.path.basename(p) for p in paths], warnings=all_warn[:100],
                   warning_count=len(all_warn), run_at=datetime.now().isoformat(timespec="seconds"))
    write_outputs(rows, summary, out_dir, tag)
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="CSV 파일 또는 폴더")
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--tag", default=datetime.now().strftime("%Y%m%d"), help="출력 파일 이름에 붙는 태그")
    a = ap.parse_args()
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(f"logs/run_{a.tag}.log", encoding="utf-8"),
                                  logging.StreamHandler(sys.stdout)])
    try:
        s = run(a.input, a.out, a.tag)
        logging.info("완료: %s", {k: v for k, v in s.items() if k != "warnings"})
    except ValidationError as e:
        logging.error("실패: %s", e)
        sys.exit(2)


if __name__ == "__main__":
    main()
