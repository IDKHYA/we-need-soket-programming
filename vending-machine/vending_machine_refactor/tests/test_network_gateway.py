from pathlib import Path

from vending_machine.app.service import VendingMachineService
from vending_machine.domain.models import CashInventory, MachineState, Product, Session
from vending_machine.infra.excel_repository import ExcelMachineRepository
from vending_machine.infra.security import PasswordHasher
from vending_machine.network.runtime import commit_local_and_publish


def make_repo(tmp_path: Path) -> tuple[ExcelMachineRepository, Path]:
    workbook = tmp_path / 'vm.xlsx'
    repo = ExcelMachineRepository(workbook)
    repo.create_template(
        products=[Product('P001', '샘물', 500, 5, 20)],
        cash_inventory=CashInventory(
            counts={10: 10, 50: 10, 100: 10, 500: 10, 1000: 10},
            min_keep={10: 10, 50: 10, 100: 10, 500: 10, 1000: 10},
            max_capacity={10: 200, 50: 200, 100: 200, 500: 200, 1000: 50},
        ),
        config={
            'admin_password_hash': PasswordHasher().hash_password('admin!1234'),
            'machine_id': 'VM-A',
            'server_id': 'server1',
            'server_api_base_url': 'http://127.0.0.1:65530',
        },
    )
    return repo, workbook


def test_commit_local_and_publish_keeps_local_commit_and_queues_pending_events(tmp_path: Path):
    repo, workbook = make_repo(tmp_path)
    state = repo.load_state()
    session = Session()
    service = VendingMachineService(state=state, session=session)

    result = service.insert_cash(500)
    commit_local_and_publish(repo, workbook, service.state, service.session, result.cash_events)

    reloaded = repo.load_session()
    assert reloaded.inserted_total == 500

    queue_path = workbook.with_suffix('.network_queue.json')
    assert queue_path.exists()
    content = queue_path.read_text(encoding='utf-8')
    assert 'VM-A' in content
    assert 'CASH-' in content
