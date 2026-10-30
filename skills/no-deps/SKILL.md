---
name: no-deps
description: pandas·sklearn·matplotlib 같은 패키지가 없고 설치도 안 될 때 표준 라이브러리로 대체하는 방법이 필요할 때 사용
---
- CSV: csv.DictReader. 숫자 변환은 함수 하나로 통일한다(빈 문자열 → None).
- XLSX: zipfile로 열어 xl/worksheets/sheet1.xml과 xl/sharedStrings.xml을 xml.etree로 파싱한다. 안 되면 사용자에게 CSV 변환을 요청한다.
- 집계·통계: collections.Counter / defaultdict, statistics(mean, median, stdev, quantiles).
- 조인: dict로 키 매핑. 그룹별 집계: defaultdict(list).
- 베이스라인: 상수 예측, 규칙, 그룹 평균. 선형회귀는 2~3변수까지 최소제곱을 직접 구현. 분류는 그룹 비율·임계값 규칙.
- 지표 직접 구현: accuracy, precision/recall/F1, MAE/RMSE, 혼동행렬.
- 시계열 이상: 이동평균·표준편차, 분위수.
- 차트: inline SVG 문자열 생성(막대·선).
- DB가 필요하면 sqlite3, HTTP는 urllib.request, 테스트는 unittest.
- numpy만 있어도 적극 사용한다. pip 설치가 가능해지면 사용자 승인 후 설치한다.
