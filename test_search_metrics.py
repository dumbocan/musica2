from app.core.search_metrics import (
    get_search_metrics,
    record_external_resolution,
    record_local_resolution,
)


def test_metrics_increment_per_user():
    record_local_resolution(42)
    record_local_resolution(None)
    record_external_resolution(42)
    record_external_resolution(42)
    metrics = get_search_metrics()
    assert metrics["local"]["global"] >= 2
    assert metrics["local"]["42"] == 1
    assert metrics["local"]["anon"] == 1
    assert metrics["external"]["42"] == 2
