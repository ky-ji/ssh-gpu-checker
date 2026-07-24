import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ssh_gpu_checker.inspect import PROCESS_QUERY, build_ssh_command, inspect_host


class BuildSshCommandTests(unittest.TestCase):
    def test_builds_ssh_command_with_timeout(self) -> None:
        command = build_ssh_command("node-a", timeout=12)
        self.assertEqual(command[:4], ["ssh", "-o", "BatchMode=yes", "-o"])
        self.assertIn("ConnectTimeout=12", command)
        self.assertEqual(command[-2], "node-a")
        self.assertIn("printf '__GPU__", command[-1])
        self.assertIn("uuid", command[-1])
        self.assertIn("temperature.gpu", command[-1])
        self.assertIn("query-compute-apps", command[-1])
        self.assertEqual(command[-1].count("ps -eo pid=,user="), 1)
        self.assertNotIn("ps -o user= -p", command[-1])
        self.assertNotIn("node-a", command[-1])

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

    @patch("ssh_gpu_checker.inspect.subprocess.run")
    def test_inspect_host_returns_parse_error(self, mock_run) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "__GPU__\nbad,row\n__PROC__\n"
        mock_run.return_value.stderr = ""

        result = inspect_host("node-a", timeout=5)

        self.assertEqual(result.status, "parse_error")

    @patch("ssh_gpu_checker.inspect.subprocess.run")
    def test_inspect_host_handles_missing_local_ssh(self, mock_run) -> None:
        mock_run.side_effect = FileNotFoundError("ssh")

        result = inspect_host("node-a", timeout=5)

        self.assertEqual(result.status, "error")


class ProcessQueryTests(unittest.TestCase):
    def test_uses_one_process_snapshot_for_repeated_gpu_pids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bin_dir = Path(temp_dir)
            calls_path = bin_dir / "ps-calls"
            nvidia_smi = bin_dir / "nvidia-smi"
            nvidia_smi.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' "
                "'GPU-a, 42, 100' "
                "'GPU-b, 42, 200' "
                "'GPU-b, 84, 300' "
                "'GPU-c, 999, 400'\n"
            )
            nvidia_smi.chmod(0o755)
            ps = bin_dir / "ps"
            ps.write_text(
                "#!/bin/sh\n"
                "printf 'called\\n' >> \"$PS_CALLS_PATH\"\n"
                "printf '%s\\n' '  42 alice' '  84 bob'\n"
            )
            ps.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["PS_CALLS_PATH"] = str(calls_path)

            completed = subprocess.run(
                ["sh", "-c", PROCESS_QUERY],
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )

            self.assertEqual(
                completed.stdout.splitlines(),
                [
                    "GPU-a,42,100,alice",
                    "GPU-b,42,200,alice",
                    "GPU-b,84,300,bob",
                    "GPU-c,999,400,unknown",
                ],
            )
            self.assertEqual(calls_path.read_text().splitlines(), ["called"])


if __name__ == "__main__":
    unittest.main()
