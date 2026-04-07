from __future__ import annotations

import json
import socket
import threading

from vending_machine.network.schemas import SyncAck
from vending_machine.network.sync_protocol import calculate_checksum, read_sync_packet
from vending_machine.server.service import ServerIntegrationService


class EventSyncServer:
    def __init__(self, service: ServerIntegrationService, host: str, port: int):
        self.service = service
        self.host = host
        self.port = port
        self._server_socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen()
        self.port = self._server_socket.getsockname()[1]
        self._thread = threading.Thread(target=self._serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=1.0)

    def _serve_forever(self) -> None:
        assert self._server_socket is not None
        while not self._stop.is_set():
            try:
                client, _ = self._server_socket.accept()
            except OSError:
                break
            with client:
                self._handle_client(client)

    def _handle_client(self, client: socket.socket) -> None:
        try:
            packet = read_sync_packet(client)
            ack = self.service.apply_events(
                [packet.event.model_copy(update={"source": "server_sync"})],
                trigger_sync=False,
            )
            duplicated = packet.event.event_id in ack.duplicated_event_ids
            response = SyncAck(ack=True, event_id=packet.event.event_id, duplicated=duplicated)
        except Exception as exc:
            response = SyncAck(ack=False, event_id="", duplicated=False, message=str(exc))
        client.sendall(json.dumps(response.model_dump(), ensure_ascii=False).encode("utf-8"))


class EventSyncClient:
    def __init__(self, host: str, port: int, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, source_server: str, target_server: str, event) -> SyncAck:
        from vending_machine.network.schemas import ServerSyncPacket
        from vending_machine.network.sync_protocol import build_sync_packet

        checksum = calculate_checksum(event.model_dump_json().encode("utf-8"))
        packet = ServerSyncPacket(
            source_server=source_server,
            target_server=target_server,
            event=event,
            checksum=checksum,
        )
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.sendall(build_sync_packet(packet))
            raw = sock.recv(65535)
        return SyncAck.model_validate(json.loads(raw.decode("utf-8")))
