import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ssh_gpu_checker.cli import load_hosts, main
from ssh_gpu_checker.models import GpuInfo, HostInspectionResult


class LoadHostsTests(unittest.TestCase):
    def test_filters_hosts_by_match_substring(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("Host alpha\nHost THUSZ1 THUSZ2\n", encoding="utf-8")
            self.assertEqual(load_hosts(config_path, match="THUSZ"), ["THUSZ1", "THUSZ2"])

    def test_loads_hosts_from_config_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "configs"
            config_dir.mkdir()
            (config_dir / "a.conf").write_text("Host alpha\n", encoding="utf-8")
            (config_dir / "b.conf").write_text("Host beta gamma\n", encoding="utf-8")
            self.assertEqual(load_hosts(config_dir, match=None), ["alpha", "beta", "gamma"])


class MainTests(unittest.TestCase):
    @patch("ssh_gpu_checker.cli.inspect_many_hosts")
    def test_main_prints_text_report(self, mock_inspect_many_hosts) -> None:
        mock_inspect_many_hosts.return_value = [
            HostInspectionResult(
                host="node-a",
                status="ok",
                gpus=[GpuInfo("0", "A100", 81920, 1024, 80896, 7)],
                message="",
            )
        ]

        buffer = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir, redirect_stdout(buffer):
            config_path = Path(tmpdir) / "config"
            config_path.write_text("Host node-a\n", encoding="utf-8")
            exit_code = main(["--config-path", str(config_path), "--top", "1"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Recommended Hosts", buffer.getvalue())
        self.assertIn("node-a", buffer.getvalue())

    @patch("ssh_gpu_checker.cli.inspect_many_hosts")
    def test_main_prints_json_report(self, mock_inspect_many_hosts) -> None:
        mock_inspect_many_hosts.return_value = [
            HostInspectionResult(
                host="node-a",
                status="ok",
                gpus=[GpuInfo("0", "A100", 81920, 1024, 80896, 7)],
                message="",
            )
        ]

        buffer = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir, redirect_stdout(buffer):
            config_path = Path(tmpdir) / "config"
            config_path.write_text("Host node-a\n", encoding="utf-8")
            exit_code = main(["--config-path", str(config_path), "--json", "--top", "1"])

        payload = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["results"][0]["host"], "node-a")
        self.assertEqual(payload["recommendations"][0]["host"], "node-a")
        self.assertEqual(payload["recommendations"][0]["best_gpu_free_memory_mb"], 80896)


if __name__ == "__main__":
    unittest.main()
