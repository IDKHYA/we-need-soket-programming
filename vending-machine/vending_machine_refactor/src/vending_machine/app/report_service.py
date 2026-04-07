from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from vending_machine.infra.excel_repository import ExcelMachineRepository


@dataclass(frozen=True)
class DailySalesRow:
    date: str
    sales_count: int
    units_sold: int
    gross_sales: int
    total_change: int
    net_sales: int


@dataclass(frozen=True)
class MonthlySalesRow:
    month: str
    sales_count: int
    units_sold: int
    gross_sales: int
    total_change: int
    net_sales: int


@dataclass(frozen=True)
class ProductSalesRow:
    product_id: str
    product_name: str
    units_sold: int
    gross_sales: int
    total_change: int
    net_sales: int


@dataclass(frozen=True)
class CashFlowRow:
    event_type: str
    total_amount: int
    total_qty: int
    event_count: int


class SalesReportService:
    def __init__(self, repository: ExcelMachineRepository):
        self.repository = repository

    def sales_events(self, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, Any]]:
        rows = []
        for row in self.repository.read_sheet_rows(self.repository.SALES_LOG_SHEET):
            if str(row.get("result", "")).upper() != "SUCCESS":
                continue
            sold_at = self._to_datetime(str(row.get("sold_at", "")))
            if not self._in_range(sold_at.date(), start_date, end_date):
                continue
            rows.append({**row, "sold_at_dt": sold_at})
        rows.sort(key=lambda item: item["sold_at_dt"])
        return rows

    def cash_events(self, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, Any]]:
        rows = []
        for row in self.repository.read_sheet_rows(self.repository.CASH_LOG_SHEET):
            event_at = self._to_datetime(str(row.get("event_at", "")))
            if not self._in_range(event_at.date(), start_date, end_date):
                continue
            rows.append({**row, "event_at_dt": event_at})
        rows.sort(key=lambda item: item["event_at_dt"])
        return rows

    def daily_sales(self, start_date: date | None = None, end_date: date | None = None) -> list[DailySalesRow]:
        grouped: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for row in self.sales_events(start_date, end_date):
            date_key = row["sold_at_dt"].strftime("%Y-%m-%d")
            grouped[date_key]["sales_count"] += 1
            grouped[date_key]["units_sold"] += self._as_int(row.get("qty"))
            grouped[date_key]["gross_sales"] += self._as_int(row.get("paid_amount"))
            grouped[date_key]["total_change"] += self._as_int(row.get("change_amount"))

        result = []
        for date_key in sorted(grouped):
            item = grouped[date_key]
            result.append(
                DailySalesRow(
                    date=date_key,
                    sales_count=item["sales_count"],
                    units_sold=item["units_sold"],
                    gross_sales=item["gross_sales"],
                    total_change=item["total_change"],
                    net_sales=item["gross_sales"] - item["total_change"],
                )
            )
        return result

    def monthly_sales(self, start_date: date | None = None, end_date: date | None = None) -> list[MonthlySalesRow]:
        grouped: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for row in self.sales_events(start_date, end_date):
            month_key = row["sold_at_dt"].strftime("%Y-%m")
            grouped[month_key]["sales_count"] += 1
            grouped[month_key]["units_sold"] += self._as_int(row.get("qty"))
            grouped[month_key]["gross_sales"] += self._as_int(row.get("paid_amount"))
            grouped[month_key]["total_change"] += self._as_int(row.get("change_amount"))

        result = []
        for month_key in sorted(grouped):
            item = grouped[month_key]
            result.append(
                MonthlySalesRow(
                    month=month_key,
                    sales_count=item["sales_count"],
                    units_sold=item["units_sold"],
                    gross_sales=item["gross_sales"],
                    total_change=item["total_change"],
                    net_sales=item["gross_sales"] - item["total_change"],
                )
            )
        return result

    def product_sales(self, start_date: date | None = None, end_date: date | None = None) -> list[ProductSalesRow]:
        grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for row in self.sales_events(start_date, end_date):
            key = (str(row.get("product_id", "")), str(row.get("product_name", "")))
            grouped[key]["units_sold"] += self._as_int(row.get("qty"))
            grouped[key]["gross_sales"] += self._as_int(row.get("paid_amount"))
            grouped[key]["total_change"] += self._as_int(row.get("change_amount"))

        result = []
        for (product_id, product_name), item in sorted(grouped.items()):
            result.append(
                ProductSalesRow(
                    product_id=product_id,
                    product_name=product_name,
                    units_sold=item["units_sold"],
                    gross_sales=item["gross_sales"],
                    total_change=item["total_change"],
                    net_sales=item["gross_sales"] - item["total_change"],
                )
            )
        return result

    def cash_flow(self, start_date: date | None = None, end_date: date | None = None) -> list[CashFlowRow]:
        grouped: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for row in self.cash_events(start_date, end_date):
            event_type = str(row.get("event_type", "UNKNOWN"))
            grouped[event_type]["total_amount"] += self._as_int(row.get("amount"))
            grouped[event_type]["total_qty"] += self._as_int(row.get("qty"))
            grouped[event_type]["event_count"] += 1

        return [
            CashFlowRow(
                event_type=event_type,
                total_amount=item["total_amount"],
                total_qty=item["total_qty"],
                event_count=item["event_count"],
            )
            for event_type, item in sorted(grouped.items())
        ]

    def summary(self, start_date: date | None = None, end_date: date | None = None) -> dict[str, Any]:
        events = self.sales_events(start_date, end_date)
        total_paid = sum(self._as_int(row.get("paid_amount")) for row in events)
        total_change = sum(self._as_int(row.get("change_amount")) for row in events)
        total_net = total_paid - total_change
        total_count = len(events)
        total_units = sum(self._as_int(row.get("qty")) for row in events)
        avg_ticket = int(round(total_net / total_count)) if total_count else 0
        product_rows = self.product_sales(start_date, end_date)
        best_seller = product_rows[0].product_name if product_rows else "-"
        if product_rows:
            best_seller = max(product_rows, key=lambda row: row.units_sold).product_name
        return {
            "sales_count": total_count,
            "units_sold": total_units,
            "gross_sales": total_paid,
            "change_total": total_change,
            "net_sales": total_net,
            "avg_ticket": avg_ticket,
            "best_seller": best_seller,
        }

    def low_stock_products(self, threshold: int = 0) -> list[dict[str, int | str]]:
        state = self.repository.load_state()
        items = []
        for product in sorted(state.products.values(), key=lambda p: (p.stock, p.product_id)):
            if product.stock <= threshold:
                items.append(
                    {
                        "product_id": product.product_id,
                        "name": product.name,
                        "stock": product.stock,
                        "price": product.price,
                        "max_stock": product.max_stock,
                    }
                )
        return items

    def _to_datetime(self, value: str) -> datetime:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ValueError(f"지원하지 않는 날짜 형식입니다: {value}")

    def _in_range(self, target: date, start_date: date | None, end_date: date | None) -> bool:
        if start_date and target < start_date:
            return False
        if end_date and target > end_date:
            return False
        return True

    def _as_int(self, value: object) -> int:
        if value in (None, ""):
            return 0
        return int(value)
