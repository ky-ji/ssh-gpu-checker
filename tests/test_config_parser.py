import unittest

from ssh_gpu_checker.config import filter_hosts_by_globs, parse_ssh_hosts


class ParseSshHostsTests(unittest.TestCase):
    def test_extracts_simple_host_aliases(self) -> None:
        text = """
Host alpha
  HostName 1.2.3.4

Host beta gamma
  User root
"""
        self.assertEqual(parse_ssh_hosts(text), ["alpha", "beta", "gamma"])

    def test_ignores_wildcard_and_negated_patterns(self) -> None:
        text = """
Host *
  ForwardAgent yes

Host !skip useful
  HostName 2.2.2.2
"""
        self.assertEqual(parse_ssh_hosts(text), ["useful"])

    def test_parses_tabs_comments_and_deduplicates(self) -> None:
        text = "Host\talpha beta # lab nodes\nHost alpha\nHost *\n"
        self.assertEqual(parse_ssh_hosts(text), ["alpha", "beta"])

    def test_filters_hosts_by_case_insensitive_globs(self) -> None:
        hosts = ["THUSZgnode1", "THUSZgnode2", "other"]
        self.assertEqual(
            filter_hosts_by_globs(hosts, ["thusz*2", "THUSZ*1"]),
            ["THUSZgnode1", "THUSZgnode2"],
        )


if __name__ == "__main__":
    unittest.main()
