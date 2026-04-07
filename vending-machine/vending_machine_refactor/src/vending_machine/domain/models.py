from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .exceptions import OutOfStockError, InvalidDenominationError

VALID_DENOMINATIONS = (10, 50, 100, 500, 1000)


@dataclass
class Product:
    product_id: str
    name: str
    price: int
    stock: int
    max_stock: int
    active: bool = True
    image_path: str | None = None
    slot_no: int | None = None

    def is_available(self) -> bool:
        return self.active and self.stock > 0

    def decrease_stock(self, qty: int = 1) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        if self.stock < qty:
            raise OutOfStockError(self.name)
        self.stock -= qty

    def refill(self, qty: int) -> int:
        if qty <= 0:
            raise ValueError("qty must be positive")
        before = self.stock
        self.stock = min(self.max_stock, self.stock + qty)
        return self.stock - before

    def refill_to_max(self) -> int:
        before = self.stock
        self.stock = self.max_stock
        return self.stock - before


@dataclass
class CashInventory:
    counts: Dict[int, int] = field(default_factory=dict)
    min_keep: Dict[int, int] = field(default_factory=dict)
    max_capacity: Dict[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for denom in VALID_DENOMINATIONS:
            self.counts.setdefault(denom, 0)
            self.min_keep.setdefault(denom, 0)
            self.max_capacity.setdefault(denom, 999999)

    def total_amount(self) -> int:
        return sum(denom * qty for denom, qty in self.counts.items())

    def add(self, denomination: int, qty: int = 1) -> None:
        if denomination not in VALID_DENOMINATIONS:
            raise InvalidDenominationError(denomination)
        if qty <= 0:
            raise ValueError("qty must be positive")
        current = self.counts.get(denomination, 0)
        max_capacity = self.max_capacity.get(denomination, 999999)
        if current + qty > max_capacity:
            raise ValueError(
                f"{denomination}원 재고 한도를 초과합니다. 현재={current}, 추가={qty}, 최대={max_capacity}"
            )
        self.counts[denomination] = current + qty

    def remove(self, denomination: int, qty: int = 1) -> None:
        if denomination not in VALID_DENOMINATIONS:
            raise InvalidDenominationError(denomination)
        if qty <= 0:
            raise ValueError("qty must be positive")
        current = self.counts.get(denomination, 0)
        if current < qty:
            raise ValueError(f"{denomination}원 재고가 부족합니다.")
        self.counts[denomination] = current - qty

    def clone(self) -> "CashInventory":
        return CashInventory(
            counts=dict(self.counts),
            min_keep=dict(self.min_keep),
            max_capacity=dict(self.max_capacity),
        )

    def removable_counts(self, keep_minimum: bool = False) -> Dict[int, int]:
        result: Dict[int, int] = {}
        for denom, count in self.counts.items():
            removable = count - self.min_keep.get(denom, 0) if keep_minimum else count
            result[denom] = max(0, removable)
        return result


@dataclass
class Session:
    inserted_total: int = 0
    inserted_breakdown: Dict[int, int] = field(default_factory=dict)

    def insert(self, denomination: int, qty: int = 1) -> None:
        if denomination not in VALID_DENOMINATIONS:
            raise InvalidDenominationError(denomination)
        if qty <= 0:
            raise ValueError("qty must be positive")
        self.inserted_total += denomination * qty
        self.inserted_breakdown[denomination] = self.inserted_breakdown.get(denomination, 0) + qty

    def spend(self, amount: int) -> None:
        if amount <= 0:
            raise ValueError("amount must be positive")
        if amount > self.inserted_total:
            raise ValueError("cannot spend more than inserted_total")
        self.inserted_total -= amount
        self.inserted_breakdown = self._breakdown_for_total(self.inserted_total)

    def clear(self) -> None:
        self.inserted_total = 0
        self.inserted_breakdown.clear()

    def _breakdown_for_total(self, amount: int) -> Dict[int, int]:
        breakdown: Dict[int, int] = {}
        remaining = amount
        for denomination in sorted(VALID_DENOMINATIONS, reverse=True):
            qty, remaining = divmod(remaining, denomination)
            if qty:
                breakdown[denomination] = qty
        if remaining != 0:
            raise ValueError(f"cannot represent session balance: {amount}")
        return breakdown


@dataclass
class MachineState:
    products: Dict[str, Product]
    cash_inventory: CashInventory
    config: Dict[str, str] = field(default_factory=dict)

    def get_product(self, product_id: str) -> Product:
        try:
            return self.products[product_id]
        except KeyError:
            from .exceptions import ProductNotFoundError
            raise ProductNotFoundError(product_id) from None
