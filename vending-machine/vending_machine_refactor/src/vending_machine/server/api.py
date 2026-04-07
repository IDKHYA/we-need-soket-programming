from __future__ import annotations

from fastapi import Body, Depends, FastAPI, HTTPException

from vending_machine.network.schemas import EventBatchAck, MachineEventEnvelope
from vending_machine.server.service import ServerIntegrationService, ServerSettings
from vending_machine.server.sync_server import EventSyncClient


def create_app(settings: ServerSettings) -> FastAPI:
    app = FastAPI(title=f"Vending Machine Integrated Server ({settings.server_id})")
    service = ServerIntegrationService(settings=settings)
    sync_client = EventSyncClient(host=settings.peer_sync_host, port=settings.peer_sync_port)
    app.state.service = service

    def get_service() -> ServerIntegrationService:
        return service

    @app.get("/api/v1/health")
    def health(svc: ServerIntegrationService = Depends(get_service)):
        svc.record_health(status="UP", detail="api_healthcheck")
        return {"status": "UP", "server_id": settings.server_id}

    @app.post("/api/v1/machines/{machine_id}/events:batch", response_model=EventBatchAck)
    def ingest_machine_events(
        machine_id: str,
        request_body: dict = Body(...),
        svc: ServerIntegrationService = Depends(get_service),
    ):
        raw_events = request_body.get("events", [])
        events = [MachineEventEnvelope.model_validate(item) for item in raw_events]
        for event in events:
            if event.machine_id != machine_id:
                raise HTTPException(status_code=400, detail="machine_id mismatch")
        ack = svc.apply_events(events, trigger_sync=True)
        for event in events:
            if event.event_id not in ack.accepted_event_ids:
                continue
            if event.source != "machine":
                continue
            try:
                sync_ack = sync_client.send(settings.server_id, settings.peer_server_id, event)
                status = "DUPLICATED" if sync_ack.duplicated else "SYNCED"
                svc.record_sync_result(event.event_id, settings.peer_server_id, status, sync_ack.message)
            except Exception as exc:
                svc.record_sync_result(event.event_id, settings.peer_server_id, "FAILED", str(exc))
        return ack

    @app.get("/api/v1/admin/machines")
    def admin_machines(svc: ServerIntegrationService = Depends(get_service)):
        return svc.machine_statuses()

    @app.get("/api/v1/admin/alerts")
    def admin_alerts(svc: ServerIntegrationService = Depends(get_service)):
        return svc.active_alerts()

    @app.get("/api/v1/admin/stats/machines")
    def admin_machine_stats(svc: ServerIntegrationService = Depends(get_service)):
        return svc.machine_sales_stats()

    @app.get("/api/v1/admin/stats/products")
    def admin_product_stats(svc: ServerIntegrationService = Depends(get_service)):
        return svc.product_sales_stats()

    @app.get("/api/v1/admin/sync-status")
    def admin_sync_status(svc: ServerIntegrationService = Depends(get_service)):
        return svc.sync_status()

    @app.get("/api/v1/admin/events/recent")
    def admin_recent_events(limit: int = 50, svc: ServerIntegrationService = Depends(get_service)):
        return svc.recent_events(limit=limit)

    return app
