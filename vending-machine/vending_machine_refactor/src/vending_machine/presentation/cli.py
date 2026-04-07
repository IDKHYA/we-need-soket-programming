from __future__ import annotations

import argparse
from pathlib import Path

from vending_machine.app.report_service import SalesReportService
from vending_machine.app.service import VendingMachineService
from vending_machine.infra.excel_repository import ExcelMachineRepository
from vending_machine.network.runtime import commit_local_and_publish


ADMIN_COMMANDS = {
    "admin-refill-product",
    "admin-collect-cash",
    "admin-refill-cash",
    "admin-set-password",
    "admin-update-product",
}
REPORT_COMMANDS = {
    "report-daily",
    "report-monthly",
    "report-product",
    "report-cashflow",
    "low-stock",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Vending machine CLI")
    parser.add_argument("--workbook", required=True, help="xlsx 파일 경로")
    parser.add_argument(
        "command",
        choices=[
            "list",
            "status",
            "insert",
            "buy",
            "refund",
            "admin-refill-product",
            "admin-collect-cash",
            "admin-refill-cash",
            "admin-set-password",
            "admin-update-product",
            "report-daily",
            "report-monthly",
            "report-product",
            "report-cashflow",
            "low-stock",
        ],
    )
    parser.add_argument("--amount", type=int)
    parser.add_argument("--product-id")
    parser.add_argument("--password")
    parser.add_argument("--actor", default="admin")
    parser.add_argument("--new-password")
    parser.add_argument("--name")
    parser.add_argument("--price", type=int)
    parser.add_argument("--max-stock", type=int)
    parser.add_argument("--active", choices=["Y", "N"])
    parser.add_argument("--image-path")
    parser.add_argument("--slot-no", type=int)
    parser.add_argument("--keep-minimum", choices=["Y", "N"], default="Y")
    parser.add_argument("--threshold", type=int, default=0)
    args = parser.parse_args()

    workbook_path = Path(args.workbook)
    repo = ExcelMachineRepository(workbook_path)

    if args.command in REPORT_COMMANDS:
        _handle_report(repo, args)
        return

    state = repo.load_state()
    session = repo.load_session()
    service = VendingMachineService(state=state, session=session)

    if args.command in ADMIN_COMMANDS:
        _require_admin(service, args.password)

    if args.command == "list":
        for product in state.products.values():
            print(f"{product.product_id}: {product.name} {product.price}원 재고={product.stock} 활성={product.active}")
        return

    if args.command == "status":
        print(f"현재 투입금액: {service.session.inserted_total}원")
        breakdown = {k: v for k, v in sorted(service.session.inserted_breakdown.items()) if v > 0}
        print(f"세션 화폐 구성: {breakdown or '{}'}")
        print(f"자판기 전체 현금: {service.state.cash_inventory.total_amount()}원")
        return

    if args.command == "insert":
        if args.amount is None:
            raise SystemExit("--amount 값이 필요합니다.")
        result = service.insert_cash(args.amount)
        commit_local_and_publish(repo, workbook_path, service.state, service.session, result.cash_events)
        print(result.message)
        print(f"현재 투입금액: {result.current_balance}원")
        return

    if args.command == "buy":
        if args.product_id is None:
            raise SystemExit("--product-id 값이 필요합니다.")
        result = service.purchase(args.product_id)
        commit_local_and_publish(
            repo,
            workbook_path,
            service.state,
            service.session,
            result.sale_events + result.cash_events + result.stock_events,
        )
        print(result.message)
        if result.dispensed_change:
            print(f"거스름돈: {result.dispensed_change}")
        return

    if args.command == "refund":
        result = service.refund()
        commit_local_and_publish(repo, workbook_path, service.state, service.session, result.cash_events)
        print(result.message)
        if result.refunded_breakdown:
            print(f"반환 상세: {result.refunded_breakdown}")
        return

    if args.command == "admin-refill-product":
        if args.product_id is None:
            raise SystemExit("--product-id 값이 필요합니다.")
        events = service.refill_product_to_max(args.product_id, actor=args.actor)
        commit_local_and_publish(repo, workbook_path, service.state, service.session, events)
        print(f"{args.product_id} 재고를 최대치로 보충했습니다.")
        return

    if args.command == "admin-collect-cash":
        keep_minimum = args.keep_minimum == "Y"
        events = service.collect_cash(keep_minimum=keep_minimum, actor=args.actor)
        commit_local_and_publish(repo, workbook_path, service.state, service.session, events)
        print("현금 수거 완료")
        return

    if args.command == "admin-refill-cash":
        events = service.refill_cash_to_minimum(actor=args.actor)
        commit_local_and_publish(repo, workbook_path, service.state, service.session, events)
        print("최소 유지 수량 기준으로 현금 보충 완료")
        return

    if args.command == "admin-set-password":
        if not args.new_password:
            raise SystemExit("--new-password 값이 필요합니다.")
        events = service.set_admin_password(args.new_password, actor=args.actor)
        commit_local_and_publish(repo, workbook_path, service.state, service.session, events)
        print("관리자 비밀번호 변경 완료")
        return

    if args.command == "admin-update-product":
        if args.product_id is None:
            raise SystemExit("--product-id 값이 필요합니다.")
        active = None if args.active is None else args.active == "Y"
        events = service.update_product(
            args.product_id,
            name=args.name,
            price=args.price,
            max_stock=args.max_stock,
            active=active,
            image_path=args.image_path,
            slot_no=args.slot_no,
            actor=args.actor,
        )
        commit_local_and_publish(repo, workbook_path, service.state, service.session, events)
        print(f"{args.product_id} 상품 정보 수정 완료")
        return


def _require_admin(service: VendingMachineService, password: str | None) -> None:
    if password is None:
        raise SystemExit("관리자 명령에는 --password 값이 필요합니다.")
    if not service.authenticate_admin(password):
        raise SystemExit("관리자 인증에 실패했습니다.")


def _handle_report(repo: ExcelMachineRepository, args: argparse.Namespace) -> None:
    report = SalesReportService(repo)

    if args.command == "report-daily":
        for row in report.daily_sales():
            print(f"{row.date} | 건수={row.sales_count} | 수량={row.units_sold} | 매출={row.net_sales}원")
        return

    if args.command == "report-monthly":
        for row in report.monthly_sales():
            print(f"{row.month} | 건수={row.sales_count} | 수량={row.units_sold} | 매출={row.net_sales}원")
        return

    if args.command == "report-product":
        for row in report.product_sales():
            print(f"{row.product_id} {row.product_name} | 판매수량={row.units_sold} | 매출={row.net_sales}원")
        return

    if args.command == "report-cashflow":
        for row in report.cash_flow():
            print(f"{row.event_type} | 이벤트수={row.event_count} | 수량={row.total_qty} | 금액={row.total_amount}원")
        return

    if args.command == "low-stock":
        for row in report.low_stock_products(threshold=args.threshold):
            print(f"{row['product_id']} {row['name']} | 재고={row['stock']} | 가격={row['price']}원")
        return


if __name__ == "__main__":
    main()
