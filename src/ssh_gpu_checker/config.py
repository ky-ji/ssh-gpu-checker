from typing import List


def parse_ssh_hosts(text: str) -> List[str]:
    hosts: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        key, _, value = line.partition(' ')
        if key.lower() != 'host':
            continue
        for token in value.split():
            if '*' in token or '?' in token or token.startswith('!'):
                continue
            hosts.append(token)
    return hosts
