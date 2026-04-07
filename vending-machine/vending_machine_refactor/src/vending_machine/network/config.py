from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class MachineNetworkConfig:
    machine_id: str
    server_id: str
    server_api_base_url: str
    enabled: bool = True

    @classmethod
    def from_sources(cls, workbook_path: Path, config: dict[str, str]) -> "MachineNetworkConfig | None":
        machine_id = str(config.get("machine_id") or os.getenv("VM_MACHINE_ID") or workbook_path.stem).strip()
        server_id = str(config.get("server_id") or os.getenv("VM_SERVER_ID") or "server1").strip()
        api_base_url = str(config.get("server_api_base_url") or os.getenv("VM_SERVER_API_BASE_URL") or "").strip()
        enabled_raw = str(config.get("network_enabled") or os.getenv("VM_NETWORK_ENABLED") or "").strip().lower()
        enabled = enabled_raw not in {"0", "false", "n", "no", "off"}
        if not api_base_url:
            return None
        return cls(
            machine_id=machine_id,
            server_id=server_id,
            server_api_base_url=api_base_url.rstrip("/"),
            enabled=enabled,
        )
