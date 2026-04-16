import unittest

from ssh_gpu_checker.models import GpuInfo, HostInspectionResult
from ssh_gpu_checker.recommend import HostRecommendation
from ssh_gpu_checker.render import render_report


class RenderReportTests(unittest.TestCase):
    def test_renders_summary_sorted_by_best_free_memory(self) -> None:
        host_a = HostInspectionResult(
            host="a",
            status="ok",
            gpus=[GpuInfo("0", "A100", 81920, 1024, 80896, 5)],
            message="",
        )
        host_b = HostInspectionResult(
            host="b",
            status="ok",
            gpus=[GpuInfo("0", "3090", 24576, 24000, 576, 92)],
            message="",
        )
        output = render_report([host_b, host_a])
        self.assertLess(output.index("a"), output.index("b"))
        self.assertIn("80896 MiB", output)

    def test_renders_recommended_hosts_section(self) -> None:
        result = HostInspectionResult(
            host="node-a",
            status="ok",
            gpus=[GpuInfo("0", "A40", 46068, 0, 46068, 0)],
            message="",
        )
        recommendation = HostRecommendation(
            host="node-a",
            score=100.0,
            best_gpu_index="0",
            best_gpu_name="A40",
            best_gpu_free_memory_mb=46068,
            best_gpu_total_memory_mb=46068,
            best_gpu_utilization_percent=0,
            reason="best GPU free 46068 MiB, util 0%",
        )

        output = render_report([result], [recommendation])

        self.assertIn("Recommended Hosts", output)
        self.assertIn("1. node-a", output)
        self.assertIn("best GPU free 46068 MiB", output)


if __name__ == "__main__":
    unittest.main()
