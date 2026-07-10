import os
import subprocess
import unittest
from pathlib import Path


class DashboardLauncherTests(unittest.TestCase):
    def test_repository_launcher_uses_project_environment(self) -> None:
        root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment["PATH"] = "/usr/bin:/bin"

        completed = subprocess.run(
            [str(root / "bin" / "ssh-gpu-dashboard"), "--help"],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Serve the SSH GPU dashboard", completed.stdout)


if __name__ == "__main__":
    unittest.main()
