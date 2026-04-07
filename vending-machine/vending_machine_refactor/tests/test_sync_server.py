from pathlib import Path

from vending_machine.network.schemas import MachineEventEnvelope
from vending_machine.server.service import ServerIntegrationService, ServerSettings
from vending_machine.server.sync_server import EventSyncClient, EventSyncServer


def test_tcp_sync_server_receives_and_stores_event(tmp_path: Path):
    settings = ServerSettings(
        server_id='server2',
        database_url=f"sqlite:///{(tmp_path / 'sync.db').as_posix()}",
        peer_server_id='server1',
        peer_sync_host='127.0.0.1',
        peer_sync_port=9101,
    )
    service = ServerIntegrationService(settings)
    server = EventSyncServer(service=service, host='127.0.0.1', port=0)
    server.start()
    try:
        client = EventSyncClient(host='127.0.0.1', port=server.port)
        event = MachineEventEnvelope(
            event_id='SYNC-SALE-1',
            machine_id='VM-C',
            server_id='server1',
            event_type='SALE',
            occurred_at='2026-04-07 12:30:00',
            sequence_no=10,
            sheet_name='sales_log',
            payload={
                'sale_id': 'SYNC-SALE-1',
                'sold_at': '2026-04-07 12:30:00',
                'product_id': 'P010',
                'product_name': '콜라',
                'unit_price': 1200,
                'qty': 1,
                'paid_amount': 1200,
                'change_amount': 0,
                'result': 'SUCCESS',
            },
        )
        ack = client.send('server1', 'server2', event)
        assert ack.ack is True

        recent = service.recent_events(limit=5)
        assert recent[0]['event_id'] == 'SYNC-SALE-1'
        assert recent[0]['source'] == 'server_sync'
    finally:
        server.stop()
