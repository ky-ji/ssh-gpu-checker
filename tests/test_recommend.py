import unittest

from ssh_gpu_checker.models import GpuInfo, HostInspectionResult
from ssh_gpu_checker.recommend import build_host_recommendations


class BuildHostRecommendationsTests(unittest.TestCase):
    def test_prefers_idle_host_over_busy_host_when_free_memory_is_close(self) -> None:
        idle_host = HostInspectionResult(
            host="idle-host",
            status="ok",
            gpus=[GpuInfo("0", "A100", 50000, 10000, 40000, 0)],
            message="",
        )
        busy_host = HostInspectionResult(
            host="busy-host",
            status="ok",
            gpus=[GpuInfo("0", "A100", 50000, 5000, 45000, 95)],
            message="",
        )

        recommendations = build_host_recommendations([busy_host, idle_host])

        self.assertEqual(recommendations[0].host, "idle-host")
        self.assertGreater(recommendations[0].score, recommendations[1].score)

    def test_applies_thresholds_and_top_limit(self) -> None:
        strong = HostInspectionResult(
            host="strong",
            status="ok",
            gpus=[GpuInfo("0", "A40", 46068, 0, 46068, 0)],
            message="",
        )
        medium = HostInspectionResult(
            host="medium",
            status="ok",
            gpus=[GpuInfo("0", "A40", 46068, 20000, 26068, 15)],
            message="",
        )
        weak = HostInspectionResult(
            host="weak",
            status="ok",
            gpus=[GpuInfo("0", "A40", 46068, 42000, 4068, 2)],
            message="",
        )

        recommendations = build_host_recommendations(
            [weak, medium, strong],
            min_free_mb=20000,
            max_util=20,
            top=1,
        )

        self.assertEqual([item.host for item in recommendations], ["strong"])

    def test_treats_unknown_utilization_as_busy_for_max_util_filter(self) -> None:
        unknown = HostInspectionResult(
            host="unknown",
            status="ok",
            gpus=[GpuInfo("0", "A100", 81920, 1024, 80896, None)],
            message="",
        )

        recommendations = build_host_recommendations([unknown], max_util=20)

        self.assertEqual(recommendations, [])


if __name__ == "__main__":
    unittest.main()
