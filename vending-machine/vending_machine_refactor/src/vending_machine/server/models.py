from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from vending_machine.server.db import Base


class Machine(Base):
    __tablename__ = "machines"

    machine_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    server_id: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(128))
    location: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MachineProduct(Base):
    __tablename__ = "machine_products"
    __table_args__ = (UniqueConstraint("machine_id", "product_id", name="uq_machine_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"), nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)


class MachineStatus(Base):
    __tablename__ = "machine_status"

    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"), primary_key=True)
    server_id: Mapped[str] = mapped_column(String(32), nullable=False)
    current_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cash_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_event_id: Mapped[str | None] = mapped_column(String(128))
    last_event_type: Mapped[str | None] = mapped_column(String(64))
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)


class MachineCashStatus(Base):
    __tablename__ = "machine_cash_status"
    __table_args__ = (UniqueConstraint("machine_id", "denomination", name="uq_machine_cash_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"), nullable=False)
    denomination: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)


class MachineEvent(Base):
    __tablename__ = "machine_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"), nullable=False)
    server_id: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    synced_to_peer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)


class SalesEvent(Base):
    __tablename__ = "sales_events"

    event_id: Mapped[str] = mapped_column(ForeignKey("machine_events.event_id"), primary_key=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    change_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class StockEvent(Base):
    __tablename__ = "stock_events"

    event_id: Mapped[str] = mapped_column(ForeignKey("machine_events.event_id"), primary_key=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    before_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    change_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    after_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class CashEvent(Base):
    __tablename__ = "cash_events"

    event_id: Mapped[str] = mapped_column(ForeignKey("machine_events.event_id"), primary_key=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    denomination: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class AdminAction(Base):
    __tablename__ = "admin_actions"

    event_id: Mapped[str] = mapped_column(ForeignKey("machine_events.event_id"), primary_key=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("machine_id", "product_id", "alert_type", name="uq_alert_machine_product_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    current_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class ServerSyncLog(Base):
    __tablename__ = "server_sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_server: Mapped[str] = mapped_column(String(32), nullable=False)
    target_server: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)


class ServerHealthLog(Base):
    __tablename__ = "server_health_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    detail: Mapped[str] = mapped_column(String(255), nullable=False, default="")
