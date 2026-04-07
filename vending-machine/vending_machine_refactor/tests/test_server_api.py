from pathlib import Path

from fastapi.testclient import TestClient

from vending_machine.network.schemas import MachineEventEnvelope
from vending_machine.server.api import create_app
from vending_machine.server.service import ServerSettings


def make_client(tmp_path: Path) -> TestClient:
    settings = ServerSettings(
        server_id='server1',
        database_url=f"sqlite:///{(tmp_path / 'server.db').as_posix()}",
        peer_server_id='server2',
        peer_sync_host='127.0.0.1',
        peer_sync_port=65531,
        low_stock_threshold=2,
    )
    app = create_app(settings)
    return TestClient(app)


def test_machine_event_batch_creates_stats_and_alerts(tmp_path: Path):
    client = make_client(tmp_path)
    events = [
        MachineEventEnvelope(
            event_id='SALE-1',
            machine_id='VM-A',
            server_id='server1',
            event_type='SALE',
            occurred_at='2026-04-07 12:00:00',
            sequence_no=1,
            sheet_name='sales_log',
            payload={
                'sale_id': 'SALE-1',
                'sold_at': '2026-04-07 12:00:00',
                'product_id': 'P001',
                'product_name': '샘물',
                'unit_price': 500,
                'qty': 1,
                'paid_amount': 500,
                'change_amount': 0,
                'result': 'SUCCESS',
                'remaining_balance': 0,
            },
        ),
        MachineEventEnvelope(
            event_id='STOCK-1',
            machine_id='VM-A',
            server_id='server1',
            event_type='STOCK_SALE',
            occurred_at='2026-04-07 12:00:01',
            sequence_no=2,
            sheet_name='stock_log',
            payload={
                'stock_event_id': 'STOCK-1',
                'event_at': '2026-04-07 12:00:01',
                'product_id': 'P001',
                'product_name': '샘물',
                'event_type': 'SALE',
                'before_stock': 2,
                'change_qty': -1,
                'after_stock': 1,
                'note': 'purchase',
            },
        ),
    ]

    response = client.post('/api/v1/machines/VM-A/events:batch', json={'events': [event.model_dump(mode='json') for event in events]})
    assert response.status_code == 200
    data = response.json()
    assert data['accepted_event_ids'] == ['SALE-1', 'STOCK-1']

    alerts = client.get('/api/v1/admin/alerts').json()
    assert len(alerts) == 1
    assert alerts[0]['alert_type'] == 'LOW_STOCK'
    assert alerts[0]['current_stock'] == 1

    machine_stats = client.get('/api/v1/admin/stats/machines').json()
    assert machine_stats[0]['machine_id'] == 'VM-A'
    assert machine_stats[0]['net_sales'] == 500

    product_stats = client.get('/api/v1/admin/stats/products').json()
    assert product_stats[0]['product_id'] == 'P001'
    assert product_stats[0]['units_sold'] == 1

    duplicate = client.post('/api/v1/machines/VM-A/events:batch', json={'events': [events[0].model_dump(mode='json')]})
    assert duplicate.status_code == 200
    assert duplicate.json()['duplicated_event_ids'] == ['SALE-1']
