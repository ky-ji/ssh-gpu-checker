# SSH GPU Checker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Git-managed Python CLI plus Codex skill that reads SSH host aliases from `~/.ssh/config`, queries remote NVIDIA GPU state over SSH, and presents a sorted availability summary in one command.

**Architecture:** Keep the implementation split into small stdlib-only Python modules: one for SSH config parsing, one for remote inspection, one for rendering, and one CLI entrypoint. Expose the tool through a repository-local wrapper script and a thin skill that simply invokes the wrapper rather than duplicating any logic.

**Tech Stack:** Python 3 standard library, `unittest`, shell wrapper scripts, Markdown docs

---

### Task 1: Bootstrap Repository Layout

**Files:**
- Create: `/.gitignore`
- Create: `/README.md`
- Create: `/pyproject.toml`
- Create: `/bin/check-ssh-gpu`
- Create: `/src/ssh_gpu_checker/__init__.py`

- [ ] **Step 1: Add a minimal `.gitignore`**

```gitignore
__pycache__/
.pytest_cache/
.coverage
dist/
build/
*.egg-info/
```

- [ ] **Step 2: Add project metadata for editable execution**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "ssh-gpu-checker"
version = "0.1.0"
description = "Check GPU availability across SSH hosts"
requires-python = ">=3.10"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 3: Add the shell entrypoint**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
exec python3 -m ssh_gpu_checker.cli "$@"
```

- [ ] **Step 4: Add package marker**

```python
__all__ = []
```

- [ ] **Step 5: Add a README skeleton**

```markdown
# SSH GPU Checker

One command to inspect NVIDIA GPU availability across SSH aliases from `~/.ssh/config`.
```

- [ ] **Step 6: Verify the wrapper is executable**

Run: `chmod +x bin/check-ssh-gpu && head -n 5 bin/check-ssh-gpu`
Expected: script prints the shell wrapper header and `exec python3 -m ssh_gpu_checker.cli "$@"`


### Task 2: Define Parsing and Rendering Tests First

**Files:**
- Create: `/tests/test_config_parser.py`
- Create: `/tests/test_gpu_parser.py`
- Create: `/tests/test_renderer.py`

- [ ] **Step 1: Write the failing SSH config parser tests**

```python
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
```

- [ ] **Step 2: Write the failing GPU parser and status tests**

```python
import unittest

from ssh_gpu_checker.inspect import classify_ssh_failure, parse_nvidia_smi_csv


class ParseNvidiaSmiCsvTests(unittest.TestCase):
    def test_parses_rows_and_computes_free_memory(self) -> None:
        rows = parse_nvidia_smi_csv("0, NVIDIA A100, 81920, 1024, 7\n")
        self.assertEqual(rows[0].free_memory_mb, 80896)
        self.assertEqual(rows[0].gpu_index, "0")

    def test_classifies_missing_binary(self) -> None:
        self.assertEqual(
            classify_ssh_failure(127, "bash: nvidia-smi: command not found"),
            "no_nvidia_smi",
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Write the failing renderer tests**

```python
import unittest

from ssh_gpu_checker.models import GpuInfo, HostInspectionResult
from ssh_gpu_checker.render import render_report


class RenderReportTests(unittest.TestCase):
    def test_renders_summary_sorted_by_best_free_memory(self) -> None:
        host_a = HostInspectionResult(
            host="a",
            status="ok",
            gpus=[GpuInfo("0", "A100", 81920, 1024, 80896, 5)],
            message="",
        )
        host_b = HostInspectionResult(
            host="b",
            status="ok",
            gpus=[GpuInfo("0", "3090", 24576, 24000, 576, 92)],
            message="",
        )
        output = render_report([host_b, host_a])
        self.assertLess(output.index("a"), output.index("b"))
        self.assertIn("80896 MiB", output)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run tests to verify they fail correctly**

Run: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
Expected: FAIL with `ModuleNotFoundError` for `ssh_gpu_checker`


### Task 3: Implement Core Data Models and Parsers

**Files:**
- Create: `/src/ssh_gpu_checker/models.py`
- Create: `/src/ssh_gpu_checker/config.py`
- Create: `/src/ssh_gpu_checker/inspect.py`

- [ ] **Step 1: Add the shared dataclasses**

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GpuInfo:
    gpu_index: str
    name: str
    total_memory_mb: int
    used_memory_mb: int
    free_memory_mb: int
    utilization_gpu_percent: int


@dataclass(frozen=True)
class HostInspectionResult:
    host: str
    status: str
    gpus: list[GpuInfo] = field(default_factory=list)
    message: str = ""

    @property
    def best_free_memory_mb(self) -> int:
        if not self.gpus:
            return -1
        return max(gpu.free_memory_mb for gpu in self.gpus)
```

- [ ] **Step 2: Implement SSH host extraction**

```python
def parse_ssh_hosts(text: str) -> list[str]:
    hosts: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(" ")
        if key.lower() != "host":
            continue
        for token in value.split():
            if "*" in token or "?" in token or token.startswith("!"):
                continue
            hosts.append(token)
    return hosts
```

- [ ] **Step 3: Implement GPU CSV parsing and status classification**

```python
from ssh_gpu_checker.models import GpuInfo


def parse_nvidia_smi_csv(output: str) -> list[GpuInfo]:
    gpus: list[GpuInfo] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        index, name, total, used, utilization = [part.strip() for part in raw_line.split(",", 4)]
        total_mb = int(total)
        used_mb = int(used)
        gpus.append(
            GpuInfo(
                gpu_index=index,
                name=name,
                total_memory_mb=total_mb,
                used_memory_mb=used_mb,
                free_memory_mb=total_mb - used_mb,
                utilization_gpu_percent=int(utilization),
            )
        )
    return gpus


def classify_ssh_failure(returncode: int, stderr: str) -> str:
    message = stderr.lower()
    if "command not found" in message and "nvidia-smi" in message:
        return "no_nvidia_smi"
    if "permission denied" in message:
        return "auth_failed"
    if "timed out" in message or "could not resolve hostname" in message:
        return "unreachable"
    if returncode == 255:
        return "unreachable"
    return "error"
```

- [ ] **Step 4: Re-run tests**

Run: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
Expected: renderer test still FAILS because `render_report` is not implemented yet; parser tests PASS


### Task 4: Implement Rendering and Batch Inspection

**Files:**
- Create: `/src/ssh_gpu_checker/render.py`
- Modify: `/src/ssh_gpu_checker/inspect.py`

- [ ] **Step 1: Add a failing batch inspection test**

```python
import unittest

from ssh_gpu_checker.inspect import build_ssh_command


class BuildSshCommandTests(unittest.TestCase):
    def test_builds_ssh_command_with_timeout(self) -> None:
        command = build_ssh_command("node-a", timeout=12)
        self.assertEqual(command[:4], ["ssh", "-o", "BatchMode=yes", "-o"])
        self.assertIn("ConnectTimeout=12", command)
        self.assertEqual(command[-2:], ["node-a", "nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify the new failure**

Run: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
Expected: FAIL with `ImportError` for `build_ssh_command`

- [ ] **Step 3: Implement the SSH command builder and inspection helpers**

```python
GPU_QUERY = "nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits"


def build_ssh_command(host: str, timeout: int) -> list[str]:
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={timeout}",
        host,
        GPU_QUERY,
    ]
```

- [ ] **Step 4: Implement the renderer**

```python
from ssh_gpu_checker.models import HostInspectionResult


def render_report(results: list[HostInspectionResult]) -> str:
    sorted_results = sorted(results, key=lambda item: (item.status != "ok", -item.best_free_memory_mb, item.host))
    lines = ["Host Summary"]
    for result in sorted_results:
        if result.status == "ok":
            lines.append(f"{result.host}: best free {result.best_free_memory_mb} MiB")
        else:
            lines.append(f"{result.host}: {result.status} ({result.message})")
    lines.append("")
    for result in sorted_results:
        lines.append(f"[{result.host}] {result.status}")
        for gpu in result.gpus:
            lines.append(
                f"  GPU {gpu.gpu_index} | {gpu.name} | free {gpu.free_memory_mb} MiB / {gpu.total_memory_mb} MiB | util {gpu.utilization_gpu_percent}%"
            )
    return "\n".join(lines)
```

- [ ] **Step 5: Re-run tests**

Run: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
Expected: all tests PASS


### Task 5: Implement the CLI and Manual Invocation Path

**Files:**
- Create: `/src/ssh_gpu_checker/cli.py`
- Modify: `/src/ssh_gpu_checker/config.py`
- Modify: `/src/ssh_gpu_checker/inspect.py`

- [ ] **Step 1: Add a failing CLI selection test**

```python
import tempfile
import unittest
from pathlib import Path

from ssh_gpu_checker.cli import load_hosts


class LoadHostsTests(unittest.TestCase):
    def test_filters_hosts_by_match_substring(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.write_text("Host alpha\nHost THUSZ1 THUSZ2\n", encoding="utf-8")
            self.assertEqual(load_hosts(config_path, match="THUSZ"), ["THUSZ1", "THUSZ2"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify the failure**

Run: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
Expected: FAIL with `ImportError` for `ssh_gpu_checker.cli`

- [ ] **Step 3: Implement the CLI**

```python
import argparse
from pathlib import Path

from ssh_gpu_checker.config import parse_ssh_hosts


def load_hosts(config_path: Path, match: str | None) -> list[str]:
    hosts = parse_ssh_hosts(config_path.read_text(encoding="utf-8"))
    if match:
        hosts = [host for host in hosts if match.lower() in host.lower()]
    return hosts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-path", default="~/.ssh/config")
    parser.add_argument("--match")
    args = parser.parse_args()
    config_path = Path(args.config_path).expanduser()
    hosts = load_hosts(config_path, args.match)
    print("\n".join(hosts))
    return 0
```

- [ ] **Step 4: Re-run tests**

Run: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
Expected: CLI tests PASS; remaining tests stay green


### Task 6: Add Skill Wrapper and Install Helper

**Files:**
- Create: `/skills/check-ssh-gpu/SKILL.md`
- Create: `/tools/install_skill.sh`
- Modify: `/README.md`

- [ ] **Step 1: Add the install helper**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${HOME}/.codex/skills/check-ssh-gpu"
mkdir -p "$(dirname "${TARGET_DIR}")"
rm -rf "${TARGET_DIR}"
ln -s "${ROOT_DIR}/skills/check-ssh-gpu" "${TARGET_DIR}"
printf 'Installed skill at %s\n' "${TARGET_DIR}"
```

- [ ] **Step 2: Add the skill**

```markdown
---
name: check-ssh-gpu
description: Use when inspecting GPU memory availability or idle NVIDIA GPUs across SSH aliases defined in the local SSH config
---

# Check SSH GPU

Run the repository tool instead of reimplementing SSH or GPU parsing in the prompt.

## Quick Reference

- From the repository root: `bin/check-ssh-gpu`
- Filter hosts: `bin/check-ssh-gpu --match THUSZ`
- Alternate config: `bin/check-ssh-gpu --config-path ~/.ssh/config`
```

- [ ] **Step 3: Expand README usage**

```markdown
## Usage

```bash
bin/check-ssh-gpu
bin/check-ssh-gpu --match THUSZ
./tools/install_skill.sh
```
```

- [ ] **Step 4: Verify helper and wrapper**

Run: `bash tools/install_skill.sh && test -L ~/.codex/skills/check-ssh-gpu`
Expected: script prints installed path and the skill symlink exists


### Task 7: End-to-End Verification and Cleanup

**Files:**
- Modify: `/src/ssh_gpu_checker/cli.py`
- Modify: `/README.md`

- [ ] **Step 1: Extend CLI to perform real inspection and render output**

```python
parser.add_argument("--timeout", type=int, default=8)
parser.add_argument("--workers", type=int, default=8)
```

Use a thread pool to inspect hosts, then render with `render_report`.

- [ ] **Step 2: Run the automated test suite**

Run: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 3: Run a local manual smoke test**

Run: `bin/check-ssh-gpu --match THUSZ`
Expected: formatted summary output; any unreachable hosts are shown as statuses instead of crashing

- [ ] **Step 4: Review README and CLI help text**

Run: `bin/check-ssh-gpu --help`
Expected: shows config-path, match, timeout, and workers options

- [ ] **Step 5: Commit implementation**

```bash
git add .
git commit -m "Implement SSH GPU checker CLI and skill"
```
