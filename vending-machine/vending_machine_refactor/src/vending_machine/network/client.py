from __future__ import annotations

from typing import Iterable

import httpx

from vending_machine.network.schemas import EventBatchAck, EventBatchRequest, MachineEventEnvelope


class MachineApiClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def publish_events(self, machine_id: str, events: Iterable[MachineEventEnvelope]) -> EventBatchAck:
        payload = EventBatchRequest(events=list(events))
        response = httpx.post(
            f"{self.base_url}/api/v1/machines/{machine_id}/events:batch",
            json=payload.model_dump(mode="json"),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return EventBatchAck.model_validate(response.json())
