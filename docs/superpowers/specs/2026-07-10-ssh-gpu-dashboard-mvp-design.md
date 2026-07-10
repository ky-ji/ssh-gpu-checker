---
title: SSH GPU Dashboard MVP Design
date: 2026-07-10
status: approved
---

# SSH GPU Dashboard MVP Design

## Goal

Extend SSH GPU Checker with a lightweight local web dashboard that shows current NVIDIA GPU availability across explicit SSH aliases, with optional glob filtering.

The dashboard must remain agentless: remote servers only need SSH access and `nvidia-smi`. It must reuse the system OpenSSH client so the user's existing host-key checks, keys, ports, aliases, and jump-host behavior continue to work. The first version is a live status viewer, not a general observability platform.

## Confirmed Product Decisions

- Access is local and single-user. The service binds to `127.0.0.1` by default and has no account system.
- Host aliases come from the existing SSH config. By default all explicit aliases are shown; optional startup patterns such as `THUSZ*` restrict the set.
- Healthy hosts should update approximately every 5–10 seconds; the default interval is 8 seconds.
- Failed hosts use exponential retry delays of 15, 30, then 60 seconds.
- The web MVP shows cluster totals, host status, per-GPU utilization, memory, temperature, and process ownership.
- The web MVP does not surface host recommendations. The existing CLI recommendation workflow remains available and unchanged.
- The selected interface is a host-strip layout with compact GPU tiles.
- The system uses FastAPI and Uvicorn, with plain HTML, CSS, and JavaScript. It has no Node build, frontend framework, chart library, database, or remote agent.

## Product Principles

1. **Open and understand immediately.** The useful state should be visible without configuration forms or navigation.
2. **Do no work when nobody is looking.** Scanning pauses shortly after the last browser stops reading snapshots.
3. **Never let a failed host delay a healthy host.** Collection and retry state are independent per alias.
4. **Keep SSH behavior trustworthy.** Use the installed OpenSSH client rather than a partial SSH implementation.
5. **Keep the existing CLI stable.** Web support is additive and does not change current commands or JSON output.

## Alternatives Considered

### Standard-library HTTP server

This would preserve the project's current zero-dependency packaging, but it would require custom routing, application lifecycle, static-file handling, request validation, and test infrastructure. That conflicts with the goal of keeping the implementation simple and maintainable.

### Fork gnvitop

This would provide a finished-looking interface quickly, but it would inherit partial SSH config parsing, permissive host-key behavior, `[N/A]` parsing failures, unescaped HTML rendering, and missing automated tests. It also duplicates capabilities that SSH GPU Checker already handles more reliably.

### Recommended: thin FastAPI layer over the existing core

This preserves the working OpenSSH collector and recommendation CLI while adding only the scheduling, snapshot, API, and static dashboard layers needed for the MVP.

## Architecture

```text
Browser (plain HTML/CSS/JS)
        │  GET /api/v1/snapshot every 2s
        │  POST /api/v1/refresh on demand
        ▼
FastAPI on 127.0.0.1
        │
        ├── Snapshot Store ──► versioned JSON response
        │          ▲
        │          └── current host states and cluster summary
        │
        └── Scan Coordinator
                   │ bounded ThreadPoolExecutor
                   ▼
             system OpenSSH
                   │ fixed read-only command
                   ▼
          allowlisted GPU servers
```

The browser never starts SSH commands directly. HTTP requests read the latest in-memory snapshot. The coordinator alone decides when a host is due and guarantees at most one active collection per host.

## Component Boundaries

### Existing modules

- `config.py` continues to discover explicit aliases. It gains whitespace, inline-comment, and duplicate-alias handling. A dashboard-specific helper applies shell-style allowlist globs without changing the existing CLI's substring-based `--match` behavior. The module does not attempt to reimplement full OpenSSH option resolution.
- `inspect.py` continues to build and run OpenSSH commands. It gains robust CSV parsing, extended GPU fields, process ownership, complete exception isolation, and sanitized error details.
- `models.py` gains optional temperature, UUID, and process fields without changing the meaning of existing fields.
- `recommend.py`, `render.py`, and the existing CLI remain CLI-only. Their current behavior and JSON response stay compatible.

### New modules

- `snapshot.py` owns the versioned dashboard response model and cluster summary calculation.
- `coordinator.py` owns per-host scheduling, bounded concurrency, retries, last-known-good data, client activity, and shutdown.
- `web.py` creates the FastAPI application, connects application lifespan to the coordinator, and exposes the minimal routes.
- `static/index.html`, `static/dashboard.css`, and `static/dashboard.js` implement the dashboard without a build step.
- `bin/ssh-gpu-dashboard` provides the repository-local one-command entrypoint.

## Host Discovery and Allowlisting

The dashboard defaults to `~/.ssh/config`, with the existing `--config-path` override retained. It extracts only explicit `Host` aliases and ignores wildcard, negated, and catch-all entries.

The dashboard uses all discovered explicit aliases when `--match` is omitted. One or more shell-style `--match` globs can restrict the dashboard to selected aliases. This flag belongs to the new dashboard entrypoint; the existing CLI keeps its current substring matching semantics. For example:

```bash
bin/ssh-gpu-dashboard
bin/ssh-gpu-dashboard --match 'THUSZ*'
```

Matching is case-insensitive and multiple patterns can be supplied. The resolved alias list is stable and follows SSH config order. The dashboard fails fast if SSH discovery produces zero hosts or explicit patterns match zero hosts.

The web API cannot add hosts, choose a config path, change SSH usernames, or submit arbitrary remote commands. Once an alias is selected, OpenSSH resolves `HostName`, `User`, `Port`, `IdentityFile`, `ProxyJump`, `Include`, and other connection options when the collector invokes `ssh <alias>`.

The MVP does not recursively discover aliases that exist only inside OpenSSH `Include` files. In that configuration style, `--config-path` must point to the included file or directory so the aliases can be discovered; OpenSSH still applies the user's main configuration while connecting.

## Collection Protocol

Each collection uses a fixed command payload and an argv-based local subprocess call. No browser value is interpolated into the remote command.

GPU inventory and metrics use fields equivalent to:

```text
index, uuid, name, memory.total, memory.used,
utilization.gpu, temperature.gpu
```

Compute-process data uses GPU UUID, PID, and GPU memory usage. A fixed remote lookup maps numeric PIDs to usernames. The dashboard does not collect complete process command lines. If process ownership is not readable, the username is `unknown` rather than failing the GPU row.

Python's `csv` module parses output. Unsupported or unavailable numeric values, including `N/A` and `[N/A]`, become `null`. A malformed row produces a structured parse error for that row or host; it never raises through the batch coordinator.

## Scheduling and Lifecycle

- The coordinator uses one bounded thread pool. Its default worker count is `min(8, host_count)`.
- Opening the page causes its snapshot requests to mark the dashboard active and wake the coordinator.
- Healthy hosts are due every 8 seconds by default. The interval is configurable but cannot be set below 5 seconds.
- A failed host retries after 15 seconds, then 30 seconds, then at most 60 seconds. A successful collection resets the retry interval.
- Each host has a single-flight guard, so auto-refresh and manual refresh cannot overlap collections for the same alias.
- `POST /api/v1/refresh` marks hosts due immediately and returns without blocking for a full scan. Repeated requests coalesce.
- If no snapshot request arrives for 30 seconds, the coordinator stops scheduling new SSH work. It wakes on the next request.
- FastAPI shutdown stops scheduling, cancels future work where possible, and closes the executor cleanly.

The coordinator stores only current state in memory. Restarting the dashboard clears all snapshots and begins a new collection when a browser connects.

## Snapshot API

`GET /api/v1/snapshot` returns a stable, versioned shape:

```json
{
  "schema_version": 1,
  "generated_at": "2026-07-10T12:34:56Z",
  "active": true,
  "summary": {
    "hosts_total": 9,
    "hosts_online": 4,
    "gpus_total": 23,
    "gpus_idle": 15
  },
  "hosts": [
    {
      "alias": "THUSZgnode3",
      "status": "ok",
      "last_attempt_at": "2026-07-10T12:34:55Z",
      "last_success_at": "2026-07-10T12:34:55Z",
      "stale": false,
      "next_retry_seconds": 0,
      "gpus": [
        {
          "index": "0",
          "uuid": "GPU-…",
          "name": "NVIDIA GeForce RTX 4090",
          "total_memory_mb": 49140,
          "used_memory_mb": 33102,
          "free_memory_mb": 16038,
          "utilization_gpu_percent": 73,
          "temperature_celsius": 56,
          "processes": [
            {"pid": 12345, "username": "bkzhu", "used_memory_mb": 33101}
          ]
        }
      ]
    }
  ]
}
```

An idle GPU has known utilization below 10% and known memory usage below 10% of total. A GPU with unknown values is not counted as idle.

`POST /api/v1/refresh` returns HTTP 202 with `{"accepted": true}`. `GET /healthz` reports only process and coordinator health; it does not trigger SSH collection.

## Error and Stale-Data Semantics

Host states are `pending`, `scanning`, `ok`, `unreachable`, `auth_failed`, `no_nvidia_smi`, `no_gpu_data`, `parse_error`, or `error`.

If a host fails after a prior success, the last successful GPU rows remain visible with `stale: true`, the failure state, the last-success time, and the next retry delay. A host that has never succeeded shows no GPU rows.

One host exception is caught at the host boundary and cannot terminate the coordinator or another host's result. Raw SSH stderr is normalized, control characters are removed, and browser-visible messages are short fixed descriptions. Detailed diagnostics remain in local logs with bounded length.

## Web Interface

The selected layout is a host-strip dashboard:

- The header shows service activity, last snapshot time, and one manual Refresh button.
- The summary row shows online hosts, total GPUs, idle GPUs, and stale hosts.
- Each host occupies one compact strip with a stable alias, status, and data age.
- GPU tiles wrap within the host strip. Each tile shows index, utilization, free/total memory, temperature, and usernames.
- Color communicates free, busy, memory-full/hot, stale, and error states; text always accompanies color.
- Error-only hosts remain visible as a compact row with the next retry time.
- Host strips follow SSH config order so cards do not jump when status changes.
- The layout automatically wraps GPU tiles on narrow screens.
- There are no graphs, dashboard editors, recommendation cards, or navigation hierarchy in the MVP.

The browser polls the snapshot endpoint every 2 seconds. This polling reads memory only and does not change the SSH collection interval.

## Local Security Boundary

- The server defaults to `127.0.0.1`; binding to a non-loopback address is outside the MVP.
- Trusted-host validation accepts only `127.0.0.1` and `localhost` host headers.
- CORS is not enabled.
- The refresh endpoint requires same-origin JSON, preventing an ordinary cross-origin form from triggering scans.
- The service never accepts arbitrary aliases, commands, SSH options, or file paths over HTTP.
- SSH always uses batch mode, a bounded connection timeout, and normal host-key verification. The dashboard never supplies a disable-verification option.
- Frontend rendering uses DOM text APIs rather than inserting remote values through `innerHTML`.

## Packaging and Commands

FastAPI and Uvicorn are normal project dependencies so installation remains one step. No separate frontend install is required.

The repository-local workflow is:

```bash
bin/ssh-gpu-dashboard
```

The command prints the loopback URL and supports `--config-path`, optional repeatable `--match`, `--interval`, `--timeout`, `--workers`, `--host`, and `--port`. `--host` rejects non-loopback values in the MVP.

The existing `bin/check-ssh-gpu` command continues to work as before.

## Testing Strategy

Development follows test-driven development: add a failing test for each behavior, implement the smallest change, and rerun the focused and full suites.

Automated coverage includes:

- config parsing with tabs, comments, duplicates, wildcard entries, dashboard allowlist globs, and unchanged CLI substring matching
- quoted CSV fields, `N/A` values, malformed rows, temperature, UUID, and process ownership joins
- subprocess timeout, missing local `ssh`, authentication failures, and per-host exception isolation
- coordinator timing with a fake clock and fake collector
- healthy intervals, retry backoff, single-flight scans, request coalescing, client inactivity, and shutdown
- snapshot schema, idle-GPU calculation, stale-data behavior, and error sanitization
- API response contracts, host allowlisting, refresh acceptance, trusted hosts, and static asset serving
- browser smoke verification for the summary, host strips, GPU tiles, stale state, and manual refresh

The current 18 tests remain part of the full suite. Test-only HTTP client dependencies may be development dependencies and do not affect runtime deployment.

## Acceptance Criteria

- Omitting `--match` scans every explicit alias discovered in the selected SSH config.
- `--match 'THUSZ*'` scans only matching explicit aliases.
- The first successful host appears within 10 seconds of opening the page when at least one host is reachable.
- Healthy-host data refreshes every 5–10 seconds under normal network conditions.
- Unreachable and authentication-failed hosts never block healthy-host updates.
- Multiple refresh requests never create overlapping scans for a host.
- No new SSH subprocess is started after the dashboard has had no client for approximately 30 seconds.
- The default listener is reachable only through `127.0.0.1` or `localhost`.
- The page shows summary counts, per-host age/status, GPU utilization, memory, temperature, and process users.
- Existing CLI text and JSON behavior remains compatible and all prior tests pass.
- The dashboard starts with one command and requires no Node runtime, database, remote service, or remote installation.

## Non-Goals

- persistent history, charts, alerting, or notifications
- public, LAN, or multi-user access
- authentication, TLS termination, or role-based authorization
- editing SSH configuration in the browser
- arbitrary remote commands or job submission
- replacing the existing CLI recommendation workflow
- AMD, Intel, Apple, TPU, or other accelerator support
- Prometheus, Grafana, or exporter compatibility in the MVP
