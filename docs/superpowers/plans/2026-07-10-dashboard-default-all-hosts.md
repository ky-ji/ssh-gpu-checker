# Dashboard Default-All Hosts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `--match` optional for the dashboard and show every discovered explicit SSH alias when it is omitted.

**Architecture:** Keep the strict glob helper unchanged and add a dashboard-level selection function that bypasses filtering only when no patterns were supplied. The dashboard CLI uses this function after SSH config discovery, while the existing one-shot CLI retains its substring semantics.

**Tech Stack:** Python 3.9+, `argparse`, standard-library `unittest`, Git/GitHub CLI.

---

### Task 1: Optional Dashboard Host Filtering

**Files:**

- Modify: `src/ssh_gpu_checker/dashboard_cli.py`
- Modify: `tests/test_dashboard_cli.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing parser test**

Replace `test_requires_match_pattern` in `tests/test_dashboard_cli.py` with:

```python
def test_match_pattern_is_optional(self) -> None:
    args = build_parser().parse_args([])
    self.assertIsNone(args.match)
```

- [ ] **Step 2: Run the parser test and verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_dashboard_cli.DashboardCliTests.test_match_pattern_is_optional -v
```

Expected: `SystemExit` because `--match` is still required.

- [ ] **Step 3: Make the parser option optional**

Change the argument in `build_parser()` to:

```python
parser.add_argument(
    "--match",
    action="append",
    help="optional SSH alias glob; repeat for more patterns",
)
```

- [ ] **Step 4: Run the parser test and verify it passes**

Run the command from Step 2. Expected: one passing test.

- [ ] **Step 5: Write the failing host-selection tests**

Import `select_dashboard_hosts` from `ssh_gpu_checker.dashboard_cli` and add:

```python
def test_uses_all_hosts_without_match_patterns(self) -> None:
    hosts = ["alpha", "THUSZgnode1", "beta"]
    self.assertEqual(select_dashboard_hosts(hosts, None), hosts)

def test_filters_hosts_when_match_patterns_are_present(self) -> None:
    hosts = ["alpha", "THUSZgnode1", "THUSZgnode2"]
    self.assertEqual(
        select_dashboard_hosts(hosts, ["THUSZ*2"]),
        ["THUSZgnode2"],
    )
```

- [ ] **Step 6: Run the selection tests and verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_dashboard_cli -v
```

Expected: import failure because `select_dashboard_hosts` does not exist.

- [ ] **Step 7: Implement dashboard host selection**

Add to `dashboard_cli.py`:

```python
def select_dashboard_hosts(
    hosts: Sequence[str], patterns: Optional[Sequence[str]]
) -> List[str]:
    if not patterns:
        return list(hosts)
    return filter_hosts_by_globs(hosts, patterns)
```

Import `List` and replace the current filter call in `main()` with:

```python
selected_hosts = select_dashboard_hosts(configured_hosts, args.match)
if not selected_hosts:
    parser.error("no SSH aliases were selected")
```

- [ ] **Step 8: Update user documentation**

Change the primary README command to `bin/ssh-gpu-dashboard`, explain that omission displays every explicit alias, keep the filtered examples, and describe `--match` as optional and repeatable.

- [ ] **Step 9: Run focused and full verification**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_dashboard_cli -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
bin/ssh-gpu-dashboard --help
git diff --check
```

Expected: every test passes, help exits zero, and no whitespace errors are reported.

- [ ] **Step 10: Commit the implementation**

```bash
git add src/ssh_gpu_checker/dashboard_cli.py tests/test_dashboard_cli.py README.md
git commit -m "Default dashboard to all SSH hosts"
```
