from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from random import Random

from vending_machine.app.dto import DomainEvent
from vending_machine.domain.models import Session
from vending_machine.infra.excel_repository import ExcelMachineRepository


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    template = root / "data" / "vending_machine_template.xlsx"
    demo = root / "data" / "vending_machine_gui_demo.xlsx"
    if not template.exists():
        raise FileNotFoundError(f"먼저 템플릿을 생성해 주세요: {template}")

    demo.write_bytes(template.read_bytes())
    repo = ExcelMachineRepository(demo)
    state = repo.load_state()
    rng = Random(42)
    events: list[DomainEvent] = []
    products = list(sorted(state.products.values(), key=lambda p: p.slot_no or 0))

    base_dt = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    for day_back in range(34, -1, -1):
        target_day = base_dt - timedelta(days=day_back)
        order_count = rng.randint(3, 10)
        for idx in range(order_count):
            sold_at = target_day + timedelta(minutes=35 * idx + rng.randint(0, 25))
            product = rng.choices(products, weights=[8, 12, 9, 7, 10, 6], k=1)[0]
            paid_options = [product.price, product.price + 100, product.price + 500, product.price + 1000]
            paid_amount = rng.choice([value for value in paid_options if value >= product.price])
            change_amount = paid_amount - product.price
            sale_id = f"SALE-SEED-{sold_at.strftime('%Y%m%d%H%M%S')}-{idx}"
            events.append(
                DomainEvent(
                    sheet_name="sales_log",
                    payload={
                        "sale_id": sale_id,
                        "sold_at": sold_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "product_id": product.product_id,
                        "product_name": product.name,
                        "unit_price": product.price,
                        "qty": 1,
                        "paid_amount": paid_amount,
                        "change_amount": change_amount,
                        "result": "SUCCESS",
                    },
                )
            )
            if change_amount:
                remaining = change_amount
                for denom in (1000, 500, 100, 50, 10):
                    qty, remaining = divmod(remaining, denom)
                    if qty:
                        events.append(
                            DomainEvent(
                                sheet_name="cash_log",
                                payload={
                                    "cash_event_id": f"CASH-SEED-{sale_id}-{denom}",
                                    "event_at": sold_at.strftime("%Y-%m-%d %H:%M:%S"),
                                    "event_type": "DISPENSE_CHANGE",
                                    "denomination": denom,
                                    "qty": qty,
                                    "amount": denom * qty,
                                    "note": f"seed_change:{product.product_id}",
                                },
                            )
                        )
        # Add occasional cash inserts for realism
        for denom, qty in ((1000, rng.randint(4, 8)), (500, rng.randint(2, 5)), (100, rng.randint(2, 4))):
            events.append(
                DomainEvent(
                    sheet_name="cash_log",
                    payload={
                        "cash_event_id": f"CASH-INSERT-{target_day.strftime('%Y%m%d')}-{denom}",
                        "event_at": target_day.strftime("%Y-%m-%d %H:%M:%S"),
                        "event_type": "INSERT",
                        "denomination": denom,
                        "qty": qty,
                        "amount": denom * qty,
                        "note": "seed_insert",
                    },
                )
            )

    # Tune current stock for dashboard warnings
    state.products["P004"].stock = 2
    state.products["P006"].stock = 1
    repo.commit(state, Session(), events)
    print(f"created: {demo}")


if __name__ == "__main__":
    main()
