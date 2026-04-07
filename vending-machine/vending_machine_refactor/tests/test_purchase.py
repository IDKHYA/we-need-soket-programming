from vending_machine.app.service import VendingMachineService
from vending_machine.domain.models import CashInventory, MachineState, Product, Session
from vending_machine.infra.security import PasswordHasher


def make_service() -> VendingMachineService:
    state = MachineState(
        products={
            "P001": Product("P001", "샘물", 480, 5, 20),
            "P002": Product("P002", "커피", 500, 5, 20),
        },
        cash_inventory=CashInventory(
            counts={10: 10, 50: 10, 100: 10, 500: 10, 1000: 10},
            min_keep={10: 10, 50: 10, 100: 10, 500: 10, 1000: 10},
            max_capacity={10: 200, 50: 200, 100: 200, 500: 200, 1000: 50},
        ),
        config={
            "admin_password_hash": PasswordHasher().hash_password("admin!1234")
        },
    )
    session = Session()
    return VendingMachineService(state=state, session=session)


def test_purchase_success():
    svc = make_service()
    svc.insert_cash(1000)
    result = svc.purchase("P002")

    assert result.success is True
    assert result.dispensed_change == {}
    assert svc.state.products["P002"].stock == 4
    assert svc.session.inserted_total == 500
    assert result.remaining_balance == 500


def test_purchase_keeps_remaining_balance_and_allows_more_cash():
    svc = VendingMachineService(
        state=MachineState(
            products={
                "P003": Product("P003", "이온음료", 1800, 5, 20),
            },
            cash_inventory=CashInventory(
                counts={10: 10, 50: 10, 100: 10, 500: 10, 1000: 10},
                min_keep={10: 10, 50: 10, 100: 10, 500: 10, 1000: 10},
                max_capacity={10: 200, 50: 200, 100: 200, 500: 200, 1000: 50},
            ),
            config={
                "admin_password_hash": PasswordHasher().hash_password("admin!1234")
            },
        ),
        session=Session(),
    )
    svc.insert_cash(1000)
    svc.insert_cash(1000)
    svc.insert_cash(1000)
    svc.insert_cash(500)
    svc.insert_cash(500)

    result = svc.purchase("P003")

    assert result.success is True
    assert svc.session.inserted_total == 2200
    assert result.remaining_balance == 2200

    second_insert = svc.insert_cash(1000)
    assert second_insert.current_balance == 3200
    assert svc.session.inserted_total == 3200


def test_insert_cash_enforces_bill_and_total_limits():
    svc = make_service()
    for _ in range(5):
        svc.insert_cash(1000)

    try:
        svc.insert_cash(1000)
        assert False, "1000원권은 누적 5000원을 넘기면 안 됩니다."
    except ValueError as exc:
        assert "5000원" in str(exc)

    svc = make_service()
    for amount in [1000, 1000, 1000, 1000, 1000, 500, 500, 500, 500]:
        svc.insert_cash(amount)

    try:
        svc.insert_cash(10)
        assert False, "총 투입 금액은 7000원을 넘기면 안 됩니다."
    except ValueError as exc:
        assert "7000원" in str(exc)


def test_purchase_insufficient_balance():
    svc = make_service()
    svc.insert_cash(100)
    result = svc.purchase("P002")

    assert result.success is False
    assert result.code == "INSUFFICIENT_BALANCE"
