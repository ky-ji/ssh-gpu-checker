import unittest

from ssh_gpu_checker.models import GpuInfo, HostInspectionResult
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


if __name__ == "__main__":
    unittest.main()
