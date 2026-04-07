from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class DomainEvent:
    sheet_name: str
    payload: dict


@dataclass
class PurchaseResult:
    success: bool
    code: str
    message: str
    remaining_balance: int
    dispensed_change: Dict[int, int] = field(default_factory=dict)
    sale_events: List[DomainEvent] = field(default_factory=list)
    cash_events: List[DomainEvent] = field(default_factory=list)
    stock_events: List[DomainEvent] = field(default_factory=list)


@dataclass
class RefundResult:
    success: bool
    code: str
    message: str
    refunded_amount: int
    refunded_breakdown: Dict[int, int] = field(default_factory=dict)
    cash_events: List[DomainEvent] = field(default_factory=list)


@dataclass
class InsertCashResult:
    success: bool
    code: str
    message: str
    current_balance: int
    cash_events: List[DomainEvent] = field(default_factory=list)
