import asyncio

from fastapi.testclient import TestClient

from app.api import maintenance as maintenance_api
from app.core import maintenance as core_maintenance
from app.main import app


def test_start_and_stop_maintenance_endpoints(monkeypatch):
    """Ensure start/stop endpoints toggle the shared maintenance state."""
    events = []

    def fake_start(*, delay_seconds=None, stagger_seconds=None):
        events.append(("start", delay_seconds, stagger_seconds))
        core_maintenance._maintenance_started = True

    def fake_stop():
        events.append(("stop",))
        core_maintenance._maintenance_started = False

    monkeypatch.setattr(maintenance_api, "start_maintenance_background", fake_start)
    monkeypatch.setattr(maintenance_api, "request_maintenance_stop", fake_stop)

    client = TestClient(app)

    response = client.post("/maintenance/start")
    assert response.status_code == 200
    assert response.json().get("running") is True

    response = client.post("/maintenance/stop")
    assert response.status_code == 200
    assert response.json() == {"stopped": True}

    assert events == [
        ("start", core_maintenance.settings.MAINTENANCE_STARTUP_DELAY_SECONDS, core_maintenance.settings.MAINTENANCE_STAGGER_SECONDS),
        ("stop",),
    ]


def test_pending_maintenance_tasks_are_cleared():
    """Ensure request_maintenance_stop removes lingering tasks."""
    async def runner():
        core_maintenance._maintenance_tasks.clear()
        core_maintenance._maintenance_started = True
        event = asyncio.Event()
        task = asyncio.create_task(event.wait())
        core_maintenance.register_maintenance_task(task)
        core_maintenance.request_maintenance_stop()
        await asyncio.sleep(0)  # let cancellation propagate
        assert task.cancelled()
        assert not core_maintenance._maintenance_tasks
        core_maintenance._maintenance_started = False

    asyncio.run(runner())
