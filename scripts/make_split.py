#!/usr/bin/env python3
"""CSV를 학습/검증/테스트로 나눈다. 표준 라이브러리만 사용.

  python3 scripts/make_split.py data/x.csv --strategy random  --test 0.2 --val 0.1
  python3 scripts/make_split.py data/x.csv --strategy stratify --target y
  python3 scripts/make_split.py data/x.csv --strategy time --time-col timestamp
  python3 scripts/make_split.py data/x.csv --strategy group --group-col equipment_id

출력: data/splits/{train,val,test}.csv + data/splits/split_report.md
- time: 시간순 정렬 후 앞=학습, 중간=검증, 뒤=테스트 (미래 정보 누수 방지)
- group: 같은 그룹(설비·고객 등)은 한 세트에만 들어감
- 중복 행은 --dedup 으로 분할 전에 제거할 수 있다
시드는 고정(기본 42). 같은 명령은 같은 결과를 낸다.
"""
import argparse
import csv
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime

DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d",
                "%Y-%m-%dT%H:%M:%S", "%Y%m%d"]


def read(path):
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            with open(path, newline="", encoding=enc) as f:
                r = csv.reader(f)
                return next(r), [row for row in r]
        except UnicodeDecodeError:
            continue
    sys.exit(f"인코딩을 읽을 수 없음: {path}")


def parse_time(v):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v.strip(), fmt)
        except ValueError:
            pass
    try:
        return float(v)
    except ValueError:
        return None


def cut(n, test, val):
    n_test = round(n * test)
    n_val = round(n * val)
    return n - n_val - n_test, n_val, n_test


def split_random(rows, test, val, rng):
    idx = list(range(len(rows)))
    rng.shuffle(idx)
    a, b, _ = cut(len(idx), test, val)
    return idx[:a], idx[a:a + b], idx[a + b:]


def split_stratify(rows, col, test, val, rng):
    by = defaultdict(list)
    for i, r in enumerate(rows):
        by[r[col]].append(i)
    tr, va, te = [], [], []
    for _, idx in sorted(by.items()):
        rng.shuffle(idx)
        a, b, _ = cut(len(idx), test, val)
        tr += idx[:a]; va += idx[a:a + b]; te += idx[a + b:]
    return tr, va, te


def split_time(rows, col, test, val):
    keyed = [(parse_time(r[col]), i) for i, r in enumerate(rows)]
    bad = sum(1 for k, _ in keyed if k is None)
    if bad:
        sys.exit(f"시간 컬럼에서 해석 못 한 값 {bad}건. --time-col 확인")
    idx = [i for _, i in sorted(keyed)]
    a, b, _ = cut(len(idx), test, val)
    return idx[:a], idx[a:a + b], idx[a + b:]


def split_group(rows, col, test, val, rng):
    groups = sorted({r[col] for r in rows})
    if len(groups) < 3:
        sys.exit(f"그룹이 {len(groups)}개뿐이라 3세트로 나눌 수 없음")
    rng.shuffle(groups)
    a, b, c = cut(len(groups), test, val)
    if b == 0 and val > 0:
        a, b = a - 1, 1
    if c == 0:
        a, c = a - 1, 1
    g_tr, g_va = set(groups[:a]), set(groups[a:a + b])
    tr, va, te = [], [], []
    for i, r in enumerate(rows):
        (tr if r[col] in g_tr else va if r[col] in g_va else te).append(i)
    return tr, va, te


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--strategy", choices=["random", "stratify", "time", "group"], default="random")
    ap.add_argument("--target", help="타깃 컬럼 (stratify 필수, 나머지는 분포 리포트용)")
    ap.add_argument("--time-col")
    ap.add_argument("--group-col")
    ap.add_argument("--test", type=float, default=0.2)
    ap.add_argument("--val", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dedup", action="store_true", help="완전 중복 행을 분할 전에 제거")
    ap.add_argument("--out", default="data/splits")
    a = ap.parse_args()

    header, rows = read(a.path)
    n0 = len(rows)
    if a.dedup:
        seen, uniq = set(), []
        for r in rows:
            t = tuple(r)
            if t not in seen:
                seen.add(t); uniq.append(r)
        rows = uniq
    col = lambda name: header.index(name) if name in header else sys.exit(f"컬럼 없음: {name}")
    rng = random.Random(a.seed)
    if a.strategy == "random":
        tr, va, te = split_random(rows, a.test, a.val, rng)
    elif a.strategy == "stratify":
        if not a.target:
            sys.exit("--strategy stratify 는 --target 이 필요")
        tr, va, te = split_stratify(rows, col(a.target), a.test, a.val, rng)
    elif a.strategy == "time":
        if not a.time_col:
            sys.exit("--strategy time 은 --time-col 이 필요")
        tr, va, te = split_time(rows, col(a.time_col), a.test, a.val)
    else:
        if not a.group_col:
            sys.exit("--strategy group 은 --group-col 이 필요")
        tr, va, te = split_group(rows, col(a.group_col), a.test, a.val, rng)

    os.makedirs(a.out, exist_ok=True)
    sets = {"train": tr, "val": va, "test": te}
    for name, idx in sets.items():
        with open(os.path.join(a.out, f"{name}.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(header); w.writerows(rows[i] for i in sorted(idx))

    # 리포트
    L = ["# 데이터 분할", "",
         f"- 생성: {datetime.now():%Y-%m-%d %H:%M} · 명령: `python3 scripts/make_split.py {' '.join(sys.argv[1:])}`",
         f"- 원본 {n0:,}행" + (f" → 중복 제거 후 {len(rows):,}행" if a.dedup else "") + f" · 방식 `{a.strategy}` · 시드 {a.seed}", "",
         "| 세트 | 행 | 비율 |" + (" 타깃 분포 |" if a.target else "") + (" 기간 |" if a.time_col else "") + (" 그룹 수 |" if a.group_col else ""),
         "|---|---|---|" + ("---|" if a.target else "") + ("---|" if a.time_col else "") + ("---|" if a.group_col else "")]
    for name, idx in sets.items():
        line = f"| {name} | {len(idx):,} | {len(idx) / max(len(rows), 1) * 100:.1f}% |"
        if a.target:
            c = Counter(rows[i][col(a.target)] for i in idx); tot = sum(c.values()) or 1
            line += " " + ", ".join(f"{k}={v} ({v / tot * 100:.1f}%)" for k, v in sorted(c.items())) + " |"
        if a.time_col:
            ts = sorted(parse_time(rows[i][col(a.time_col)]) for i in idx)
            line += f" {ts[0]} ~ {ts[-1]} |" if ts else " - |"
        if a.group_col:
            line += f" {len({rows[i][col(a.group_col)] for i in idx})} |"
        L.append(line)
    checks = []
    tr_s, va_s, te_s = set(tr), set(va), set(te)
    checks.append(f"- 인덱스 겹침 없음: {'예' if not (tr_s & va_s or tr_s & te_s or va_s & te_s) else '아니오'}")
    checks.append(f"- 행 수 합계 = 전체: {'예' if len(tr) + len(va) + len(te) == len(rows) else '아니오'}")
    key = lambda i: tuple(rows[i])
    dup_cross = len({key(i) for i in te} & {key(i) for i in tr})
    checks.append(f"- 학습과 테스트에 똑같은 행: {dup_cross}건" + (" ← 누수 가능, --dedup 고려" if dup_cross else ""))
    if a.group_col:
        g = lambda s: {rows[i][col(a.group_col)] for i in s}
        checks.append(f"- 그룹이 세트 사이에 섞임: {'없음' if not (g(tr) & g(te) or g(tr) & g(va)) else '있음'}")
    if a.time_col and tr and te:
        checks.append(f"- 학습이 테스트보다 과거: {'예' if max(parse_time(rows[i][col(a.time_col)]) for i in tr) <= min(parse_time(rows[i][col(a.time_col)]) for i in te) else '아니오'}")
    if a.target:
        for name, idx in sets.items():
            c = Counter(rows[i][col(a.target)] for i in idx)
            if len(c) < len(Counter(r[col(a.target)] for r in rows)):
                checks.append(f"- {name}에 없는 타깃 클래스가 있음 ← stratify 고려")
    L += ["", "## 자동 점검", ""] + checks + ["", "## 분할 근거 (사람이 채움, NOTES.md에도 한 줄)", "", "- "]
    with open(os.path.join(a.out, "split_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"train {len(tr):,} / val {len(va):,} / test {len(te):,} → {a.out}/")
    for c in checks:
        print(c)


if __name__ == "__main__":
    main()
