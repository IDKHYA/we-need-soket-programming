from __future__ import annotations

import csv
from pathlib import Path

from vending_machine.domain.models import CashInventory, Product
from vending_machine.infra.excel_repository import ExcelMachineRepository
from vending_machine.infra.security import PasswordHasher


def read_drinks(path: Path) -> list[Product]:
    products = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            name, price, stock = [part.strip() for part in line.split(",")]
            products.append(
                Product(
                    product_id=f"P{idx:03d}",
                    name=name,
                    price=int(price),
                    stock=int(stock),
                    max_stock=20,
                    active=True,
                    image_path=f"images/P{idx:03d}.jpg",
                    slot_no=idx,
                )
            )
    return products


def read_coins(path: Path) -> CashInventory:
    counts = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            denom, count = [part.strip() for part in line.split(",")]
            counts[int(denom)] = int(count)
    min_keep = {10: 10, 50: 10, 100: 10, 500: 10, 1000: 10}
    max_capacity = {10: 200, 50: 200, 100: 200, 500: 200, 1000: 50}
    return CashInventory(counts=counts, min_keep=min_keep, max_capacity=max_capacity)


def read_password_hash(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raw = "admin!12345"
    return PasswordHasher().hash_password(raw)


def main() -> None:
    legacy_dir = Path("legacy")
    workbook_path = Path("data/vending_machine.xlsx")
    repo = ExcelMachineRepository(workbook_path)

    products = read_drinks(legacy_dir / "drinks.txt")
    cash_inventory = read_coins(legacy_dir / "coins.txt")
    config = {
        "admin_password_hash": read_password_hash(legacy_dir / "password.txt"),
        "currency_unit": "KRW",
        "refund_strategy": "exact_only",
        "legacy_source": str(legacy_dir.resolve()),
    }
    repo.create_template(products=products, cash_inventory=cash_inventory, config=config)
    print(f"migrated workbook created: {workbook_path}")


if __name__ == "__main__":
    main()
