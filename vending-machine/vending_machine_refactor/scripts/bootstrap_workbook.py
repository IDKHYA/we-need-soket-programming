from __future__ import annotations

from pathlib import Path

from vending_machine.domain.models import CashInventory, Product
from vending_machine.infra.excel_repository import ExcelMachineRepository
from vending_machine.infra.security import PasswordHasher


PRODUCTS = [
    Product("P001", "커피", 2200, 6, 10, True, "images/coffee_cup.jpg", 1),
    Product("P002", "물", 1000, 8, 10, True, "images/water.jpg", 2),
    Product("P003", "이온음료", 1800, 7, 10, True, "images/ion_drink.jpg", 3),
    Product("P004", "레쓰비", 1200, 5, 10, True, "images/letsbe.jpg", 4),
    Product("P005", "사이다", 1300, 4, 10, True, "images/cider.jpg", 5),
    Product("P006", "특화음료", 2500, 3, 10, True, "images/special_drink.jpg", 6),
]


def main() -> None:
    workbook_path = Path("data/vending_machine_template.xlsx")
    repo = ExcelMachineRepository(workbook_path)

    cash_inventory = CashInventory(
        counts={10: 30, 50: 25, 100: 25, 500: 20, 1000: 12},
        min_keep={10: 15, 50: 10, 100: 10, 500: 8, 1000: 5},
        max_capacity={10: 300, 50: 250, 100: 250, 500: 200, 1000: 80},
    )
    config = {
        "admin_password_hash": PasswordHasher().hash_password("admin!12345"),
        "currency_unit": "KRW",
        "refund_strategy": "exact_only",
        "legacy_source": "pyside_gui_ready",
        "theme": "midnight_blue_metal",
        "machine_id": "VM-A",
        "server_id": "server1",
        "server_api_base_url": "",
        "network_enabled": "Y",
    }
    repo.create_template(products=PRODUCTS, cash_inventory=cash_inventory, config=config)
    print(f"created: {workbook_path}")


if __name__ == "__main__":
    main()
