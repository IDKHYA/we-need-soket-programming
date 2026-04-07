from __future__ import annotations

from pathlib import Path
from typing import Iterable

from vending_machine.app.dto import DomainEvent
from vending_machine.infra.excel_repository import ExcelMachineRepository


def commit_local_and_publish(
    repo: ExcelMachineRepository,
    workbook_path: Path,
    state,
    session,
    events: Iterable[DomainEvent],
) -> None:
    event_list = list(events)
    repo.commit(state, session, event_list)

    try:
        from vending_machine.network.gateway import MachineNetworkGateway
    except ModuleNotFoundError:
        # ???? ???? ??? ?? ???? ?? ?????.
        return

    try:
        gateway = MachineNetworkGateway.create(workbook_path=workbook_path, state_config=state.config)
    except ModuleNotFoundError:
        return

    if gateway is None:
        return
    try:
        gateway.publish_domain_events(event_list)
    except Exception:
        # ?? ??? ?? ???? ???? ??? ?? ????.
        return
