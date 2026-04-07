from __future__ import annotations

import hashlib
import json
import socket
import struct

from vending_machine.network.schemas import ServerSyncPacket


def calculate_checksum(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_sync_packet(packet: ServerSyncPacket) -> bytes:
    body = packet.model_dump_json().encode("utf-8")
    return struct.pack("!I", len(body)) + body


def read_sync_packet(sock: socket.socket) -> ServerSyncPacket:
    header = _recv_exact(sock, 4)
    length = struct.unpack("!I", header)[0]
    body = _recv_exact(sock, length)
    packet = ServerSyncPacket.model_validate(json.loads(body.decode("utf-8")))
    expected = calculate_checksum(packet.event.model_dump_json().encode("utf-8"))
    if packet.checksum != expected:
        raise ValueError("동기화 패킷 checksum 검증에 실패했습니다.")
    return packet


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("소켓 수신이 중간에 종료되었습니다.")
        chunks.extend(chunk)
    return bytes(chunks)
