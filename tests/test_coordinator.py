import threading
import time
import unittest
from datetime import datetime, timezone

from ssh_gpu_checker.coordinator import ScanCoordinator
from ssh_gpu_checker.models import GpuInfo, HostInspectionResult


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def monotonic(self) -> float:
        return self.value

    def now(self) -> datetime:
        return datetime.fromtimestamp(self.value, timezone.utc)

    def advance(self, seconds: float) -> None:
        self.value += seconds


def wait_until(predicate, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition was not met before timeout")


class CoordinatorTests(unittest.TestCase):
    def test_healthy_and_failed_hosts_get_independent_delays(self) -> None:
        clock = FakeClock()
        coordinator = ScanCoordinator(
            ["ok", "bad"],
            collector=lambda host, timeout: HostInspectionResult(
                host, "ok" if host == "ok" else "unreachable", [], ""
            ),
            interval_seconds=8,
            monotonic=clock.monotonic,
            now=clock.now,
        )
        coordinator.start()
        try:
            coordinator.touch_client()
            wait_until(
                lambda: all(
                    host["last_attempt_at"]
                    for host in coordinator.snapshot()["hosts"]
                )
            )
            hosts = {host["alias"]: host for host in coordinator.snapshot()["hosts"]}
            self.assertEqual(hosts["ok"]["next_retry_seconds"], 8)
            self.assertEqual(hosts["bad"]["next_retry_seconds"], 15)
        finally:
            coordinator.stop()

    def test_coordinator_does_not_scan_without_a_client(self) -> None:
        calls = []
        coordinator = ScanCoordinator(
            ["node-a"],
            collector=lambda host, timeout: calls.append(host),
        )
        coordinator.start()
        try:
            time.sleep(0.05)
            self.assertEqual(calls, [])
        finally:
            coordinator.stop()

    def test_retry_progression_resets_after_success(self) -> None:
        clock = FakeClock()
        statuses = iter(["unreachable", "unreachable", "unreachable", "ok"])
        call_count = 0
        lock = threading.Lock()

        def collect(host, timeout):
            nonlocal call_count
            with lock:
                call_count += 1
            return HostInspectionResult(host, next(statuses), [], "")

        coordinator = ScanCoordinator(
            ["node-a"],
            collector=collect,
            interval_seconds=8,
            monotonic=clock.monotonic,
            now=clock.now,
        )
        coordinator.start()
        try:
            coordinator.touch_client()
            for expected_calls, expected_delay in ((1, 15), (2, 30), (3, 60)):
                wait_until(lambda: call_count >= expected_calls)
                wait_until(
                    lambda: coordinator.snapshot()["hosts"][0]["status"]
                    != "scanning"
                )
                self.assertEqual(
                    coordinator.snapshot()["hosts"][0]["next_retry_seconds"],
                    expected_delay,
                )
                clock.advance(expected_delay)
                coordinator.touch_client()
            wait_until(lambda: call_count >= 4)
            wait_until(
                lambda: coordinator.snapshot()["hosts"][0]["status"] == "ok"
            )
            self.assertEqual(
                coordinator.snapshot()["hosts"][0]["next_retry_seconds"], 8
            )
        finally:
            coordinator.stop()

    def test_failed_scan_retains_last_success_as_stale(self) -> None:
        clock = FakeClock()
        gpu = GpuInfo("0", "A100", 1000, 100, 900, 10)
        results = iter(
            [
                HostInspectionResult("node-a", "ok", [gpu], ""),
                HostInspectionResult("node-a", "unreachable", [], "timeout"),
            ]
        )
        call_count = 0

        def collect(host, timeout):
            nonlocal call_count
            call_count += 1
            return next(results)

        coordinator = ScanCoordinator(
            ["node-a"],
            collector=collect,
            interval_seconds=8,
            monotonic=clock.monotonic,
            now=clock.now,
        )
        coordinator.start()
        try:
            coordinator.touch_client()
            wait_until(lambda: call_count == 1)
            clock.advance(8)
            coordinator.touch_client()
            wait_until(lambda: call_count == 2)
            wait_until(
                lambda: coordinator.snapshot()["hosts"][0]["status"]
                == "unreachable"
            )
            host = coordinator.snapshot()["hosts"][0]
            self.assertTrue(host["stale"])
            self.assertEqual(len(host["gpus"]), 1)
        finally:
            coordinator.stop()

    def test_activity_expires_after_thirty_seconds(self) -> None:
        clock = FakeClock()
        calls = 0

        def collect(host, timeout):
            nonlocal calls
            calls += 1
            return HostInspectionResult(host, "ok", [], "")

        coordinator = ScanCoordinator(
            ["node-a"],
            collector=collect,
            interval_seconds=60,
            inactive_after_seconds=30,
            monotonic=clock.monotonic,
            now=clock.now,
        )
        coordinator.start()
        try:
            coordinator.touch_client()
            wait_until(lambda: calls == 1)
            clock.advance(31)
            self.assertFalse(coordinator.snapshot()["active"])
            time.sleep(0.05)
            self.assertEqual(calls, 1)
        finally:
            coordinator.stop()

    def test_refresh_while_busy_coalesces_without_overlap(self) -> None:
        started = threading.Event()
        release = threading.Event()
        calls = 0
        active_calls = 0
        maximum_active = 0
        lock = threading.Lock()

        def collect(host, timeout):
            nonlocal calls, active_calls, maximum_active
            with lock:
                calls += 1
                current_call = calls
                active_calls += 1
                maximum_active = max(maximum_active, active_calls)
            if current_call == 1:
                started.set()
                release.wait(timeout=1)
            with lock:
                active_calls -= 1
            return HostInspectionResult(host, "ok", [], "")

        coordinator = ScanCoordinator(
            ["node-a"], collector=collect, interval_seconds=60
        )
        coordinator.start()
        try:
            coordinator.touch_client()
            self.assertTrue(started.wait(timeout=1))
            coordinator.request_refresh()
            coordinator.request_refresh()
            coordinator.request_refresh()
            release.set()
            wait_until(lambda: calls == 2)
            time.sleep(0.05)
            self.assertEqual(calls, 2)
            self.assertEqual(maximum_active, 1)
        finally:
            release.set()
            coordinator.stop()


if __name__ == "__main__":
    unittest.main()
