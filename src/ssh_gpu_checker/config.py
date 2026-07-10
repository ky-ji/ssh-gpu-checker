from fnmatch import fnmatchcase
from typing import Iterable, List, Sequence


def parse_ssh_hosts(text: str) -> List[str]:
    hosts: List[str] = []
    seen = set()
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or parts[0].lower() != "host":
            continue
        for token in parts[1].split():
            if "*" in token or "?" in token or token.startswith("!"):
                continue
            if token not in seen:
                seen.add(token)
                hosts.append(token)
    return hosts


def filter_hosts_by_globs(
    hosts: Iterable[str], patterns: Sequence[str]
) -> List[str]:
    if not patterns:
        raise ValueError("dashboard host allowlist requires at least one glob")
    lowered_patterns = [pattern.lower() for pattern in patterns]
    return [
        host
        for host in hosts
        if any(fnmatchcase(host.lower(), pattern) for pattern in lowered_patterns)
    ]
