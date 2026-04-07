from pathlib import Path

from vending_machine.app.service import VendingMachineService
from vending_machine.domain.models import CashInventory, MachineState, Product, Session
from vending_machine.infra.excel_repository import ExcelMachineRepository
from vending_machine.infra.security import PasswordHasher


def make_repo(tmp_path: Path) -> ExcelMachineRepository:
    repo = ExcelMachineRepository(tmp_path / "vm.xlsx")
    repo.create_template(
        products=[Product("P001", "샘물", 480, 5, 20)],
        cash_inventory=CashInventory(
            counts={10: 10, 50: 10, 100: 10, 500: 10, 1000: 10},
            min_keep={10: 10, 50: 10, 100: 10, 500: 10, 1000: 10},
            max_capacity={10: 200, 50: 200, 100: 200, 500: 200, 1000: 50},
        ),
        config={"admin_password_hash": PasswordHasher().hash_password("admin!1234")},
    )
    return repo


def test_session_persists_across_repository_reload(tmp_path: Path):
    repo = make_repo(tmp_path)
    state = repo.load_state()
    session = repo.load_session()
    service = VendingMachineService(state=state, session=session)

    result = service.insert_cash(500)
    repo.commit(service.state, service.session, result.cash_events)

    reloaded_session = repo.load_session()
    assert reloaded_session.inserted_total == 500
    assert reloaded_session.inserted_breakdown[500] == 1


def test_commit_writes_sale_log_and_keeps_remaining_session_balance(tmp_path: Path):
    repo = make_repo(tmp_path)
    state = repo.load_state()
    session = repo.load_session()
    service = VendingMachineService(state=state, session=session)

    service.insert_cash(500)
    result = service.purchase("P001")
    repo.commit(service.state, service.session, result.sale_events + result.cash_events + result.stock_events)

    reloaded_state = repo.load_state()
    reloaded_session = repo.load_session()

    assert reloaded_state.products["P001"].stock == 4
    assert reloaded_session.inserted_total == 20
    assert reloaded_session.inserted_breakdown[10] == 2
