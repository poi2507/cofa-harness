#!/usr/bin/env python3
"""CSV 데이터 품질 점검 → 마크다운 리포트. 표준 라이브러리만 사용.

  python3 scripts/data_check.py data/ --out reports/data_check.md
  python3 scripts/data_check.py data/a.csv data/b.csv --target failure_within_24h

점검 항목: 행·열, 컬럼 타입, 결측률, 고유값, 숫자 범위·극단값(IQR), 날짜 범위,
중복 행, 키 컬럼 중복, 타깃 분포, 파일 간 키 정합성, 누수 의심 컬럼(이름 기준).
리포트 끝의 "문서와 대조"와 "처리 결정"은 사람이 채운다.
"""
import argparse
import csv
import os
import re
import statistics
import sys
from collections import Counter
from datetime import datetime

MISSING = {"", "na", "n/a", "nan", "null", "none", "-", "?"}
DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d",
                "%Y-%m-%dT%H:%M:%S", "%Y%m%d", "%m/%d/%Y", "%d/%m/%Y", "%Y.%m.%d"]
KEY_RE = re.compile(r"(^|_)(id|key|no|code|lot)$|id$", re.I)
LEAK_RE = re.compile(r"(result|outcome|final|after|actual|label|target|score|flag|status)", re.I)


def read_csv(path, max_rows):
    last_err = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            with open(path, newline="", encoding=enc) as f:
                r = csv.reader(f)
                header = next(r, [])
                rows, truncated = [], False
                for i, row in enumerate(r):
                    if i >= max_rows:
                        truncated = True
                        break
                    rows.append(row + [""] * (len(header) - len(row)))
            return header, rows, enc, truncated
        except UnicodeDecodeError as e:
            last_err = e
    raise last_err


def is_missing(v):
    return v is None or v.strip().lower() in MISSING


def to_num(v):
    try:
        return float(v.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def to_date(v):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            pass
    return None


def fmt(x):
    if isinstance(x, float):
        return f"{x:,.4g}" if abs(x) < 1e6 else f"{x:,.0f}"
    return str(x)


def analyze_column(name, values):
    n = len(values)
    present = [v.strip() for v in values if not is_missing(v)]
    missing = n - len(present)
    uniq = len(set(present))
    info = dict(name=name, missing=missing, missing_pct=(missing / n * 100 if n else 0), uniq=uniq,
                type="text", range="", flags=[])
    if not present:
        info["type"] = "empty"
        info["flags"].append("전부 결측")
        return info
    nums = [x for x in (to_num(v) for v in present) if x is not None]
    if len(nums) / len(present) >= 0.95:
        info["type"] = "int" if all(x.is_integer() for x in nums) else "float"
        lo, hi = min(nums), max(nums)
        info["range"] = f"{fmt(lo)} ~ {fmt(hi)} (중앙값 {fmt(statistics.median(nums))})"
        if len(nums) >= 20:
            q = statistics.quantiles(nums, n=4)
            iqr = q[2] - q[0]
            if iqr > 0:
                out = sum(1 for x in nums if x < q[0] - 3 * iqr or x > q[2] + 3 * iqr)
                if out:
                    info["flags"].append(f"극단값 {out}건 (IQR×3 밖)")
        if len(nums) < len(present):
            info["flags"].append(f"숫자 아닌 값 {len(present) - len(nums)}건")
        if uniq == 2 and set(present) <= {"0", "1", "0.0", "1.0"}:
            info["flags"].append("이진(타깃 후보)")
        if info["type"] == "int" and uniq == len(present) and n > 1:
            info["flags"].append("전부 고유(ID일 수 있음)")
        return info
    sample = present[:300]
    dates = [d for d in (to_date(v) for v in sample) if d is not None]
    if len(dates) / len(sample) >= 0.9:
        all_dates = [d for d in (to_date(v) for v in present) if d is not None]
        info["type"] = "date"
        info["range"] = f"{min(all_dates):%Y-%m-%d %H:%M} ~ {max(all_dates):%Y-%m-%d %H:%M}"
        if len(all_dates) < len(present):
            info["flags"].append(f"날짜 아닌 값 {len(present) - len(all_dates)}건")
        return info
    top = Counter(present).most_common(5)
    info["range"] = ", ".join(f"{k}({c})" for k, c in top) + (" …" if uniq > 5 else "")
    if 2 <= uniq <= 10 and n >= 20:
        info["flags"].append("범주형")
    return info


def check_file(path, max_rows, target):
    header, rows, enc, truncated = read_csv(path, max_rows)
    n = len(rows)
    cols = [list(c) for c in zip(*rows)] if rows else [[] for _ in header]
    infos = [analyze_column(h, c) for h, c in zip(header, cols)]
    dup_rows = n - len(set(tuple(r) for r in rows))
    key_dups = {}
    for h, c in zip(header, cols):
        if KEY_RE.search(h):
            vals = [v for v in c if not is_missing(v)]
            d = len(vals) - len(set(vals))
            if d and vals and len(set(vals)) / len(vals) >= 0.5:   # 고유값이 절반 이상일 때만 "키"로 본다
                key_dups[h] = d
    target_info = None
    if target and target in header:
        target_info = Counter(v.strip() for v in cols[header.index(target)]).most_common(10)
    leak = [h for h in header if LEAK_RE.search(h) and h != target]
    return dict(path=path, header=header, n=n, enc=enc, truncated=truncated, infos=infos,
                dup_rows=dup_rows, key_dups=key_dups, target=target_info, leak=leak, cols=cols)


def join_checks(files):
    out = []
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            a, b = files[i], files[j]
            for col in sorted(set(a["header"]) & set(b["header"])):
                if not KEY_RE.search(col):
                    continue
                sa = {v for v in a["cols"][a["header"].index(col)] if not is_missing(v)}
                sb = {v for v in b["cols"][b["header"].index(col)] if not is_missing(v)}
                out.append((os.path.basename(a["path"]), os.path.basename(b["path"]), col,
                            len(sa), len(sb), len(sa - sb), len(sb - sa)))
    return out


def render(files, joins, argv):
    L = ["# 데이터 점검", "",
         f"- 생성: {datetime.now():%Y-%m-%d %H:%M} · 명령: `python3 scripts/data_check.py {' '.join(argv)}`",
         "- 표는 자동 생성. 마지막 두 절은 사람이 채운다.", "", "## 요약", "",
         "| 파일 | 행 | 열 | 중복 행 | 인코딩 | 비고 |", "|---|---|---|---|---|---|"]
    for f in files:
        note = []
        if f["truncated"]:
            note.append("max-rows로 잘림")
        if f["key_dups"]:
            note.append("키 중복: " + ", ".join(f"{k} {v}건" for k, v in f["key_dups"].items()))
        L.append(f"| {os.path.basename(f['path'])} | {f['n']:,} | {len(f['header'])} | {f['dup_rows']:,} | {f['enc']} | {'; '.join(note)} |")
    for f in files:
        L += ["", f"## {os.path.basename(f['path'])}", "",
              "| 컬럼 | 타입 | 결측 | 고유 | 범위 / 상위값 | 표시 |", "|---|---|---|---|---|---|"]
        for c in f["infos"]:
            miss = f"{c['missing']:,} ({c['missing_pct']:.1f}%)" if c["missing"] else "0"
            L.append(f"| {c['name']} | {c['type']} | {miss} | {c['uniq']:,} | {c['range']} | {'; '.join(c['flags'])} |")
        if f["target"]:
            tot = sum(v for _, v in f["target"])
            L += ["", "타깃 분포: " + ", ".join(f"{k or '(결측)'}={v:,} ({v / tot * 100:.1f}%)" for k, v in f["target"])]
        if f["leak"]:
            L += ["", "누수 의심(이름 기준, 확인 필요): " + ", ".join(f["leak"])]
    if joins:
        L += ["", "## 파일 간 키 정합성", "",
              "| 파일 A | 파일 B | 키 | A 고유 | B 고유 | A에만 | B에만 |", "|---|---|---|---|---|---|---|"]
        for a, b, col, na, nb, ab, ba in joins:
            L.append(f"| {a} | {b} | {col} | {na:,} | {nb:,} | {ab:,} | {ba:,} |")
    items = []
    for f in files:
        base = os.path.basename(f["path"])
        if f["dup_rows"]:
            items.append(f"{base}: 중복 행 {f['dup_rows']:,}건 → 제거할지, 정당한 중복인지")
        for k, v in f["key_dups"].items():
            items.append(f"{base}: 키 `{k}` 중복 {v}건 → 조인 전에 해결")
        for c in f["infos"]:
            if c["missing_pct"] >= 5:
                items.append(f"{base}.{c['name']}: 결측 {c['missing_pct']:.1f}% → 제외/대체/결측 자체가 신호인지 결정")
            for fl in c["flags"]:
                if fl.startswith(("극단값", "숫자 아닌", "날짜 아닌")):
                    items.append(f"{base}.{c['name']}: {fl} → 단위 오류인지 실제 이상인지 원본 확인")
        if f["leak"]:
            items.append(f"{base}: 누수 의심 컬럼 {', '.join(f['leak'])} → 예측 시점에 알 수 있는 값인지")
    for a, b, col, na, nb, ab, ba in joins:
        if ab or ba:
            items.append(f"{a}↔{b} 키 `{col}`: 한쪽에만 있는 값 {ab:,}/{ba:,} → 조인 손실 확인")
    L += ["", "## 확인 필요 (자동 추출)", ""]
    L += [f"- [ ] {it}" for it in items] or ["- 자동 추출된 항목 없음"]
    L += ["", "## 문서와 대조 (사람이 채움)", "",
          "| 항목 | 데이터에서 | 과제 문서·메신저에서 | 일치 |", "|---|---|---|---|",
          "| 행 수 / 건수 | | | |", "| 기간 | | | |", "| 대상 수(설비·제품·고객 등) | | | |", "| 핵심 합계 | | | |",
          "", "## 처리 결정 (사람이 채움, NOTES.md에도 한 줄)", "", "- "]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="CSV 파일 또는 폴더")
    ap.add_argument("--out", default="reports/data_check.md")
    ap.add_argument("--target", default=None, help="타깃 컬럼 이름")
    ap.add_argument("--max-rows", type=int, default=300000)
    a = ap.parse_args()
    csvs = []
    for p in a.paths:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                csvs += [os.path.join(root, x) for x in sorted(names) if x.lower().endswith((".csv", ".tsv"))]
        elif os.path.isfile(p):
            csvs.append(p)
        else:
            print(f"없음: {p}", file=sys.stderr)
    if not csvs:
        sys.exit("점검할 CSV가 없음")
    files = [check_file(p, a.max_rows, a.target) for p in csvs]
    md = render(files, join_checks(files), sys.argv[1:])
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(md)
    for f in files:
        print(f"{os.path.basename(f['path'])}: {f['n']:,}행 {len(f['header'])}열, 중복 {f['dup_rows']:,}, "
              f"결측 있는 컬럼 {sum(1 for c in f['infos'] if c['missing'])}개")
    print(f"→ {a.out}")


if __name__ == "__main__":
    main()
