import unittest

from ssh_gpu_checker.config import parse_ssh_hosts


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


if __name__ == "__main__":
    unittest.main()
