#!/usr/bin/env python3
"""EDA 리포트: 통계표 + 그래프(inline SVG) → reports/eda.html, 숫자 요약 → reports/eda_stats.md
표준 라이브러리만 사용. 브라우저 미리보기로 eda.html을 연다.

  python3 scripts/eda_report.py data/x.csv
  python3 scripts/eda_report.py data/x.csv --target y --time timestamp --group line
  python3 scripts/eda_report.py data/long.csv --pivot timestamp,line --tag-col tag --value-col value   # 긴 형식 → 넓은 형식

포함: 숫자 요약(평균·표준편차·분위수·왜도·결측), 히스토그램, 범주 막대, 상관 히트맵,
시간 추세(일 단위, 그룹별 선), 타깃 관계(범주별 타깃 평균·구간별 타깃 평균·상관 순위),
기간 전후 비교, 자동 가설 후보.
"""
import argparse
import csv
import html
import math
import os
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import datetime

DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d",
                "%Y-%m-%dT%H:%M:%S", "%Y%m%d"]
MISSING = {"", "na", "n/a", "nan", "null", "none", "-"}
PALETTE = ["#2f6fbf", "#d9822b", "#2e9e6a", "#c2455a", "#7d5bbf", "#8a8f2e"]
W, H, PAD = 420, 220, 36


# ---------- 읽기·타입 ----------
def read(path):
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            with open(path, newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    sys.exit(f"인코딩을 읽을 수 없음: {path}")


def num(v):
    if v is None or v.strip().lower() in MISSING:
        return None
    try:
        return float(v.replace(",", ""))
    except ValueError:
        return None


def date(v):
    if not v:
        return None
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(v.strip(), f)
        except ValueError:
            pass
    return None


SENTINELS = {-9999.0, -999.0, -99.0, 999.0, 9999.0, 99999.0}


def find_sentinels(rows, cols):
    """-999 같은 결측 표시값: 정확히 그 값이 2번 이상, 나머지 분포에서 IQR×3 밖. {컬럼: (값, 건수)}"""
    out = {}
    for c in cols:
        xs = [x for x in (num(r.get(c)) for r in rows) if x is not None]
        cnt = Counter(x for x in xs if x in SENTINELS)
        rest = [x for x in xs if x not in SENTINELS]
        if not cnt or len(rest) < 20:
            continue
        q = st.quantiles(rest, n=4); iqr = q[2] - q[0]
        for v, n in cnt.items():
            if n >= 2 and (v < q[0] - 3 * iqr or v > q[2] + 3 * iqr):
                out.setdefault(c, []).append((v, n))
    return out


def pivot(rows, keys, tag, val):
    out = {}
    for r in rows:
        k = tuple(r[c] for c in keys)
        out.setdefault(k, {c: r[c] for c in keys})[r[tag]] = r[val]
    return list(out.values())


def col_types(rows, cols):
    t = {}
    for c in cols:
        vals = [r[c] for r in rows if r.get(c) is not None and r[c].strip().lower() not in MISSING]
        if not vals:
            t[c] = "empty"; continue
        sample = vals[:500]
        if sum(num(v) is not None for v in sample) / len(sample) >= 0.95:
            t[c] = "num"
        elif sum(date(v) is not None for v in sample[:200]) / len(sample[:200]) >= 0.9:
            t[c] = "date"
        elif len(set(vals)) <= 30:
            t[c] = "cat"
        else:
            t[c] = "text"
    return t


# ---------- 통계 ----------
def describe(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return None
    m = st.fmean(xs)
    sd = st.pstdev(xs) if n > 1 else 0.0
    q = st.quantiles(xs, n=4) if n >= 4 else [xs[0], st.median(xs), xs[-1]]
    skew = (sum((x - m) ** 3 for x in xs) / n) / (sd ** 3) if sd > 0 else 0.0
    return dict(n=n, mean=m, sd=sd, min=xs[0], q1=q[0], med=q[1], q3=q[2], max=xs[-1], skew=skew)


def pearson(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    xs, ys = zip(*pairs)
    mx, my = st.fmean(xs), st.fmean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in pairs) / (sx * sy)


def welch(a, b):
    """두 그룹 평균 차이: 차이, 효과크기(d), 대략적 t. 표본이 작으면 None."""
    if len(a) < 5 or len(b) < 5:
        return None
    ma, mb = st.fmean(a), st.fmean(b)
    va, vb = st.variance(a), st.variance(b)
    se = math.sqrt(va / len(a) + vb / len(b))
    sp = math.sqrt((va + vb) / 2)
    return dict(diff=mb - ma, d=(mb - ma) / sp if sp else 0.0, t=(mb - ma) / se if se else 0.0)


def f(x, d=3):
    if x is None:
        return "-"
    if isinstance(x, float):
        if abs(x) >= 1e5:
            return f"{x:,.0f}"
        return f"{x:,.{d}g}" if abs(x) < 1 else f"{x:,.{d + 1}g}"
    return f"{x:,}" if isinstance(x, int) else html.escape(str(x))


# ---------- SVG ----------
def svg_open(title, w=W, h=H):
    return [f'<figure><figcaption>{html.escape(title)}</figcaption><svg viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(title)}">']


def axis(lo, hi, w=W, h=H, ylab=""):
    out = [f'<line x1="{PAD}" y1="{h - PAD}" x2="{w - 8}" y2="{h - PAD}" class="ax"/>',
           f'<line x1="{PAD}" y1="10" x2="{PAD}" y2="{h - PAD}" class="ax"/>']
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        y = h - PAD - (h - PAD - 10) * i / 4
        out.append(f'<line x1="{PAD}" y1="{y:.1f}" x2="{w - 8}" y2="{y:.1f}" class="grid"/>'
                   f'<text x="{PAD - 4}" y="{y + 3:.1f}" class="tick" text-anchor="end">{f(v, 2)}</text>')
    if ylab:
        out.append(f'<text x="4" y="10" class="tick">{html.escape(ylab)}</text>')
    return out


def histogram(name, xs, bins=20):
    lo, hi = min(xs), max(xs)
    if lo == hi:
        hi = lo + 1
    step = (hi - lo) / bins
    cnt = [0] * bins
    for x in xs:
        cnt[min(int((x - lo) / step), bins - 1)] += 1
    top = max(cnt)
    s = svg_open(f"{name} 분포 (n={len(xs):,})") + axis(0, top, ylab="건수")
    bw = (W - PAD - 8) / bins
    for i, c in enumerate(cnt):
        bh = (H - PAD - 10) * c / top if top else 0
        s.append(f'<rect x="{PAD + i * bw + 1:.1f}" y="{H - PAD - bh:.1f}" width="{bw - 2:.1f}" height="{bh:.1f}" fill="{PALETTE[0]}"><title>{f(lo + i * step)}~{f(lo + (i + 1) * step)}: {c}</title></rect>')
    s.append(f'<text x="{PAD}" y="{H - 8}" class="tick">{f(lo)}</text><text x="{W - 8}" y="{H - 8}" class="tick" text-anchor="end">{f(hi)}</text>')
    return "".join(s) + "</svg></figure>"


def bars(title, items, fmt=lambda v: f(v), ylab="", note=None):
    """items: [(라벨, 값, 보조텍스트)]"""
    items = items[:15]
    if not items:
        return ""
    vals = [v for _, v, _ in items]
    lo, hi = min(0, min(vals)), max(vals) or 1
    h = max(H, 26 + 20 * len(items))
    s = [f'<figure><figcaption>{html.escape(title)}</figcaption><svg viewBox="0 0 {W} {h}" role="img" aria-label="{html.escape(title)}">']
    lab_w = 110
    for i, (lab, v, extra) in enumerate(items):
        y = 10 + i * 20
        bw = (W - lab_w - 70) * (v - lo) / (hi - lo) if hi > lo else 0
        s.append(f'<text x="{lab_w - 6}" y="{y + 12}" class="tick" text-anchor="end">{html.escape(str(lab)[:16])}</text>'
                 f'<rect x="{lab_w}" y="{y + 2}" width="{max(bw, 1):.1f}" height="14" fill="{PALETTE[1] if note and lab in note else PALETTE[0]}"><title>{html.escape(str(lab))}: {fmt(v)} {html.escape(extra)}</title></rect>'
                 f'<text x="{lab_w + bw + 4:.1f}" y="{y + 13}" class="tick">{fmt(v)} {html.escape(extra)}</text>')
    return "".join(s) + "</svg></figure>"


def lines(title, series, ylab=""):
    """series: {이름: [(x숫자, y)]} — x는 정렬된 숫자(일 인덱스)"""
    pts = [p for ps in series.values() for p in ps]
    if len(pts) < 2:
        return ""
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs) or 1
    y0, y1 = min(ys), max(ys)
    if y0 == y1:
        y1 = y0 + 1
    s = svg_open(title) + axis(y0, y1, ylab=ylab)
    sx = lambda x: PAD + (W - PAD - 8) * (x - x0) / ((x1 - x0) or 1)
    sy = lambda y: H - PAD - (H - PAD - 10) * (y - y0) / (y1 - y0)
    for k, (name, ps) in enumerate(list(series.items())[:6]):
        d = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in sorted(ps))
        s.append(f'<polyline points="{d}" fill="none" stroke="{PALETTE[k % 6]}" stroke-width="1.6"/>'
                 f'<text x="{W - 10}" y="{14 + k * 12}" class="tick" text-anchor="end" fill="{PALETTE[k % 6]}">{html.escape(str(name))}</text>')
    return "".join(s) + "</svg></figure>"


def heat(names, mat):
    n = len(names)
    cell = 26
    lab = 100
    w, h = lab + n * cell + 10, lab + n * cell + 10
    s = [f'<figure><figcaption>숫자 컬럼 상관 (피어슨)</figcaption><svg viewBox="0 0 {w} {h}" role="img" aria-label="상관 히트맵">']
    for i, a in enumerate(names):
        s.append(f'<text x="{lab - 4}" y="{lab + i * cell + 17}" class="tick" text-anchor="end">{html.escape(a[:14])}</text>'
                 f'<text x="{lab + i * cell + 13}" y="{lab - 4}" class="tick" transform="rotate(-50 {lab + i * cell + 13} {lab - 4})">{html.escape(a[:14])}</text>')
        for j in range(n):
            r = mat[i][j]
            if r is None:
                col = "#ddd"
            else:
                a_ = min(abs(r), 1)
                col = f"rgba(47,111,191,{a_:.2f})" if r >= 0 else f"rgba(194,69,90,{a_:.2f})"
            s.append(f'<rect x="{lab + j * cell}" y="{lab + i * cell}" width="{cell - 1}" height="{cell - 1}" fill="{col}"><title>{html.escape(a)} × {html.escape(names[j])}: {f(r, 2)}</title></rect>')
            if r is not None and i != j and abs(r) >= 0.3:
                s.append(f'<text x="{lab + j * cell + 13}" y="{lab + i * cell + 17}" class="tick" text-anchor="middle">{r:.1f}</text>')
    return "".join(s) + "</svg></figure>"


# ---------- 본체 ----------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--target"); ap.add_argument("--time"); ap.add_argument("--group")
    ap.add_argument("--pivot", help="긴 형식일 때 키 컬럼들(쉼표). --tag-col, --value-col 과 같이")
    ap.add_argument("--tag-col"); ap.add_argument("--value-col")
    ap.add_argument("--split-date", help="기간 전후 비교 기준일 YYYY-MM-DD (없으면 기간의 중간)")
    ap.add_argument("--out", default="reports/eda.html")
    a = ap.parse_args()

    rows = read(a.path)
    if a.pivot:
        if not (a.tag_col and a.value_col):
            sys.exit("--pivot 은 --tag-col, --value-col 이 필요")
        rows = pivot(rows, a.pivot.split(","), a.tag_col, a.value_col)
    if not rows:
        sys.exit("행이 없음")
    cols = list(rows[0].keys())
    for c in (a.target, a.time, a.group):
        if c and c not in cols:
            sys.exit(f"컬럼 없음: {c} (있는 것: {', '.join(cols)})")
    types = col_types(rows, cols)
    if a.time:
        types[a.time] = "date"
    numc = [c for c in cols if types[c] == "num" and c != a.target][:12]
    catc = [c for c in cols if types[c] == "cat" and c not in (a.target, a.group)]
    if a.group:
        catc = [a.group] + catc
    tgt_num = a.target and types.get(a.target) == "num"
    sent = find_sentinels(rows, numc + ([a.target] if tgt_num else []))
    for c, vals in sent.items():          # 결측 표시값은 결측으로 바꿔서 통계를 오염시키지 않게
        bad = {str(v) for v, _ in vals} | {str(int(v)) for v, _ in vals}
        for r in rows:
            if r.get(c) is not None and r[c].strip() in bad:
                r[c] = ""
    binary = {c for c in numc + ([a.target] if a.target else []) if {r.get(c, "").strip() for r in rows} - {""} <= {"0", "1", "0.0", "1.0"}}

    figs, md, hyps = [], [], []
    md += [f"# EDA 통계 요약", "", f"- 원본: `{a.path}` · {len(rows):,}행 {len(cols)}열 · 명령: `python3 scripts/eda_report.py {' '.join(sys.argv[1:])}`", ""]
    for c, vals in sent.items():
        msg = ", ".join(f"{v:g}({n}건)" for v, n in vals)
        md.append(f"- **결측 표시값 감지** `{c}`: {msg} → 결측으로 처리하고 통계 계산. 원본 정의 확인 필요")
        hyps.append(f"`{c}`에 결측 표시값 {msg}: 센서 오류·통신 끊김 시점이 특정 그룹·기간에 몰려 있는지 확인 (그 자체가 신호일 수 있음)")
    md.append("")

    # 1) 숫자 요약 + 히스토그램
    md += ["## 숫자 컬럼", "", "| 컬럼 | n | 결측 | 평균 | 표준편차 | 최소 | 25% | 중앙값 | 75% | 최대 | 왜도 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    summary = {}
    for c in numc + ([a.target] if tgt_num else []):
        xs = [x for x in (num(r.get(c)) for r in rows) if x is not None]
        d = describe(xs)
        if not d:
            continue
        summary[c] = d
        md.append(f"| {c} | {d['n']:,} | {len(rows) - d['n']:,} | {f(d['mean'])} | {f(d['sd'])} | {f(d['min'])} | {f(d['q1'])} | {f(d['med'])} | {f(d['q3'])} | {f(d['max'])} | {d['skew']:.2f} |")
        figs.append(("분포", histogram(c, xs)))
        if abs(d["skew"]) > 2 and c not in binary:
            hyps.append(f"`{c}` 왜도 {d['skew']:.1f}: 한쪽으로 긴 꼬리. 극단값·단위 오류 확인, 로그 변환이나 중앙값 기준 비교 고려")

    # 2) 범주 막대
    md += ["", "## 범주 컬럼", ""]
    for c in catc[:6]:
        cnt = Counter(r[c] for r in rows)
        md.append(f"- `{c}`: " + ", ".join(f"{k}={v:,}" for k, v in cnt.most_common(10)))
        figs.append(("범주", bars(f"{c} 빈도", [(k, v, "") for k, v in cnt.most_common(15)], fmt=lambda v: f"{v:,}")))

    # 3) 상관
    if len(numc) >= 2:
        allc = numc + ([a.target] if tgt_num else [])
        vecs = {c: [num(r.get(c)) for r in rows] for c in allc}
        mat = [[1.0 if i == j else pearson(vecs[x], vecs[y]) for j, y in enumerate(allc)] for i, x in enumerate(allc)]
        figs.append(("상관", heat(allc, mat)))
        strong = sorted(((abs(mat[i][j]), allc[i], allc[j], mat[i][j]) for i in range(len(allc)) for j in range(i + 1, len(allc)) if mat[i][j] is not None), reverse=True)[:5]
        md += ["", "## 상관 상위 (|r|)", ""] + [f"- {x} × {y}: r = {r:.2f}" for _, x, y, r in strong]
        for _, x, y, r in strong[:2]:
            if abs(r) >= 0.5 and a.target not in (x, y):
                hyps.append(f"`{x}`와 `{y}` 상관 r={r:.2f}: 같은 원인을 공유하거나 하나가 다른 하나의 결과일 수 있음. 모델에 같이 넣으면 해석이 흔들림")

    # 4) 타깃 관계
    if a.target:
        md += ["", f"## 타깃 `{a.target}` 관계", ""]
        ty = [num(r.get(a.target)) for r in rows]
        if tgt_num:
            ranks = []
            for c in numc:
                r_ = pearson([num(r.get(c)) for r in rows], ty)
                if r_ is not None:
                    ranks.append((abs(r_), c, r_))
            ranks.sort(reverse=True)
            figs.append(("타깃", bars(f"타깃과 상관 (|r| 순)", [(c, abs(r_), f"(r={r_:+.2f})") for _, c, r_ in ranks], fmt=lambda v: f"{v:.2f}")))
            md += [f"- {c}: r = {r_:+.2f}" for _, c, r_ in ranks[:8]]
            for _, c, r_ in ranks[:3]:
                if abs(r_) >= 0.2:
                    hyps.append(f"`{c}`가 타깃과 r={r_:+.2f}: 구간별 타깃 평균 그래프로 비선형·임계값 여부 확인, 시간 순서상 원인이 먼저인지 확인")
                # 구간별 타깃 평균 (5분위)
                pairs = sorted((x, y) for x, y in zip((num(r.get(c)) for r in rows), ty) if x is not None and y is not None)
                if len(pairs) >= 50:
                    k = 5
                    items = []
                    for b in range(k):
                        chunk = pairs[b * len(pairs) // k:(b + 1) * len(pairs) // k]
                        items.append((f"{f(chunk[0][0])}~{f(chunk[-1][0])}", st.fmean(y for _, y in chunk), f"n={len(chunk)}"))
                    figs.append(("타깃", bars(f"{c} 구간(5분위)별 타깃 평균", items, fmt=lambda v: f"{v:.3g}")))
        for c in catc[:4]:
            g = defaultdict(list)
            for r, y in zip(rows, ty):
                if y is not None:
                    g[r[c]].append(y)
            items = sorted(((k, st.fmean(v), f"n={len(v)}") for k, v in g.items() if len(v) >= 5), key=lambda t: -t[1])
            if len(items) >= 2:
                figs.append(("타깃", bars(f"{c}별 타깃 평균", items, fmt=lambda v: f"{v:.3g}")))
                md.append(f"- `{c}`별 타깃 평균: " + ", ".join(f"{k}={v:.3g}({e})" for k, v, e in items[:8]))
                hi_, lo_ = items[0], items[-1]
                if lo_[1] and hi_[1] / lo_[1] >= 1.5 or (lo_[1] == 0 and hi_[1] > 0):
                    hyps.append(f"`{c}`={hi_[0]}의 타깃 평균 {hi_[1]:.3g}가 {lo_[0]}({lo_[1]:.3g})보다 큼: 이 차이가 기간·다른 범주로 나눠도 유지되는지(심슨의 역설) 확인")

    # 5) 시간 추세 + 전후 비교
    if a.time:
        dated = [(date(r[a.time]), r) for r in rows]
        dated = [(d, r) for d, r in dated if d]
        if dated:
            t0 = min(d for d, _ in dated)
            split = datetime.strptime(a.split_date, "%Y-%m-%d") if a.split_date else t0 + (max(d for d, _ in dated) - t0) / 2
            md += ["", f"## 시간 (기준 {split:%Y-%m-%d %H:%M} 전후 비교)", "", "| 컬럼 | 그룹 | 이전 평균 | 이후 평균 | 차이 | 효과크기 d | 대략 t |", "|---|---|---|---|---|---|---|"]
            for c in (([a.target] if a.target and types.get(a.target) == "num" else []) + numc)[:6]:
                ser = defaultdict(lambda: defaultdict(list))
                for d, r in dated:
                    v = num(r.get(c))
                    if v is not None:
                        ser[r[a.group] if a.group else "전체"][(d - t0).days].append(v)
                series = {g: [(day, st.fmean(vs)) for day, vs in sorted(days.items())] for g, days in ser.items()}
                figs.append(("시간", lines(f"{c} 일평균 추세" + (f" ({a.group}별)" if a.group else "") + f" · x=시작일({t0:%m-%d})부터 일수", series)))
                for g in list(ser.keys())[:6]:
                    before = [v for d, r in dated if (not a.group or r[a.group] == g) and d < split for v in [num(r.get(c))] if v is not None]
                    after = [v for d, r in dated if (not a.group or r[a.group] == g) and d >= split for v in [num(r.get(c))] if v is not None]
                    w_ = welch(before, after)
                    if w_:
                        md.append(f"| {c} | {g} | {f(st.fmean(before))} | {f(st.fmean(after))} | {f(w_['diff'])} | {w_['d']:.2f} | {w_['t']:.1f} |")
                        if abs(w_["d"]) >= 0.5 and abs(w_["t"]) >= 3:
                            hyps.append(f"`{c}`({g})가 {split:%m-%d} 이후 평균 {f(w_['diff'])} 변화(d={w_['d']:.2f}): 변화 시점을 일 단위로 좁히고, 같은 시점 다른 그룹·다른 변수도 바뀌었는지 확인")

    # 출력
    md += ["", "## 자동 가설 후보 (검증 전, 사람이 판단)", ""]
    md += [f"- [ ] {h}" for h in hyps] or ["- 자동 추출된 후보 없음. 범주별·기간별로 직접 나눠 볼 것"]
    md += ["", "## 검증 계획 (사람이 채움)", "", "| 가설 | 검증 방법(나눠 보기·전후 비교·반례 찾기) | 결과 | 채택 |", "|---|---|---|---|", "| | | | |"]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    md_path = os.path.join(os.path.dirname(a.out) or ".", "eda_stats.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")

    order = ["타깃", "시간", "상관", "분포", "범주"]
    sections = "".join(
        f"<h2>{sec}</h2><div class='grid'>{''.join(s for k, s in figs if k == sec and s)}</div>" for sec in order if any(k == sec and s for k, s in figs))
    hyp_html = "".join(f"<li>{html.escape(h)}</li>" for h in hyps) or "<li>자동 추출된 후보 없음</li>"
    tbl = "".join(f"<tr><td>{html.escape(c)}</td><td>{d['n']:,}</td><td>{f(d['mean'])}</td><td>{f(d['sd'])}</td><td>{f(d['min'])}</td><td>{f(d['med'])}</td><td>{f(d['max'])}</td><td>{d['skew']:.2f}</td></tr>" for c, d in summary.items())
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EDA · {html.escape(os.path.basename(a.path))}</title><style>
:root{{--bg:#f6f7f9;--panel:#fff;--ink:#1d2430;--muted:#5f6b7a;--line:#d9dee5}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 -apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:20px 16px 60px}} h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:16px;margin:26px 0 8px}}
.sub{{color:var(--muted);margin:0 0 14px}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:12px}}
figure{{margin:0;background:var(--panel);border:1px solid var(--line);padding:10px}} figcaption{{font-weight:600;font-size:13px;margin-bottom:4px}}
svg{{width:100%;height:auto}} .ax{{stroke:#8a94a3}} .grid line,.grid{{}} line.grid{{stroke:#e8ebef}} .tick{{font-size:10px;fill:var(--muted)}}
table{{border-collapse:collapse;background:var(--panel);font-variant-numeric:tabular-nums;width:100%}} th,td{{border-bottom:1px solid var(--line);padding:5px 8px;text-align:right}} th:first-child,td:first-child{{text-align:left}}
.hyp{{background:var(--panel);border:1px solid var(--line);padding:10px 14px 10px 30px}} .tw{{overflow-x:auto}}
</style></head><body><main>
<h1>EDA · {html.escape(os.path.basename(a.path))}</h1>
<p class="sub">{len(rows):,}행 · {len(cols)}열 · 타깃 {html.escape(a.target or '-')} · 시간 {html.escape(a.time or '-')} · 그룹 {html.escape(a.group or '-')} · 상세 숫자는 {html.escape(os.path.basename(md_path))}</p>
<h2>가설 후보 (자동, 검증 전)</h2><ol class="hyp">{hyp_html}</ol>
<h2>숫자 요약</h2><div class="tw"><table><tr><th>컬럼</th><th>n</th><th>평균</th><th>표준편차</th><th>최소</th><th>중앙값</th><th>최대</th><th>왜도</th></tr>{tbl}</table></div>
{sections}
</main></body></html>"""
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"그래프 {sum(1 for _, s in figs if s)}개, 가설 후보 {len(hyps)}개 → {a.out}, {md_path}")


if __name__ == "__main__":
    main()
