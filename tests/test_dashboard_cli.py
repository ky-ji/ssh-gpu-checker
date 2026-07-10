import unittest

from ssh_gpu_checker.config import filter_hosts_by_globs
from ssh_gpu_checker.dashboard_cli import (
    build_parser,
    select_dashboard_hosts,
    validate_loopback_host,
)


class DashboardAllowlistTests(unittest.TestCase):
    def test_requires_at_least_one_glob(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowlist"):
            filter_hosts_by_globs(["node-a"], [])


class DashboardCliTests(unittest.TestCase):
    def test_match_pattern_is_optional(self) -> None:
        args = build_parser().parse_args([])
        self.assertIsNone(args.match)

    def test_collects_repeatable_match_patterns(self) -> None:
        args = build_parser().parse_args(
            ["--match", "THUSZ*", "--match", "lab-gpu-?"]
        )
        self.assertEqual(args.match, ["THUSZ*", "lab-gpu-?"])

    def test_uses_all_hosts_without_match_patterns(self) -> None:
        hosts = ["alpha", "THUSZgnode1", "beta"]
        self.assertEqual(select_dashboard_hosts(hosts, None), hosts)

    def test_filters_hosts_when_match_patterns_are_present(self) -> None:
        hosts = ["alpha", "THUSZgnode1", "THUSZgnode2"]
        self.assertEqual(
            select_dashboard_hosts(hosts, ["THUSZ*2"]),
            ["THUSZgnode2"],
        )

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
