import unittest

from ssh_gpu_checker.config import filter_hosts_by_globs
from ssh_gpu_checker.dashboard_cli import build_parser, validate_loopback_host


class DashboardAllowlistTests(unittest.TestCase):
    def test_requires_at_least_one_glob(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowlist"):
            filter_hosts_by_globs(["node-a"], [])


class DashboardCliTests(unittest.TestCase):
    def test_requires_match_pattern(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args([])

    def test_collects_repeatable_match_patterns(self) -> None:
        args = build_parser().parse_args(
            ["--match", "THUSZ*", "--match", "lab-gpu-?"]
        )
        self.assertEqual(args.match, ["THUSZ*", "lab-gpu-?"])

    def test_rejects_non_loopback_bind(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            validate_loopback_host("0.0.0.0")

    def test_rejects_alternate_loopback_addresses(self) -> None:
        for value in ("127.0.0.2", "::1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "127.0.0.1"):
                    validate_loopback_host(value)

    def test_accepts_localhost_and_ipv4_loopback(self) -> None:
        self.assertEqual(validate_loopback_host("localhost"), "localhost")
        self.assertEqual(validate_loopback_host("127.0.0.1"), "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
