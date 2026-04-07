from __future__ import annotations

from datetime import datetime

from vending_machine.app.dto import DomainEvent, InsertCashResult, PurchaseResult, RefundResult
from vending_machine.domain.change import ChangeCalculator
from vending_machine.domain.models import MachineState, Session, VALID_DENOMINATIONS
from vending_machine.infra.security import PasswordHasher


class VendingMachineService:
    MAX_BILL_INPUT_TOTAL = 5000
    MAX_INSERTED_TOTAL = 7000

    def __init__(
        self,
        state: MachineState,
        session: Session | None = None,
        change_calculator: ChangeCalculator | None = None,
        password_hasher: PasswordHasher | None = None,
    ) -> None:
        self.state = state
        self.session = session or Session()
        self.change_calculator = change_calculator or ChangeCalculator()
        self.password_hasher = password_hasher or PasswordHasher()

    def insert_cash(self, denomination: int) -> InsertCashResult:
        if denomination not in VALID_DENOMINATIONS:
            raise ValueError(f"지원하지 않는 금액입니다: {denomination}")

        self._validate_insert_limits(denomination)
        self.state.cash_inventory.add(denomination, 1)
        self.session.insert(denomination, 1)

        event = DomainEvent(
            sheet_name="cash_log",
            payload={
                "cash_event_id": self._new_id("CASH"),
                "event_at": self._now(),
                "event_type": "INSERT",
                "denomination": denomination,
                "qty": 1,
                "amount": denomination,
                "note": "user_insert",
            },
        )
        return InsertCashResult(
            success=True,
            code="OK",
            message=f"{denomination}원 투입 완료",
            current_balance=self.session.inserted_total,
            cash_events=[event],
        )

    def purchase(self, product_id: str) -> PurchaseResult:
        product = self.state.get_product(product_id)

        if not product.is_available():
            return PurchaseResult(
                success=False,
                code="OUT_OF_STOCK",
                message=f"{product.name} 재고가 없습니다.",
                remaining_balance=self.session.inserted_total,
            )

        if self.session.inserted_total < product.price:
            return PurchaseResult(
                success=False,
                code="INSUFFICIENT_BALANCE",
                message=f"잔액이 부족합니다. {product.price}원이 필요합니다.",
                remaining_balance=self.session.inserted_total,
            )

        before_stock = product.stock
        product.decrease_stock(1)
        self.session.spend(product.price)
        remaining = self.session.inserted_total

        now = self._now()
        sale_event = DomainEvent(
            sheet_name="sales_log",
            payload={
                "sale_id": self._new_id("SALE"),
                "sold_at": now,
                "product_id": product.product_id,
                "product_name": product.name,
                "unit_price": product.price,
                "qty": 1,
                "paid_amount": product.price,
                "change_amount": 0,
                "result": "SUCCESS",
            },
        )

        stock_events = [
            DomainEvent(
                sheet_name="stock_log",
                payload={
                    "stock_event_id": self._new_id("STOCK"),
                    "event_at": now,
                    "product_id": product.product_id,
                    "product_name": product.name,
                    "event_type": "SALE",
                    "before_stock": before_stock,
                    "change_qty": -1,
                    "after_stock": product.stock,
                    "note": "purchase",
                },
            )
        ]

        if product.stock == 0:
            stock_events.append(
                DomainEvent(
                    sheet_name="stock_log",
                    payload={
                        "stock_event_id": self._new_id("STOCK"),
                        "event_at": now,
                        "product_id": product.product_id,
                        "product_name": product.name,
                        "event_type": "OUT_OF_STOCK",
                        "before_stock": 0,
                        "change_qty": 0,
                        "after_stock": 0,
                        "note": "auto_record",
                    },
                )
            )

        return PurchaseResult(
            success=True,
            code="OK",
            message=f"{product.name} 구매 완료",
            remaining_balance=remaining,
            sale_events=[sale_event],
            cash_events=[],
            stock_events=stock_events,
        )

    def refund(self) -> RefundResult:
        amount = self.session.inserted_total
        if amount == 0:
            return RefundResult(
                success=True,
                code="NO_MONEY",
                message="반환할 금액이 없습니다.",
                refunded_amount=0,
            )

        refund_breakdown = self.change_calculator.calculate(
            amount=amount,
            available=self.state.cash_inventory.counts,
        )
        for denom, qty in refund_breakdown.items():
            self.state.cash_inventory.remove(denom, qty)
        self.session.clear()

        now = self._now()
        events = []
        for denom, qty in sorted(refund_breakdown.items()):
            events.append(
                DomainEvent(
                    sheet_name="cash_log",
                    payload={
                        "cash_event_id": self._new_id("CASH"),
                        "event_at": now,
                        "event_type": "REFUND",
                        "denomination": denom,
                        "qty": qty,
                        "amount": denom * qty,
                        "note": "user_refund",
                    },
                )
            )

        return RefundResult(
            success=True,
            code="OK",
            message=f"{amount}원 반환 완료",
            refunded_amount=amount,
            refunded_breakdown=refund_breakdown,
            cash_events=events,
        )

    def refill_product_to_max(self, product_id: str, actor: str = "admin") -> list[DomainEvent]:
        product = self.state.get_product(product_id)
        before_stock = product.stock
        delta = product.refill_to_max()
        now = self._now()
        return [
            DomainEvent(
                sheet_name="stock_log",
                payload={
                    "stock_event_id": self._new_id("STOCK"),
                    "event_at": now,
                    "product_id": product.product_id,
                    "product_name": product.name,
                    "event_type": "REFILL",
                    "before_stock": before_stock,
                    "change_qty": delta,
                    "after_stock": product.stock,
                    "note": "admin_refill_to_max",
                },
            ),
            self._audit_event(
                actor=actor,
                action="PRODUCT_REFILL_TO_MAX",
                target=product.product_id,
                detail=f"before={before_stock}, added={delta}, after={product.stock}",
                now=now,
            ),
        ]

    def refill_cash_to_minimum(self, actor: str = "admin") -> list[DomainEvent]:
        now = self._now()
        events: list[DomainEvent] = []
        for denom in sorted(self.state.cash_inventory.counts):
            current = self.state.cash_inventory.counts.get(denom, 0)
            minimum = self.state.cash_inventory.min_keep.get(denom, 0)
            delta = max(0, minimum - current)
            if delta <= 0:
                continue
            self.state.cash_inventory.add(denom, delta)
            events.append(
                DomainEvent(
                    sheet_name="cash_log",
                    payload={
                        "cash_event_id": self._new_id("CASH"),
                        "event_at": now,
                        "event_type": "REFILL_CASH",
                        "denomination": denom,
                        "qty": delta,
                        "amount": denom * delta,
                        "note": "admin_refill_to_minimum",
                    },
                )
            )

        events.append(
            self._audit_event(
                actor=actor,
                action="CASH_REFILL_TO_MINIMUM",
                target="cash_inventory",
                detail="minimum cash baseline restored",
                now=now,
            )
        )
        return events

    def collect_cash(self, keep_minimum: bool = True, actor: str = "admin") -> list[DomainEvent]:
        now = self._now()
        events = []
        removable = self.state.cash_inventory.removable_counts(keep_minimum=keep_minimum)
        total_amount = 0
        for denom, qty in sorted(removable.items()):
            if qty <= 0:
                continue
            self.state.cash_inventory.remove(denom, qty)
            total_amount += denom * qty
            events.append(
                DomainEvent(
                    sheet_name="cash_log",
                    payload={
                        "cash_event_id": self._new_id("CASH"),
                        "event_at": now,
                        "event_type": "COLLECT",
                        "denomination": denom,
                        "qty": qty,
                        "amount": denom * qty,
                        "note": "admin_collect_keep_min" if keep_minimum else "admin_collect_all",
                    },
                )
            )
        events.append(
            self._audit_event(
                actor=actor,
                action="CASH_COLLECT",
                target="cash_inventory",
                detail=f"keep_minimum={keep_minimum}, total_amount={total_amount}",
                now=now,
            )
        )
        return events

    def authenticate_admin(self, raw_password: str) -> bool:
        stored = self.state.config.get("admin_password_hash", "")
        return self.password_hasher.verify(raw_password, stored)

    def set_admin_password(self, new_password: str, actor: str = "admin") -> list[DomainEvent]:
        self._validate_password_policy(new_password)
        self.state.config["admin_password_hash"] = self.password_hasher.hash_password(new_password)
        return [
            self._audit_event(
                actor=actor,
                action="PASSWORD_CHANGED",
                target="machine_config.admin_password_hash",
                detail="admin password hash updated",
                extra_payload={"changes": {"admin_password_hash": ["***", "***updated***"]}},
            )
        ]

    def adjust_product_stock(self, product_id: str, delta: int, actor: str = "admin") -> list[DomainEvent]:
        if delta == 0:
            return []
        product = self.state.get_product(product_id)
        before_stock = product.stock
        next_stock = max(0, min(product.max_stock, product.stock + delta))
        actual_delta = next_stock - before_stock
        if actual_delta == 0:
            return []
        product.stock = next_stock
        now = self._now()
        return [
            DomainEvent(
                sheet_name="stock_log",
                payload={
                    "stock_event_id": self._new_id("STOCK"),
                    "event_at": now,
                    "product_id": product.product_id,
                    "product_name": product.name,
                    "event_type": "MANUAL_ADJUST",
                    "before_stock": before_stock,
                    "change_qty": actual_delta,
                    "after_stock": product.stock,
                    "note": "admin_manual_adjust",
                },
            ),
            self._audit_event(
                actor=actor,
                action="PRODUCT_STOCK_ADJUSTED",
                target=product.product_id,
                detail=f"before={before_stock}, delta={actual_delta}, after={product.stock}",
                now=now,
            ),
        ]

    def update_product(
        self,
        product_id: str,
        *,
        name: str | None = None,
        price: int | None = None,
        max_stock: int | None = None,
        active: bool | None = None,
        image_path: str | None = None,
        slot_no: int | None = None,
        actor: str = "admin",
    ) -> list[DomainEvent]:
        product = self.state.get_product(product_id)
        before = {
            "name": product.name,
            "price": product.price,
            "stock": product.stock,
            "max_stock": product.max_stock,
            "active": product.active,
            "image_path": product.image_path,
            "slot_no": product.slot_no,
        }

        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise ValueError("상품명은 비워둘 수 없습니다.")
            product.name = cleaned
        if price is not None:
            self._validate_price(price)
            product.price = price
        if max_stock is not None:
            if max_stock <= 0:
                raise ValueError("최대 재고는 1 이상이어야 합니다.")
            if product.stock > max_stock:
                raise ValueError("현재 재고보다 작은 max_stock으로 줄일 수 없습니다.")
            product.max_stock = max_stock
        if active is not None:
            product.active = active
        if image_path is not None:
            product.image_path = image_path.strip() or None
        if slot_no is not None:
            self._validate_unique_slot(product_id, slot_no)
            product.slot_no = slot_no

        after = {
            "name": product.name,
            "price": product.price,
            "stock": product.stock,
            "max_stock": product.max_stock,
            "active": product.active,
            "image_path": product.image_path,
            "slot_no": product.slot_no,
        }
        changed = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
        if not changed:
            return []

        return [
            self._audit_event(
                actor=actor,
                action="PRODUCT_UPDATED",
                target=product.product_id,
                detail=", ".join(f"{k}:{v[0]}->{v[1]}" for k, v in changed.items()),
                extra_payload={"changes": changed},
            )
        ]

    def _validate_password_policy(self, password: str) -> None:
        if len(password) < 8:
            raise ValueError("비밀번호는 최소 8자 이상이어야 합니다.")
        if not any(ch.isalpha() for ch in password):
            raise ValueError("비밀번호에는 영문이 최소 1자 포함되어야 합니다.")
        if not any(ch.isdigit() for ch in password):
            raise ValueError("비밀번호에는 숫자가 최소 1자 포함되어야 합니다.")
        if not any(ch in r"!@#$%^&*()-_=+[]{};:,.?/\\|" for ch in password):
            raise ValueError("비밀번호에는 특수문자가 최소 1자 포함되어야 합니다.")

    def _validate_price(self, price: int) -> None:
        if price <= 0:
            raise ValueError("가격은 0보다 커야 합니다.")
        if price % 10 != 0:
            raise ValueError("가격은 10원 단위여야 합니다.")

    def _validate_unique_slot(self, current_product_id: str, slot_no: int) -> None:
        for product_id, product in self.state.products.items():
            if product_id == current_product_id:
                continue
            if product.slot_no == slot_no:
                raise ValueError(f"slot_no {slot_no}는 이미 다른 상품이 사용 중입니다.")

    def _validate_insert_limits(self, denomination: int) -> None:
        if self.session.inserted_total + denomination > self.MAX_INSERTED_TOTAL:
            raise ValueError("총 투입 금액은 7000원을 넘을 수 없습니다.")

        if denomination == 1000 and self._bill_inserted_total() + denomination > self.MAX_BILL_INPUT_TOTAL:
            raise ValueError("지폐 입력 누적 금액은 5000원을 넘을 수 없습니다.")

    def _bill_inserted_total(self) -> int:
        return self.session.inserted_breakdown.get(1000, 0) * 1000

    def _audit_event(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        detail: str,
        now: str | None = None,
        extra_payload: dict | None = None,
    ) -> DomainEvent:
        payload = {
            "audit_id": self._new_id("AUDIT"),
            "event_at": now or self._now(),
            "actor": actor,
            "action": action,
            "target": target,
            "detail": detail,
        }
        if extra_payload:
            payload.update(extra_payload)
        return DomainEvent(
            sheet_name="audit_log",
            payload=payload,
        )

    def _now(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
