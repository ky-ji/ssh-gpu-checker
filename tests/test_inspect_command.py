import unittest
from unittest.mock import patch

from ssh_gpu_checker.inspect import build_ssh_command, inspect_host


class BuildSshCommandTests(unittest.TestCase):
    def test_builds_ssh_command_with_timeout(self) -> None:
        command = build_ssh_command("node-a", timeout=12)
        self.assertEqual(command[:4], ["ssh", "-o", "BatchMode=yes", "-o"])
        self.assertIn("ConnectTimeout=12", command)
        self.assertEqual(
            command[-2:],
            [
                "node-a",
                "nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits",
            ],
        )

    @patch("ssh_gpu_checker.inspect.subprocess.run")
    def test_inspect_host_returns_ok_result(self, mock_run) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "0, NVIDIA A100, 81920, 1024, 7\n"
        mock_run.return_value.stderr = ""

        result = inspect_host("node-a", timeout=5)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.best_free_memory_mb, 80896)

    @patch("ssh_gpu_checker.inspect.subprocess.run")
    def test_inspect_host_classifies_auth_failure(self, mock_run) -> None:
        mock_run.return_value.returncode = 255
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "Permission denied (publickey)."

        result = inspect_host("node-a", timeout=5)

        self.assertEqual(result.status, "auth_failed")


if __name__ == "__main__":
    unittest.main()
