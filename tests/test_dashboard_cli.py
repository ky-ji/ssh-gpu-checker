import unittest

from ssh_gpu_checker.config import filter_hosts_by_globs


class DashboardAllowlistTests(unittest.TestCase):
    def test_requires_at_least_one_glob(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowlist"):
            filter_hosts_by_globs(["node-a"], [])


if __name__ == "__main__":
    unittest.main()
