from __future__ import annotations

from pathlib import Path
from typing import Iterable

from vending_machine.app.dto import DomainEvent
from vending_machine.network.client import MachineApiClient
from vending_machine.network.config import MachineNetworkConfig
from vending_machine.network.queue import OutboundEventQueue
from vending_machine.network.schemas import MachineEventEnvelope


class MachineNetworkGateway:
    def __init__(self, config: MachineNetworkConfig, queue: OutboundEventQueue):
        self.config = config
        self.queue = queue
        self.client = MachineApiClient(config.server_api_base_url)

    @classmethod
    def create(cls, workbook_path: Path, state_config: dict[str, str]) -> "MachineNetworkGateway | None":
        config = MachineNetworkConfig.from_sources(workbook_path, state_config)
        if not config or not config.enabled:
            return None
        queue_path = workbook_path.with_suffix(".network_queue.json")
        return cls(config=config, queue=OutboundEventQueue(queue_path))

    def publish_domain_events(self, events: Iterable[DomainEvent]) -> None:
        envelopes = [self._to_envelope(event) for event in events]
        if not envelopes:
            return
        self.queue.append(envelopes)
        self.flush_pending()

    def flush_pending(self) -> None:
        pending = self.queue.list_events()
        if not pending:
            return
        ack = self.client.publish_events(self.config.machine_id, pending)
        accepted_ids = [*ack.accepted_event_ids, *ack.duplicated_event_ids]
        self.queue.acknowledge(accepted_ids)

    def _to_envelope(self, event: DomainEvent) -> MachineEventEnvelope:
        event_id = _extract_event_id(event)
        occurred_at = _extract_occurred_at(event)
        return MachineEventEnvelope(
            event_id=event_id,
            machine_id=self.config.machine_id,
            server_id=self.config.server_id,
            event_type=_resolve_event_type(event),
            occurred_at=occurred_at,
            sequence_no=self.queue.next_sequence(),
            sheet_name=event.sheet_name,
            payload=event.payload,
        )


def _extract_event_id(event: DomainEvent) -> str:
    candidates = ("sale_id", "cash_event_id", "stock_event_id", "audit_id", "event_id")
    for key in candidates:
        value = event.payload.get(key)
        if value:
            return str(value)
    raise ValueError(f"이벤트 식별자가 없습니다: {event.sheet_name}")


def _extract_occurred_at(event: DomainEvent) -> str:
    for key in ("sold_at", "event_at", "occurred_at"):
        value = event.payload.get(key)
        if value:
            return str(value)
    raise ValueError(f"이벤트 발생 시각이 없습니다: {event.sheet_name}")


def _resolve_event_type(event: DomainEvent) -> str:
    if event.sheet_name == "sales_log":
        return "SALE"
    if event.sheet_name == "cash_log":
        return str(event.payload.get("event_type", "CASH")).upper()
    if event.sheet_name == "stock_log":
        return f"STOCK_{str(event.payload.get('event_type', 'UPDATE')).upper()}"
    if event.sheet_name == "audit_log":
        return f"ADMIN_{str(event.payload.get('action', 'AUDIT')).upper()}"
    return event.sheet_name.upper()
