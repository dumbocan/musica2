from app.api import maintenance as maintenance_api


def test_stop_maintenance_calls_request():
    """Verify the maintenance stop endpoint triggers the stop helper."""
    called = []
    original = maintenance_api.request_maintenance_stop

    def fake_request_stop():
        called.append(True)

    maintenance_api.request_maintenance_stop = fake_request_stop
    try:
        result = maintenance_api.stop_maintenance()
        assert result == {"stopped": True}
        assert called == [True]
    finally:
        maintenance_api.request_maintenance_stop = original
