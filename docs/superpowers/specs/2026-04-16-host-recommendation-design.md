---
title: Host Recommendation Design
date: 2026-04-16
status: draft
---

# Host Recommendation Design

## Goal

Upgrade `ssh-gpu-checker` so it can recommend the best host for a new GPU workload instead of only dumping raw per-host GPU metrics.

The repository should keep the scoring and recommendation rules in code, while the Codex skill should guide the model to use the tool consistently and summarize why a host is recommended.

## Context

- The current CLI already discovers hosts from `~/.ssh/config` or `~/.ssh/configs`.
- The current CLI already gathers GPU memory and utilization data for each host.
- The current CLI output is useful for inspection, but it still requires the user to manually decide which host is best.
- The user wants a stronger skill inspired by `ssh-dashboard`, but the main need is host recommendation rather than a full interactive terminal UI.

## Recommendation Strategy

The tool should recommend hosts, not individual GPUs, but each host recommendation should be justified by the best GPU on that host.

Each GPU will receive a score based on:

- free memory in MB
- free memory ratio
- inverse utilization

Each host will receive:

- a `best_gpu_score`
- a `best_gpu_free_memory_mb`
- a `best_gpu_utilization_percent`
- a short human-readable recommendation reason

The host recommendation list will sort by the best GPU score descending. This keeps the output host-focused while still reflecting the most attractive GPU on each machine.

## Default Ranking Model

The default model should prefer hosts that have:

- high absolute free memory
- low GPU utilization
- high free-memory ratio when two cards have similar free memory

The exact formula should remain simple and inspectable. The first version should normalize values inside the current result set rather than depending on hard-coded device assumptions.

## CLI Enhancements

The CLI should add recommendation-oriented options:

- `--recommend-hosts`: explicitly enable host recommendation mode
- `--top N`: limit the number of recommendations shown
- `--min-free-mb N`: exclude hosts whose best GPU has less than this free memory
- `--max-util N`: exclude hosts whose best GPU utilization is above this threshold
- `--sort score|free|util`: choose recommendation ordering

The default text output should begin with a `Recommended Hosts` section before the detailed host listing.

JSON output should include both:

- the raw host inspection results
- the computed recommendation list

## Borrowed Ideas From ssh-dashboard

The design should intentionally borrow these ideas from `ssh-dashboard`:

- scan many SSH hosts in one pass
- keep failures isolated so one broken host does not abort the whole run
- present a decision-oriented summary at the top
- make multi-host comparison easy

The design should not attempt to copy the full Bubble Tea dashboard interaction model in this version.

## Skill Upgrade

The skill should become more than a command reminder. It should:

- trigger for requests about finding the best host for a job
- prefer recommendation mode over raw metric dumps
- mention filtering patterns such as `--match THUSZ`
- encourage JSON output only when the result will be consumed programmatically
- summarize the top host with its reason, then mention notable fallbacks or failures

## Testing

Automated tests should cover:

- per-GPU score computation
- host recommendation ordering
- threshold-based filtering
- text rendering of recommendation summaries
- JSON output shape including recommendations

Manual smoke tests should cover:

- filtering a real host group such as `THUSZ`
- confirming the top recommendation is accompanied by a clear reason

## Non-Goals

- interactive TUI host picker
- persistent SSH sessions
- direct shell handoff into the recommended host
- automatic job scheduling or locking
