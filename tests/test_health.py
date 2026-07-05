from health import start_health_server


def test_start_health_server_reuses_existing_live_thread(monkeypatch):
    class FakeThread:
        created = 0

        def __init__(self, target, daemon):
            FakeThread.created += 1
            self.target = target
            self.daemon = daemon

        def start(self):
            return None

        def is_alive(self):
            return True

    monkeypatch.setattr("health._health_thread", None)
    monkeypatch.setattr("health.threading.Thread", FakeThread)

    first = start_health_server()
    second = start_health_server()

    assert first is second
    assert FakeThread.created == 1
