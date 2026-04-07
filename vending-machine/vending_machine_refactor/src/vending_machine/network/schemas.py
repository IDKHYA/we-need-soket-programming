from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MachineEventEnvelope(BaseModel):
    event_id: str
    machine_id: str
    server_id: str
    event_type: str
    occurred_at: str
    sequence_no: int
    schema_version: str = "1"
    source: Literal["machine", "server_sync"] = "machine"
    sheet_name: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EventBatchRequest(BaseModel):
    events: list[MachineEventEnvelope]


class EventBatchAck(BaseModel):
    accepted_event_ids: list[str] = Field(default_factory=list)
    duplicated_event_ids: list[str] = Field(default_factory=list)
    failed_event_ids: list[str] = Field(default_factory=list)
    sync_triggered: bool = False


class ServerSyncPacket(BaseModel):
    packet_type: Literal["EVENT_SYNC"] = "EVENT_SYNC"
    source_server: str
    target_server: str
    event: MachineEventEnvelope
    checksum: str


class SyncAck(BaseModel):
    ack: bool
    event_id: str
    duplicated: bool = False
    message: str = "OK"
