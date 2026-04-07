from pathlib import Path

from vending_machine.app.report_service import SalesReportService
from vending_machine.app.service import VendingMachineService
from vending_machine.domain.models import CashInventory, Product
from vending_machine.infra.excel_repository import ExcelMachineRepository
from vending_machine.infra.security import PasswordHasher


def make_repo(tmp_path: Path) -> ExcelMachineRepository:
    repo = ExcelMachineRepository(tmp_path / "vm.xlsx")
    repo.create_template(
        products=[
            Product("P001", "샘물", 500, 5, 20, slot_no=1),
            Product("P002", "커피", 700, 3, 20, slot_no=2),
        ],
        cash_inventory=CashInventory(
            counts={10: 10, 50: 10, 100: 10, 500: 10, 1000: 10},
            min_keep={10: 10, 50: 10, 100: 10, 500: 10, 1000: 10},
            max_capacity={10: 200, 50: 200, 100: 200, 500: 200, 1000: 50},
        ),
        config={"admin_password_hash": PasswordHasher().hash_password("Admin!1234")},
    )
    return repo


def test_report_service_summarizes_sales_and_cashflow(tmp_path: Path):
    repo = make_repo(tmp_path)
    state = repo.load_state()
    session = repo.load_session()
    service = VendingMachineService(state=state, session=session)

    insert_result = service.insert_cash(1000)
    repo.commit(service.state, service.session, insert_result.cash_events)

    state = repo.load_state()
    session = repo.load_session()
    service = VendingMachineService(state=state, session=session)
    result = service.purchase("P001")
    repo.commit(service.state, service.session, result.sale_events + result.cash_events + result.stock_events)

    report = SalesReportService(repo)
    daily = report.daily_sales()
    monthly = report.monthly_sales()
    product = report.product_sales()
    cashflow = report.cash_flow()

    assert len(daily) == 1
    assert daily[0].net_sales == 500
    assert len(monthly) == 1
    assert monthly[0].net_sales == 500
    assert product[0].product_id == "P001"
    assert product[0].units_sold == 1

    cashflow_by_type = {row.event_type: row for row in cashflow}
    assert cashflow_by_type["INSERT"].total_amount == 1000


def test_admin_actions_write_audit_log(tmp_path: Path):
    repo = make_repo(tmp_path)
    state = repo.load_state()
    session = repo.load_session()
    service = VendingMachineService(state=state, session=session)

    events = []
    events += service.update_product("P001", price=600, actor="tester")
    events += service.refill_product_to_max("P002", actor="tester")
    events += service.set_admin_password("Newpass!123", actor="tester")
    repo.commit(service.state, service.session, events)

    audit_rows = repo.read_sheet_rows(repo.AUDIT_LOG_SHEET)
    actions = [row["action"] for row in audit_rows]

    assert "PRODUCT_UPDATED" in actions
    assert "PRODUCT_REFILL_TO_MAX" in actions
    assert "PASSWORD_CHANGED" in actions


def test_file_lock_is_cleaned_after_commit(tmp_path: Path):
    repo = make_repo(tmp_path)
    state = repo.load_state()
    session = repo.load_session()
    service = VendingMachineService(state=state, session=session)

    result = service.insert_cash(500)
    repo.commit(service.state, service.session, result.cash_events)

    assert not (tmp_path / "vm.xlsx.lock").exists()


def test_stale_lock_file_is_removed_automatically(tmp_path: Path):
    repo = make_repo(tmp_path)
    lock_path = tmp_path / "vm.xlsx.lock"
    lock_path.write_text("999999", encoding="utf-8")

    state = repo.load_state()

    assert state.products["P001"].product_id == "P001"
    assert not lock_path.exists()
