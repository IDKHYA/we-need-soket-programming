# 자판기 리팩터링 프로젝트

이 프로젝트는 기존 txt 기반 자판기 프로그램을 Python 패키지 구조로 다시 정리한 버전입니다.
핵심은 단일 스크립트가 아니라 `domain + app + infra + presentation` 계층으로 분리되어 있고,
저장소는 DB 대신 Excel 워크북을 사용한다는 점입니다.

현재 폴더 기준 실제 구현은 다음 성격을 가집니다.

- 엑셀 파일을 DB처럼 사용하는 로컬 자판기 운영 시스템
- CLI와 PySide6 GUI를 함께 제공하는 실행형 프로젝트
- 판매, 현금 흐름, 재고, 관리자 작업을 로그로 남기는 구조
- 관리자 대시보드와 통계 화면까지 포함한 시연 가능한 GUI

## 현재 구현된 핵심 기능

- 동전과 지폐 투입
  - 지원 단위: `10, 50, 100, 500, 1000, 5000, 10000, 50000`
- 상품 구매
- 환불
- 구매 후 잔액 유지
  - 예: `1000 x3 + 500 x2 = 4000원` 투입 후 `1800원` 음료 구매 시 `2200원`이 남고 계속 추가 투입 가능
- 세션 상태의 엑셀 저장 및 재로딩
- 상품 최대치 보충
- 현금 최소 유지 수량 기준 보충
- 현금 수거
- 관리자 비밀번호 검증 및 변경
- 상품 정보 수정 및 수동 재고 조정
- 판매/현금/재고/감사 로그 기록
- 일별/월별/상품별 매출 리포트
- 현금 흐름 리포트 및 저재고 조회
- 파일 잠금과 atomic save 기반 안전 저장

## 현재 미구현 또는 주의할 점

- 소켓 프로그래밍 기반 클라이언트-서버 구조는 현재 폴더에 구현되어 있지 않습니다.
- 저장소가 Excel 단일 파일이므로 다중 사용자 동시 접근과 대량 로그 처리에는 한계가 있습니다.
- GUI는 현재 동작하지만, 실행 환경에 따라 `PySide6.QtCharts` DLL 문제가 있을 수 있습니다.
- 테스트 파일은 존재하지만, 환경에 `pytest`가 없으면 전체 테스트 실행은 되지 않습니다.

## 아키텍처

```text
src/vending_machine/
├─ domain/
│  ├─ models.py
│  ├─ change.py
│  └─ exceptions.py
├─ app/
│  ├─ dto.py
│  ├─ service.py
│  └─ report_service.py
├─ infra/
│  ├─ excel_repository.py
│  ├─ file_lock.py
│  └─ security.py
└─ presentation/
   ├─ cli.py
   └─ pyside_gui.py
```

- `domain`
  - 상품, 현금 재고, 세션, 거스름돈 계산 같은 핵심 규칙을 담당합니다.
- `app`
  - 구매, 환불, 관리자 기능, 리포트 같은 유스케이스를 담당합니다.
- `infra`
  - 엑셀 저장소, 파일 잠금, 비밀번호 해시를 담당합니다.
- `presentation`
  - CLI와 PySide6 GUI를 담당합니다.

## 주요 도메인 구성

### Product

- 상품 식별자, 이름, 가격, 재고, 최대 재고를 가집니다.
- 판매 가능 여부 판단
- 재고 감소
- 최대치 보충

### CashInventory

- 화폐 단위별 수량
- 최소 유지 수량
- 최대 적재 수량
- 수거 가능한 수량 계산

### Session

- 현재 사용자 투입 금액을 관리합니다.
- 구매 시 전체 세션을 비우지 않고 금액만 차감합니다.
- 따라서 남은 금액으로 추가 구매나 추가 투입이 가능합니다.

### ChangeCalculator

- 단순 greedy가 아니라 DFS + memo 방식으로 정확한 거스름돈 조합을 찾습니다.
- 재고 제한을 고려한 정확한 잔돈 계산에 사용됩니다.

## 애플리케이션 서비스

### VendingMachineService

주요 메서드:

- `insert_cash`
- `purchase`
- `refund`
- `refill_product_to_max`
- `refill_cash_to_minimum`
- `collect_cash`
- `set_admin_password`
- `adjust_product_stock`
- `update_product`

구매 시 처리 흐름:

1. 상품 조회
2. 품절 여부 확인
3. 잔액 확인
4. 재고 차감
5. 세션 금액 차감
6. 판매/재고 로그 생성

### SalesReportService

다음 데이터를 계산합니다.

- 일별 매출
- 월별 매출
- 상품별 매출
- 현금 흐름
- 요약 지표
- 저재고 상품 목록

## 엑셀 저장소 구조

저장소 구현은 [src/vending_machine/infra/excel_repository.py](src/vending_machine/infra/excel_repository.py)에 있습니다.

워크북 시트는 총 8개입니다.

- `products`
- `cash_inventory`
- `machine_config`
- `session_state`
- `sales_log`
- `cash_log`
- `stock_log`
- `audit_log`

### session_state

현재 세션 정보를 저장합니다.

- `inserted_total`
- `inserted_10`
- `inserted_50`
- `inserted_100`
- `inserted_500`
- `inserted_1000`
- `inserted_5000`
- `inserted_10000`
- `inserted_50000`

### 로그 시트

아래 시트는 append-only 로그처럼 사용됩니다.

- `sales_log`
- `cash_log`
- `stock_log`
- `audit_log`

즉, 누적 통계를 직접 수정하기보다 로그를 읽어 리포트를 계산하는 구조입니다.

## GUI

PySide6 GUI는 [src/vending_machine/presentation/pyside_gui.py](src/vending_machine/presentation/pyside_gui.py)에 있습니다.

구성 요소:

- 사용자용 자판기 화면
- 상품 카드 목록
- 금액 표시부
- 동전/지폐 투입 버튼
- 환불 버튼
- 관리자 모드 버튼
- 관리자 대시보드

관리자 대시보드 특징:

- 통계 탭
- 상품 관리 탭
- 현금 관리 탭
- 일별 매출 차트
- 상품 매출 비중 차트
- 현금 흐름 차트
- 누적 매출 추이
- 저재고 목록

현재 GUI에서는 관리자 모드가 열려 있는 동안 자판기 입력을 잠시 멈추도록 되어 있습니다.

## CLI

CLI는 [src/vending_machine/presentation/cli.py](src/vending_machine/presentation/cli.py)에 있습니다.

예시:

```bash
python -m vending_machine.presentation.cli --workbook data/vending_machine.xlsx list
python -m vending_machine.presentation.cli --workbook data/vending_machine.xlsx status
python -m vending_machine.presentation.cli --workbook data/vending_machine.xlsx insert --amount 5000
python -m vending_machine.presentation.cli --workbook data/vending_machine.xlsx buy --product-id P002
python -m vending_machine.presentation.cli --workbook data/vending_machine.xlsx refund
python -m vending_machine.presentation.cli --workbook data/vending_machine.xlsx report-daily
```

관리자 명령 예시:

```bash
python -m vending_machine.presentation.cli --workbook data/vending_machine.xlsx admin-refill-product --product-id P002 --password admin!12345
python -m vending_machine.presentation.cli --workbook data/vending_machine.xlsx admin-refill-cash --password admin!12345
python -m vending_machine.presentation.cli --workbook data/vending_machine.xlsx admin-collect-cash --password admin!12345 --keep-minimum Y
python -m vending_machine.presentation.cli --workbook data/vending_machine.xlsx admin-update-product --product-id P001 --price 600 --name 생수 --password admin!12345
```

## 실행 방법

### 1. 설치

```bash
pip install -e .
```

필요 시:

```bash
pip install openpyxl PySide6
```

### 2. 기본 워크북 생성

```bash
python scripts/bootstrap_workbook.py
```

### 3. 데모 데이터 생성

```bash
python scripts/seed_demo_analytics.py
```

### 4. GUI 실행

가장 간단한 방법:

```bash
python run_gui.py
```

또는 직접 실행:

```bash
python -m vending_machine.presentation.pyside_gui data/vending_machine_gui_demo.xlsx
```

기본 관리자 비밀번호는 `admin!12345` 입니다.

## 테스트

테스트 파일은 `tests/` 아래에 있습니다.

현재 포함된 검증 범위:

- 잔돈 계산 정확성
- 구매 성공/실패
- 세션 저장
- 구매 후 잔액 유지
- 리포트 계산
- 감사 로그 기록
- 파일 잠금 정리

실행:

```bash
pytest
```

## 레거시 자산과 마이그레이션

프로젝트에는 과거 txt 기반 자산이 `legacy/` 폴더에 남아 있습니다.

- `drinks.txt`
- `coins.txt`
- `password.txt`
- `sales.txt`
- `transaction.txt`
- `sales_cycle.txt`

이를 엑셀 워크북으로 옮기기 위한 스크립트:

```bash
python scripts/migrate_from_legacy_txt.py
```

## 참고

- 이 프로젝트의 현재 정체성은 "txt 기반 자판기 프로그램을 Excel 기반 구조로 이관한 리팩터링판"에 가깝습니다.
- 소켓 통신이나 분산 서버 구조는 현재 구현 범위에 포함되지 않습니다.
