# SSH GPU Dashboard MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight, local-only, agentless web dashboard that continuously shows current GPU state for an allowlisted set of SSH aliases.

**Architecture:** Keep the existing OpenSSH collector and CLI behavior, add a per-host background coordinator with an in-memory snapshot store, and serve a build-free host-strip dashboard through FastAPI. Browser reads never launch SSH directly; they only wake the coordinator and read cached state.

**Tech Stack:** Python 3.9+, standard-library `unittest`, FastAPI, Uvicorn, plain HTML/CSS/JavaScript, system OpenSSH, NVIDIA `nvidia-smi`.

---

## File Map

**Create**

- `src/ssh_gpu_checker/snapshot.py` — dashboard host state, summary calculation, versioned JSON serialization.
- `src/ssh_gpu_checker/coordinator.py` — per-host scheduling, bounded concurrency, retry backoff, inactivity pause, single-flight scans.
- `src/ssh_gpu_checker/web.py` — FastAPI factory, loopback/trusted-host boundary, API and static routes.
- `src/ssh_gpu_checker/dashboard_cli.py` — dashboard arguments, allowlist resolution, coordinator/application startup.
- `src/ssh_gpu_checker/static/index.html` — accessible dashboard document.
- `src/ssh_gpu_checker/static/dashboard.css` — host-strip layout and responsive styles.
- `src/ssh_gpu_checker/static/dashboard.js` — safe DOM rendering, snapshot polling, manual refresh.
- `bin/ssh-gpu-dashboard` — repository-local dashboard launcher.
- `tests/test_snapshot.py`, `tests/test_coordinator.py`, `tests/test_web.py`, `tests/test_dashboard_cli.py`.

**Modify**

- `pyproject.toml`, `.gitignore`, `README.md`.
- `src/ssh_gpu_checker/config.py`, `cli.py`, `models.py`, `inspect.py`.
- `tests/test_config_parser.py`, `test_gpu_parser.py`, `test_inspect_command.py`.

## Task 1: Packaging and SSH Alias Allowlist

**Files:**

- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Modify: `src/ssh_gpu_checker/config.py`
- Modify: `tests/test_config_parser.py`
- Create: `tests/test_dashboard_cli.py`

- [ ] **Step 1: Add failing config parser and dashboard glob tests**

Add to `tests/test_config_parser.py`:

```python
from ssh_gpu_checker.config import filter_hosts_by_globs, parse_ssh_hosts

def test_parses_tabs_comments_and_deduplicates(self) -> None:
    text = "Host\talpha beta # lab nodes\nHost alpha\nHost *\n"
    self.assertEqual(parse_ssh_hosts(text), ["alpha", "beta"])

def test_filters_hosts_by_case_insensitive_globs(self) -> None:
    hosts = ["THUSZgnode1", "THUSZgnode2", "other"]
    self.assertEqual(
        filter_hosts_by_globs(hosts, ["thusz*2", "THUSZ*1"]),
        ["THUSZgnode1", "THUSZgnode2"],
    )
```

Create `tests/test_dashboard_cli.py`:

```python
import unittest
from ssh_gpu_checker.config import filter_hosts_by_globs

class DashboardAllowlistTests(unittest.TestCase):
    def test_requires_at_least_one_glob(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowlist"):
            filter_hosts_by_globs(["node-a"], [])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run focused tests and verify failure**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest \
  tests.test_config_parser tests.test_dashboard_cli -v
```

Expected: import failure because `filter_hosts_by_globs` is not defined, plus the parser assertion failure.

- [ ] **Step 3: Implement robust discovery and dashboard-only glob matching**

Implement in `config.py`:

```python
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

def filter_hosts_by_globs(hosts: Iterable[str], patterns: Sequence[str]) -> List[str]:
    if not patterns:
        raise ValueError("dashboard host allowlist requires at least one glob")
    lowered = [pattern.lower() for pattern in patterns]
    return [host for host in hosts if any(
        fnmatchcase(host.lower(), pattern) for pattern in lowered
    )]
```

Do not change `cli.load_hosts(config_path, match)` substring semantics.

- [ ] **Step 4: Add dependencies and package data**

Update `pyproject.toml`:

```toml
[project]
name = "ssh-gpu-checker"
version = "0.2.0"
description = "Check and monitor GPU availability across SSH hosts"
requires-python = ">=3.9"
dependencies = ["fastapi>=0.115,<1", "uvicorn>=0.30,<1"]

[project.optional-dependencies]
test = ["httpx>=0.27,<1"]

[project.scripts]
ssh-gpu-checker = "ssh_gpu_checker.cli:main"
ssh-gpu-dashboard = "ssh_gpu_checker.dashboard_cli:main"

[tool.setuptools.package-data]
ssh_gpu_checker = ["static/*.html", "static/*.css", "static/*.js"]
```

Add `.venv/` and `.superpowers/` to `.gitignore`.

- [ ] **Step 5: Create the environment and verify packaging**

```bash
uv venv .venv --python 3.9
uv pip install --python .venv/bin/python -e '.[test]'
uv pip check --python .venv/bin/python
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Expected: editable install succeeds, dependency check passes, and all tests pass.

- [ ] **Step 6: Commit**

```bash
git add .gitignore pyproject.toml src/ssh_gpu_checker/config.py \
  tests/test_config_parser.py tests/test_dashboard_cli.py
git commit -m "Prepare dashboard packaging and host allowlist"
```

## Task 2: Extended GPU and Process Collection

**Files:**

- Modify: `src/ssh_gpu_checker/models.py`
- Modify: `src/ssh_gpu_checker/inspect.py`
- Modify: `tests/test_gpu_parser.py`
- Modify: `tests/test_inspect_command.py`

- [ ] **Step 1: Add failing extended parser tests**

Add to `tests/test_gpu_parser.py`:

```python
from ssh_gpu_checker.inspect import parse_nvidia_smi_output

def test_parses_extended_gpu_and_process_rows(self) -> None:
    output = """__GPU__
0, GPU-abc, NVIDIA RTX 4090, 49140, 1024, [N/A], 42
__PROC__
GPU-abc, 1234, 768, alice
"""
    rows = parse_nvidia_smi_output(output)
    self.assertEqual(rows[0].uuid, "GPU-abc")
    self.assertEqual(rows[0].temperature_celsius, 42)
    self.assertIsNone(rows[0].utilization_gpu_percent)
    self.assertEqual(rows[0].processes[0].pid, 1234)
    self.assertEqual(rows[0].processes[0].username, "alice")

def test_rejects_malformed_gpu_row(self) -> None:
    with self.assertRaisesRegex(ValueError, "GPU row"):
        parse_nvidia_smi_output("__GPU__\nnot,enough,fields\n__PROC__\n")
```

Add to `tests/test_inspect_command.py`:

```python
@patch("ssh_gpu_checker.inspect.subprocess.run")
def test_inspect_host_returns_parse_error(self, mock_run) -> None:
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "__GPU__\nbad,row\n__PROC__\n"
    mock_run.return_value.stderr = ""
    result = inspect_host("node-a", timeout=5)
    self.assertEqual(result.status, "parse_error")
```

- [ ] **Step 2: Run tests and verify failure**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_gpu_parser tests.test_inspect_command -v
```

Expected: import/attribute failures for the new parser and model fields.

- [ ] **Step 3: Extend models without breaking positional callers**

Append defaulted fields in `models.py`:

```python
@dataclass(frozen=True)
class GpuProcessInfo:
    pid: int
    username: str
    used_memory_mb: Optional[int]

@dataclass(frozen=True)
class GpuInfo:
    gpu_index: str
    name: str
    total_memory_mb: int
    used_memory_mb: int
    free_memory_mb: int
    utilization_gpu_percent: Optional[int]
    uuid: Optional[str] = None
    temperature_celsius: Optional[int] = None
    processes: List[GpuProcessInfo] = field(default_factory=list)
```

- [ ] **Step 4: Implement a fixed combined query and CSV parser**

In `inspect.py`, define the complete fixed payload:

```python
GPU_QUERY = (
    "nvidia-smi --query-gpu=index,uuid,name,memory.total,memory.used,"
    "utilization.gpu,temperature.gpu --format=csv,noheader,nounits"
)
PROCESS_QUERY = (
    "nvidia-smi --query-compute-apps=gpu_uuid,pid,used_gpu_memory "
    "--format=csv,noheader,nounits 2>/dev/null | "
    "while IFS=, read -r uuid pid used; do "
    "pid=$(printf '%s' \"$pid\" | tr -d ' '); "
    "case \"$pid\" in ''|*[!0-9]*) continue ;; esac; "
    "user=$(ps -o user= -p \"$pid\" 2>/dev/null | awk '{$1=$1;print}'); "
    "printf '%s,%s,%s,%s\\n' \"$uuid\" \"$pid\" \"$used\" \"${user:-unknown}\"; "
    "done"
)
REMOTE_QUERY = (
    "printf '__GPU__\\n'; " + GPU_QUERY
    + "; printf '__PROC__\\n'; " + PROCESS_QUERY
)
```

Use `csv.reader`, split only on `__GPU__`/`__PROC__`, parse unavailable numbers as `None`, join process rows by GPU UUID, and expose:

```python
def _optional_int(value: str) -> Optional[int]:
    normalized = value.strip()
    if normalized in {"", "N/A", "[N/A]"}:
        return None
    return int(normalized)

def parse_nvidia_smi_output(output: str) -> List[GpuInfo]:
    if "__GPU__" not in output or "__PROC__" not in output:
        return parse_nvidia_smi_csv(output)
    gpu_part, process_part = output.split("__PROC__", 1)
    gpu_part = gpu_part.split("__GPU__", 1)[1]
    processes_by_uuid: Dict[str, List[GpuProcessInfo]] = {}
    for row in csv.reader(StringIO(process_part)):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != 4:
            raise ValueError(f"Malformed process row: {row!r}")
        uuid, pid, used, username = [cell.strip() for cell in row]
        processes_by_uuid.setdefault(uuid, []).append(GpuProcessInfo(
            pid=int(pid),
            username=username or "unknown",
            used_memory_mb=_optional_int(used),
        ))
    gpus: List[GpuInfo] = []
    for row in csv.reader(StringIO(gpu_part)):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != 7:
            raise ValueError(f"Malformed GPU row: {row!r}")
        index, uuid, name, total, used, utilization, temperature = [
            cell.strip() for cell in row
        ]
        total_mb = int(total)
        used_mb = int(used)
        gpus.append(GpuInfo(
            index, name, total_mb, used_mb, total_mb - used_mb,
            _optional_int(utilization), uuid=uuid,
            temperature_celsius=_optional_int(temperature),
            processes=processes_by_uuid.get(uuid, []),
        ))
    return gpus
```

Keep `parse_nvidia_smi_csv` as a compatibility wrapper. The constant remote payload queries index, UUID, name, total/used memory, utilization and temperature, followed by GPU UUID, numeric PID, process memory and username. No browser value is interpolated.

- [ ] **Step 5: Isolate parse and local process errors**

Update `inspect_host`:

```python
try:
    gpus = parse_nvidia_smi_output(stdout)
except (ValueError, csv.Error) as exc:
    return HostInspectionResult(host, "parse_error", [], str(exc))
```

Catch local `OSError` from a missing `ssh` binary and return `status="error"`.

- [ ] **Step 6: Run focused and full tests**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_gpu_parser tests.test_inspect_command -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Expected: every test passes.

- [ ] **Step 7: Commit**

```bash
git add src/ssh_gpu_checker/models.py src/ssh_gpu_checker/inspect.py \
  tests/test_gpu_parser.py tests/test_inspect_command.py
git commit -m "Collect dashboard GPU and process metrics"
```

## Task 3: Versioned Snapshot Model

**Files:**

- Create: `src/ssh_gpu_checker/snapshot.py`
- Create: `tests/test_snapshot.py`

- [ ] **Step 1: Write failing snapshot tests**

Create `tests/test_snapshot.py`:

```python
import unittest
from datetime import datetime, timezone

from ssh_gpu_checker.models import GpuInfo, HostInspectionResult
from ssh_gpu_checker.snapshot import HostState, gpu_is_idle, serialize_snapshot

class SnapshotTests(unittest.TestCase):
    def test_serializes_summary_idle_and_stale_state(self) -> None:
        now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        gpu = GpuInfo("0", "A100", 1000, 50, 950, 5,
                      uuid="GPU-a", temperature_celsius=40)
        state = HostState(alias="node-a")
        state.apply_result(HostInspectionResult("node-a", "ok", [gpu], ""), now, 8)
        state.stale = True
        payload = serialize_snapshot([state], active=True, generated_at=now)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["summary"]["hosts_online"], 1)
        self.assertEqual(payload["summary"]["gpus_idle"], 1)
        self.assertTrue(payload["hosts"][0]["stale"])

    def test_unknown_gpu_values_are_not_idle(self) -> None:
        self.assertFalse(gpu_is_idle(GpuInfo("0", "A100", 1000, 0, 1000, None)))

    def test_raw_error_details_are_not_exposed(self) -> None:
        now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        state = HostState(alias="node-a", status="auth_failed",
                          message="alice@10.0.0.1: Permission denied\x1b[31m")
        payload = serialize_snapshot([state], active=True, generated_at=now)
        message = payload["hosts"][0]["message"]
        self.assertEqual(message, "SSH authentication failed")
        self.assertNotIn("alice", message)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify failure**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_snapshot -v
```

Expected: `ModuleNotFoundError` for `ssh_gpu_checker.snapshot`.

- [ ] **Step 3: Implement host state and serializer**

Expose in `snapshot.py`:

```python
def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()

PUBLIC_MESSAGES = {
    "unreachable": "Host unreachable",
    "auth_failed": "SSH authentication failed",
    "no_nvidia_smi": "nvidia-smi is unavailable",
    "no_gpu_data": "No GPU data returned",
    "parse_error": "GPU data could not be parsed",
    "error": "Unexpected collection error",
}

@dataclass
class HostState:
    alias: str
    status: str = "pending"
    gpus: List[GpuInfo] = field(default_factory=list)
    message: str = ""
    last_attempt_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    stale: bool = False
    next_retry_seconds: int = 0
    failure_count: int = 0

    def apply_result(self, result: HostInspectionResult,
                     observed_at: datetime, next_delay_seconds: float) -> None:
        self.last_attempt_at = observed_at
        self.status = result.status
        self.message = result.message
        self.next_retry_seconds = int(next_delay_seconds)
        if result.status == "ok":
            self.gpus = list(result.gpus)
            self.last_success_at = observed_at
            self.stale = False
            self.failure_count = 0
        else:
            self.failure_count += 1
            self.stale = self.last_success_at is not None

def gpu_is_idle(gpu: GpuInfo) -> bool:
    return (
        gpu.utilization_gpu_percent is not None
        and gpu.total_memory_mb > 0
        and gpu.utilization_gpu_percent < 10
        and gpu.used_memory_mb / gpu.total_memory_mb < 0.10
    )

def serialize_snapshot(states: Sequence[HostState], active: bool,
                       generated_at: datetime) -> Dict[str, object]:
    hosts = []
    for state in states:
        hosts.append({
            "alias": state.alias,
            "status": state.status,
            "message": PUBLIC_MESSAGES.get(state.status, ""),
            "last_attempt_at": _iso(state.last_attempt_at),
            "last_success_at": _iso(state.last_success_at),
            "stale": state.stale,
            "next_retry_seconds": state.next_retry_seconds,
            "gpus": [asdict(gpu) for gpu in state.gpus],
        })
    all_gpus = [gpu for state in states for gpu in state.gpus]
    return {
        "schema_version": 1,
        "generated_at": _iso(generated_at),
        "active": active,
        "summary": {
            "hosts_total": len(states),
            "hosts_online": sum(state.status == "ok" for state in states),
            "hosts_stale": sum(state.stale for state in states),
            "gpus_total": len(all_gpus),
            "gpus_idle": sum(gpu_is_idle(gpu) for gpu in all_gpus),
        },
        "hosts": hosts,
    }
```

Preserve host input order. Use timezone-aware ISO-8601 strings. On failure after success, retain GPU rows and set `stale=True`; never-successful hosts have no GPU rows.

- [ ] **Step 4: Run focused and full tests**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_snapshot -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ssh_gpu_checker/snapshot.py tests/test_snapshot.py
git commit -m "Add versioned dashboard snapshots"
```

## Task 4: Per-Host Scan Coordinator

**Files:**

- Create: `src/ssh_gpu_checker/coordinator.py`
- Create: `tests/test_coordinator.py`

- [ ] **Step 1: Add failing deterministic scheduling tests**

Create `tests/test_coordinator.py`:

```python
import unittest
from datetime import datetime, timezone
from ssh_gpu_checker.coordinator import ScanCoordinator
from ssh_gpu_checker.models import HostInspectionResult

class FakeClock:
    def __init__(self) -> None: self.value = 100.0
    def monotonic(self) -> float: return self.value
    def now(self) -> datetime: return datetime.fromtimestamp(self.value, timezone.utc)
    def advance(self, seconds: float) -> None: self.value += seconds

class CoordinatorTests(unittest.TestCase):
    def test_healthy_and_failed_hosts_get_independent_delays(self) -> None:
        clock = FakeClock()
        coordinator = ScanCoordinator(
            ["ok", "bad"],
            collector=lambda host, timeout: HostInspectionResult(
                host, "ok" if host == "ok" else "unreachable", [], ""
            ),
            interval_seconds=8,
            monotonic=clock.monotonic,
            now=clock.now,
        )
        coordinator.touch_client()
        coordinator.run_due_synchronously_for_test()
        self.assertEqual(coordinator.delay_for("ok"), 8)
        self.assertEqual(coordinator.delay_for("bad"), 15)

    def test_inactive_coordinator_does_not_scan(self) -> None:
        calls = []
        clock = FakeClock()
        coordinator = ScanCoordinator(
            ["node-a"],
            collector=lambda host, timeout: calls.append(host),
            monotonic=clock.monotonic,
            now=clock.now,
        )
        coordinator.run_due_synchronously_for_test()
        self.assertEqual(calls, [])
```

Add these deterministic cases in the same test class:

```python
    def test_retry_progression_resets_after_success(self) -> None:
        clock = FakeClock()
        statuses = iter(["unreachable", "unreachable", "unreachable", "ok"])
        coordinator = ScanCoordinator(
            ["node-a"],
            collector=lambda host, timeout: HostInspectionResult(
                host, next(statuses), [], ""
            ),
            monotonic=clock.monotonic,
            now=clock.now,
        )
        coordinator.touch_client()
        for expected_delay in (15, 30, 60):
            coordinator.run_due_synchronously_for_test()
            self.assertEqual(coordinator.delay_for("node-a"), expected_delay)
            clock.advance(expected_delay)
            coordinator.touch_client()
        coordinator.run_due_synchronously_for_test()
        self.assertEqual(coordinator.delay_for("node-a"), 8)

    def test_failed_scan_retains_last_success_as_stale(self) -> None:
        clock = FakeClock()
        gpu = GpuInfo("0", "A100", 1000, 100, 900, 10)
        results = iter([
            HostInspectionResult("node-a", "ok", [gpu], ""),
            HostInspectionResult("node-a", "unreachable", [], "timeout"),
        ])
        coordinator = ScanCoordinator(
            ["node-a"], collector=lambda host, timeout: next(results),
            monotonic=clock.monotonic, now=clock.now,
        )
        coordinator.touch_client()
        coordinator.run_due_synchronously_for_test()
        clock.advance(8)
        coordinator.touch_client()
        coordinator.run_due_synchronously_for_test()
        host = coordinator.snapshot()["hosts"][0]
        self.assertTrue(host["stale"])
        self.assertEqual(len(host["gpus"]), 1)

    def test_activity_expires_after_thirty_seconds(self) -> None:
        calls = []
        clock = FakeClock()
        coordinator = ScanCoordinator(
            ["node-a"],
            collector=lambda host, timeout: calls.append(host),
            monotonic=clock.monotonic,
            now=clock.now,
        )
        coordinator.touch_client()
        clock.advance(31)
        coordinator.run_due_synchronously_for_test()
        self.assertEqual(calls, [])
```

Add one event-driven background test whose collector records concurrent calls, blocks
on its first invocation, and receives multiple `request_refresh()` calls while busy.
Release it and assert that exactly one follow-up scan occurs and that maximum
concurrency for the host remains one. Always call `stop()` in `finally`.

- [ ] **Step 2: Run and verify failure**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_coordinator -v
```

Expected: module import failure.

- [ ] **Step 3: Implement coordinator surface**

Expose:

```python
class ScanCoordinator:
    def __init__(
        self,
        hosts: Sequence[str],
        collector: Callable[[str, int], HostInspectionResult],
        interval_seconds: float = 8.0,
        timeout_seconds: int = 8,
        workers: int = 8,
        inactive_after_seconds: float = 30.0,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        if not hosts:
            raise ValueError("coordinator requires at least one host")
        self._hosts = list(hosts)
        self._collector = collector
        self._interval = interval_seconds
        self._timeout = timeout_seconds
        self._inactive_after = inactive_after_seconds
        self._monotonic = monotonic
        self._now = now
        self._condition = threading.Condition()
        self._states = {host: HostState(host) for host in hosts}
        self._next_due = {host: 0.0 for host in hosts}
        self._busy = set()
        self._refresh_pending = set()
        self._last_client_seen: Optional[float] = None
        self._stop_requested = False
        self._executor = ThreadPoolExecutor(max_workers=min(workers, len(hosts)))
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        with self._condition:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._condition:
            self._stop_requested = True
            self._condition.notify_all()
        if self._thread:
            self._thread.join(timeout=5)
        self._executor.shutdown(wait=True, cancel_futures=True)

    def touch_client(self) -> None:
        with self._condition:
            self._last_client_seen = self._monotonic()
            self._condition.notify_all()

    def request_refresh(self) -> None:
        with self._condition:
            self._last_client_seen = self._monotonic()
            for host in self._hosts:
                if host in self._busy:
                    self._refresh_pending.add(host)
                else:
                    self._next_due[host] = 0.0
            self._condition.notify_all()

    def snapshot(self) -> Dict[str, object]:
        with self._condition:
            states = [copy.deepcopy(self._states[host]) for host in self._hosts]
            active = self._is_active(self._monotonic())
        return serialize_snapshot(states, active, self._now())

    def run_due_synchronously_for_test(self) -> None:
        now_value = self._monotonic()
        if not self._is_active(now_value):
            return
        for host in self._due_hosts(now_value):
            result = self._collector(host, self._timeout)
            self._apply_result(host, result, now_value)

    def delay_for(self, host: str) -> int:
        return max(0, int(self._next_due[host] - self._monotonic()))

    def _is_active(self, now_value: float) -> bool:
        return (
            self._last_client_seen is not None
            and now_value - self._last_client_seen <= self._inactive_after
        )

    def _due_hosts(self, now_value: float) -> List[str]:
        return [
            host for host in self._hosts
            if host not in self._busy and self._next_due[host] <= now_value
        ]

    def _retry_delay(self, failure_number: int) -> int:
        return (15, 30, 60)[min(max(failure_number, 1) - 1, 2)]

    def _apply_result(self, host: str, result: HostInspectionResult,
                      observed_monotonic: float) -> None:
        state = self._states[host]
        delay = self._interval if result.status == "ok" else self._retry_delay(
            state.failure_count + 1
        )
        state.apply_result(result, self._now(), delay)
        self._busy.discard(host)
        if host in self._refresh_pending:
            self._refresh_pending.discard(host)
            self._next_due[host] = 0.0
        else:
            self._next_due[host] = observed_monotonic + delay

    def _complete_future(self, host: str, future: Future) -> None:
        try:
            result = future.result()
        except Exception as exc:
            result = HostInspectionResult(host, "error", [], type(exc).__name__)
        with self._condition:
            self._apply_result(host, result, self._monotonic())
            self._condition.notify_all()

    def _submit_due(self, now_value: float) -> None:
        for host in self._due_hosts(now_value):
            self._busy.add(host)
            self._states[host].status = "scanning"
            future = self._executor.submit(self._collector, host, self._timeout)
            future.add_done_callback(
                lambda completed, alias=host: self._complete_future(alias, completed)
            )

    def _run(self) -> None:
        while True:
            with self._condition:
                if self._stop_requested:
                    return
                now_value = self._monotonic()
                if not self._is_active(now_value):
                    self._condition.wait()
                    continue
                self._submit_due(now_value)
                future_due = [
                    due for host, due in self._next_due.items()
                    if host not in self._busy
                ]
                timeout = None if not future_due else max(0.05, min(future_due) - now_value)
                self._condition.wait(timeout=timeout)
```

Use a `threading.Condition`, `ThreadPoolExecutor(max_workers=min(workers, len(hosts)))`, and a busy-host set. Background and deterministic test paths must share due-host and result-application logic.

- [ ] **Step 4: Implement inactivity and shutdown**

The scheduler waits on the condition without busy polling. While inactive it submits no work. `stop()` sets the stop flag, notifies, joins the scheduler thread, and calls `executor.shutdown(wait=True, cancel_futures=True)` when supported.

- [ ] **Step 5: Run focused and full tests**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_coordinator -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Expected: all tests pass and tests leave no live coordinator threads.

- [ ] **Step 6: Commit**

```bash
git add src/ssh_gpu_checker/coordinator.py tests/test_coordinator.py
git commit -m "Add lightweight per-host scan coordinator"
```

## Task 5: Local-Only FastAPI Application

**Files:**

- Create: `src/ssh_gpu_checker/web.py`
- Create: `tests/test_web.py`

- [ ] **Step 1: Write failing route and security tests**

Create `tests/test_web.py`:

```python
import unittest
from fastapi.testclient import TestClient
from ssh_gpu_checker.web import create_app

class FakeCoordinator:
    def __init__(self) -> None:
        self.touched = 0
        self.refreshed = 0
    def start(self) -> None: pass
    def stop(self) -> None: pass
    def touch_client(self) -> None: self.touched += 1
    def request_refresh(self) -> None: self.refreshed += 1
    def snapshot(self):
        return {"schema_version": 1, "hosts": [], "summary": {}}

class WebTests(unittest.TestCase):
    def setUp(self) -> None:
        self.coordinator = FakeCoordinator()
        self.client = TestClient(create_app(self.coordinator))

    def test_snapshot_touches_client_and_returns_cache(self) -> None:
        response = self.client.get("/api/v1/snapshot")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["schema_version"], 1)
        self.assertEqual(self.coordinator.touched, 1)

    def test_refresh_requires_json_and_returns_202(self) -> None:
        self.assertEqual(self.client.post("/api/v1/refresh").status_code, 415)
        good = self.client.post("/api/v1/refresh", json={})
        self.assertEqual(good.status_code, 202)
        self.assertEqual(self.coordinator.refreshed, 1)

    def test_rejects_untrusted_host_header(self) -> None:
        response = self.client.get("/healthz", headers={"host": "evil.example"})
        self.assertEqual(response.status_code, 400)
```

- [ ] **Step 2: Run and verify failure**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_web -v
```

Expected: import failure for `ssh_gpu_checker.web`.

- [ ] **Step 3: Implement the application factory**

`create_app(coordinator)` must:

- use FastAPI lifespan to call `start()` and `stop()`
- add `TrustedHostMiddleware` for `127.0.0.1`, `localhost`, and `testserver`
- serve packaged `index.html` at `/` and assets at `/static`
- touch client activity only for `GET /api/v1/snapshot`
- require `application/json` for `POST /api/v1/refresh`, return HTTP 202, and never wait for SSH
- return `{"status": "ok"}` from `/healthz` without waking scans
- omit CORS middleware

Mount the package static directory with `check_dir=False` so the API tests in this
task can construct the application before Task 6 creates the assets. A request for
a missing asset still returns 404.

- [ ] **Step 4: Run focused and full tests**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_web -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ssh_gpu_checker/web.py tests/test_web.py
git commit -m "Add local-only dashboard API"
```

## Task 6: Host-Strip Dashboard Frontend

**Files:**

- Create: `src/ssh_gpu_checker/static/index.html`
- Create: `src/ssh_gpu_checker/static/dashboard.css`
- Create: `src/ssh_gpu_checker/static/dashboard.js`
- Modify: `tests/test_web.py`

- [ ] **Step 1: Add failing static asset tests**

Add to `tests/test_web.py`:

```python
def test_dashboard_and_assets_are_packaged(self) -> None:
    page = self.client.get("/")
    self.assertEqual(page.status_code, 200)
    self.assertIn("SSH GPU Dashboard", page.text)
    self.assertIn('/static/dashboard.js', page.text)
    script = self.client.get("/static/dashboard.js")
    self.assertEqual(script.status_code, 200)
    self.assertIn("textContent", script.text)
    self.assertNotIn("innerHTML", script.text)
```

- [ ] **Step 2: Run and verify failure**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_web.WebTests.test_dashboard_and_assets_are_packaged -v
```

Expected: missing-file or 404 failure.

- [ ] **Step 3: Implement document and safe renderer**

`index.html` contains a semantic header, four summary cards, status region, host-list container, and Refresh button.

`dashboard.js` uses only DOM creation and `.textContent` for remote values. Define
`gpuState` to classify free/busy/constrained/unknown, `renderSummary` for online,
GPU, idle, and stale totals, `renderGpu` for compact GPU tiles, `renderHost` for a
stable host strip plus failure row, `loadSnapshot` for a cached GET every two
seconds, and `requestRefresh` for the asynchronous JSON POST and button state.

On network error, update the status region but preserve the most recent host DOM. Never use `innerHTML` for rendering.

- [ ] **Step 4: Implement responsive CSS**

Use `repeat(auto-fit, minmax(150px, 1fr))` GPU grids, visible focus states, text alongside every status color, `prefers-reduced-motion`, and one mobile breakpoint. Do not add external fonts, images, charts, or animation libraries.

- [ ] **Step 5: Run focused and full tests**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_web -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/ssh_gpu_checker/static tests/test_web.py
git commit -m "Build lightweight host-strip dashboard"
```

## Task 7: Dashboard CLI and Documentation

**Files:**

- Create: `src/ssh_gpu_checker/dashboard_cli.py`
- Create: `bin/ssh-gpu-dashboard`
- Modify: `tests/test_dashboard_cli.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing CLI tests**

Extend `tests/test_dashboard_cli.py`:

```python
from ssh_gpu_checker.dashboard_cli import build_parser, validate_loopback_host

class DashboardCliTests(unittest.TestCase):
    def test_requires_match_pattern(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args([])

    def test_rejects_non_loopback_bind(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            validate_loopback_host("0.0.0.0")

    def test_accepts_localhost_and_ipv4_loopback(self) -> None:
        self.assertEqual(validate_loopback_host("localhost"), "localhost")
        self.assertEqual(validate_loopback_host("127.0.0.1"), "127.0.0.1")
```

- [ ] **Step 2: Run and verify failure**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_dashboard_cli -v
```

Expected: import failure for `dashboard_cli`.

- [ ] **Step 3: Implement argument parsing and startup**

`dashboard_cli.py` defines:

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the SSH GPU dashboard")
    parser.add_argument("--config-path")
    parser.add_argument("--match", action="append", required=True)
    parser.add_argument("--interval", type=float, default=8.0)
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8848)
    return parser

def validate_loopback_host(value: str) -> str:
    if value == "localhost":
        return value
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("dashboard host must be a loopback address") from exc
    if not address.is_loopback:
        raise ValueError("dashboard host must be loopback-only")
    return value

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.interval < 5:
        parser.error("--interval must be at least 5 seconds")
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    try:
        host = validate_loopback_host(args.host)
    except ValueError as exc:
        parser.error(str(exc))
    config_path = (
        Path(args.config_path).expanduser()
        if args.config_path else resolve_default_config_path()
    )
    selected = filter_hosts_by_globs(load_hosts(config_path, None), args.match)
    if not selected:
        parser.error("host allowlist matched no SSH aliases")
    coordinator = ScanCoordinator(
        selected, inspect_host, interval_seconds=args.interval,
        timeout_seconds=args.timeout, workers=args.workers,
    )
    app = create_app(coordinator)
    print(f"SSH GPU Dashboard: http://{host}:{args.port}", flush=True)
    uvicorn.run(app, host=host, port=args.port, log_level="warning")
    return 0
```

Arguments are `--config-path`, repeatable required `--match`, `--interval` default 8, `--timeout` default 8, `--workers` default 8, `--host` default `127.0.0.1`, and `--port` default 8848. Reject intervals below 5, workers below 1, empty host selections, and non-loopback bind values. Start Uvicorn with warning logging and print the exact URL before serving.

Create `bin/ssh-gpu-dashboard` using the existing repository-root/PYTHONPATH wrapper pattern.

- [ ] **Step 4: Update README**

Document:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
bin/ssh-gpu-dashboard --match 'THUSZ*'
```

Explain loopback-only access, healthy 8-second scans, 15/30/60 retry backoff, 30-second inactivity pause, system OpenSSH behavior, lack of history, and the unchanged CLI recommendation command.

- [ ] **Step 5: Run CLI and full tests**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_dashboard_cli -v
.venv/bin/ssh-gpu-dashboard --help
bin/ssh-gpu-dashboard --help
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Expected: both help commands exit 0 and all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/ssh_gpu_checker/dashboard_cli.py bin/ssh-gpu-dashboard \
  tests/test_dashboard_cli.py README.md
git commit -m "Add one-command dashboard launcher"
```

## Task 8: Live Smoke Test and Final Verification

**Files:**

- Modify only when verification proves a concrete defect.

- [ ] **Step 1: Run static verification**

```bash
git diff --check
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
uv pip check --python .venv/bin/python
```

Expected: zero whitespace errors, zero test failures, and compatible dependencies.

- [ ] **Step 2: Start the real loopback dashboard**

```bash
bin/ssh-gpu-dashboard --match 'THUSZ*' --port 8848
```

Expected: prints `http://127.0.0.1:8848` and listens only on loopback.

- [ ] **Step 3: Verify API and listener**

```bash
curl -fsS http://127.0.0.1:8848/healthz
curl -fsS http://127.0.0.1:8848/api/v1/snapshot
lsof -nP -iTCP:8848 -sTCP:LISTEN
```

Expected: health is `ok`, snapshot schema version is 1, and listener is `127.0.0.1:8848`, never `*:8848`.

- [ ] **Step 4: Browser smoke test**

Open `http://127.0.0.1:8848` and verify summary cards, independent host population, stable host order, GPU metrics, process users, compact failure rows, manual refresh, and an empty browser console.

- [ ] **Step 5: Verify inactivity pause**

Close the dashboard tab, wait at least 35 seconds, and inspect coordinator diagnostics or SSH process activity.

Expected: no new SSH subprocess begins after the inactivity threshold.

- [ ] **Step 6: Review the complete change set**

```bash
git status --short
git log --oneline --decorate -10
BASE=$(git merge-base main HEAD)
git diff "$BASE" HEAD --stat
git diff "$BASE" HEAD --check
```

Expected: only dashboard-related files and the approved plan are present, and the worktree is clean.

- [ ] **Step 7: Commit only proven verification adjustments**

If verification changed README wording:

```bash
git add README.md
git commit -m "Clarify dashboard verification notes"
```

Otherwise do not create an empty commit.
