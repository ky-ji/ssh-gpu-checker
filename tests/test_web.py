import unittest

from fastapi.testclient import TestClient

from ssh_gpu_checker.web import create_app


class FakeCoordinator:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.touched = 0
        self.refreshed = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def touch_client(self) -> None:
        self.touched += 1

    def request_refresh(self) -> None:
        self.refreshed += 1

    def snapshot(self):
        return {"schema_version": 1, "hosts": [], "summary": {}}


class WebTests(unittest.TestCase):
    def setUp(self) -> None:
        self.coordinator = FakeCoordinator()
        self.client = TestClient(create_app(self.coordinator))

    def test_snapshot_touches_client_and_returns_cache(self) -> None:
        response = self.client.get("/api/v1/snapshot")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["schema_version"], 1)
        self.assertEqual(self.coordinator.touched, 1)

    def test_refresh_requires_json_and_returns_202(self) -> None:
        self.assertEqual(self.client.post("/api/v1/refresh").status_code, 415)

        good = self.client.post("/api/v1/refresh", json={})

        self.assertEqual(good.status_code, 202)
        self.assertEqual(self.coordinator.refreshed, 1)

    def test_refresh_rejects_invalid_json(self) -> None:
        response = self.client.post(
            "/api/v1/refresh",
            content="not-json",
            headers={"content-type": "application/json"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.coordinator.refreshed, 0)

    def test_rejects_untrusted_host_header(self) -> None:
        response = self.client.get("/healthz", headers={"host": "evil.example"})

        self.assertEqual(response.status_code, 400)

    def test_health_check_does_not_wake_scans(self) -> None:
        response = self.client.get("/healthz")

        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(self.coordinator.touched, 0)

    def test_lifespan_starts_and_stops_coordinator(self) -> None:
        with TestClient(create_app(self.coordinator)) as client:
            self.assertEqual(client.get("/healthz").status_code, 200)
            self.assertEqual(self.coordinator.started, 1)

        self.assertEqual(self.coordinator.stopped, 1)


if __name__ == "__main__":
    unittest.main()
