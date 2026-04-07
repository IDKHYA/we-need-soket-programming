from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from vending_machine.network.schemas import MachineEventEnvelope


class OutboundEventQueue:
    def __init__(self, queue_path: Path):
        self.queue_path = queue_path
        self.meta_path = queue_path.with_suffix(queue_path.suffix + ".meta")
        self._lock = Lock()

    def next_sequence(self) -> int:
        with self._lock:
            meta = self._read_meta()
            value = int(meta.get("last_sequence", 0)) + 1
            meta["last_sequence"] = value
            self._write_meta(meta)
            return value

    def append(self, events: list[MachineEventEnvelope]) -> None:
        if not events:
            return
        with self._lock:
            existing = self._read_rows()
            existing.extend(event.model_dump() for event in events)
            self._write_rows(existing)

    def list_events(self) -> list[MachineEventEnvelope]:
        with self._lock:
            return [MachineEventEnvelope.model_validate(item) for item in self._read_rows()]

    def acknowledge(self, event_ids: list[str]) -> None:
        if not event_ids:
            return
        accepted = set(event_ids)
        with self._lock:
            rows = [row for row in self._read_rows() if str(row.get("event_id")) not in accepted]
            self._write_rows(rows)

    def _read_rows(self) -> list[dict]:
        if not self.queue_path.exists():
            return []
        text = self.queue_path.read_text(encoding="utf-8").strip()
        if not text:
            return []
        return json.loads(text)

    def _write_rows(self, rows: list[dict]) -> None:
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.queue_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_meta(self) -> dict:
        if not self.meta_path.exists():
            return {}
        text = self.meta_path.read_text(encoding="utf-8").strip()
        if not text:
            return {}
        return json.loads(text)

    def _write_meta(self, meta: dict) -> None:
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
