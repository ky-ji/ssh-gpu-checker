import unittest
from datetime import datetime, timezone

from ssh_gpu_checker.models import GpuInfo, GpuProcessInfo, HostInspectionResult
from ssh_gpu_checker.snapshot import HostState, gpu_is_idle, serialize_snapshot


class SnapshotTests(unittest.TestCase):
    def test_serializes_summary_idle_and_stale_state(self) -> None:
        now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        gpu = GpuInfo(
            "0",
            "A100",
            1000,
            50,
            950,
            5,
            uuid="GPU-a",
            temperature_celsius=40,
            processes=[GpuProcessInfo(123, "alice", 50)],
        )
        state = HostState(alias="node-a")
        state.apply_result(
            HostInspectionResult("node-a", "ok", [gpu], ""), now, 8
        )
        state.stale = True

        payload = serialize_snapshot([state], active=True, generated_at=now)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["summary"]["hosts_online"], 1)
        self.assertEqual(payload["summary"]["gpus_idle"], 1)
        self.assertTrue(payload["hosts"][0]["stale"])
        self.assertEqual(
            payload["hosts"][0]["gpus"][0]["processes"][0]["username"],
            "alice",
        )

    def test_unknown_gpu_values_are_not_idle(self) -> None:
        self.assertFalse(
            gpu_is_idle(GpuInfo("0", "A100", 1000, 0, 1000, None))
        )

    def test_raw_error_details_are_not_exposed(self) -> None:
        now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        state = HostState(
            alias="node-a",
            status="auth_failed",
            message="alice@10.0.0.1: Permission denied\x1b[31m",
        )

        payload = serialize_snapshot([state], active=True, generated_at=now)

        message = payload["hosts"][0]["message"]
        self.assertEqual(message, "SSH authentication failed")
        self.assertNotIn("alice", message)

    def test_failure_retains_successful_gpu_data_as_stale(self) -> None:
        first = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        second = datetime(2026, 7, 10, 12, 1, tzinfo=timezone.utc)
        gpu = GpuInfo("0", "A100", 1000, 100, 900, 10)
        state = HostState(alias="node-a")
        state.apply_result(
            HostInspectionResult("node-a", "ok", [gpu], ""), first, 8
        )

        state.apply_result(
            HostInspectionResult("node-a", "unreachable", [], "timeout"),
            second,
            15,
        )

        self.assertEqual(state.gpus, [gpu])
        self.assertEqual(state.last_success_at, first)
        self.assertTrue(state.stale)
        self.assertEqual(state.failure_count, 1)


if __name__ == "__main__":
    unittest.main()
