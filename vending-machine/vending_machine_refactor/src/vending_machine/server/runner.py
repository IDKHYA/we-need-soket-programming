from __future__ import annotations

import argparse
import os

import uvicorn

from vending_machine.server.api import create_app
from vending_machine.server.service import ServerSettings
from vending_machine.server.sync_server import EventSyncServer


def main() -> None:
    parser = argparse.ArgumentParser(description="통합 자판기 FastAPI 서버 실행")
    parser.add_argument('--server-id', default=os.getenv('VM_SERVER_ID', 'server1'))
    parser.add_argument('--database-url', default=os.getenv('VM_DATABASE_URL', 'sqlite:///./vending_machine_server.db'))
    parser.add_argument('--peer-server-id', default=os.getenv('VM_PEER_SERVER_ID', 'server2'))
    parser.add_argument('--peer-sync-host', default=os.getenv('VM_PEER_SYNC_HOST', '127.0.0.1'))
    parser.add_argument('--peer-sync-port', type=int, default=int(os.getenv('VM_PEER_SYNC_PORT', '9102')))
    parser.add_argument('--sync-host', default=os.getenv('VM_SYNC_HOST', '127.0.0.1'))
    parser.add_argument('--sync-port', type=int, default=int(os.getenv('VM_SYNC_PORT', '9101')))
    parser.add_argument('--host', default=os.getenv('VM_API_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.getenv('VM_API_PORT', '8000')))
    args = parser.parse_args()

    settings = ServerSettings(
        server_id=args.server_id,
        database_url=args.database_url,
        peer_server_id=args.peer_server_id,
        peer_sync_host=args.peer_sync_host,
        peer_sync_port=args.peer_sync_port,
    )
    app = create_app(settings)
    sync_server = EventSyncServer(service=app.state.service if hasattr(app.state, 'service') else None, host=args.sync_host, port=args.sync_port)
    if sync_server.service is None:
        from vending_machine.server.service import ServerIntegrationService
        sync_server.service = ServerIntegrationService(settings)
    sync_server.start()
    try:
        uvicorn.run(app, host=args.host, port=args.port)
    finally:
        sync_server.stop()


if __name__ == '__main__':
    main()
