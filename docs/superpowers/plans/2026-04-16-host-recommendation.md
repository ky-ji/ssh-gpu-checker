# Host Recommendation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add host recommendation scoring, filtering, and richer skill guidance so `ssh-gpu-checker` can recommend the best machine for a new GPU workload.

**Architecture:** Keep host inspection as-is, add a small recommendation layer that derives GPU and host scores from inspection results, then teach the CLI and renderer to expose that recommendation data. Upgrade the skill so it drives the new recommendation-first workflow instead of acting as a thin command reminder.

**Tech Stack:** Python 3 standard library, `unittest`, Markdown skill docs

---

### Task 1: Write recommendation tests first

**Files:**
- Modify: `tests/test_renderer.py`
- Modify: `tests/test_cli.py`
- Create: `tests/test_recommend.py`

- [ ] Add tests for GPU score, host ordering, and threshold filtering.
- [ ] Add CLI tests for recommendation-first text output.
- [ ] Add CLI tests for JSON payload including recommendations.
- [ ] Run the targeted tests and confirm they fail for missing recommendation functionality.

### Task 2: Implement recommendation model

**Files:**
- Create: `src/ssh_gpu_checker/recommend.py`
- Modify: `src/ssh_gpu_checker/models.py`

- [ ] Add recommendation dataclasses for host-level recommendation output.
- [ ] Implement GPU scoring and host recommendation generation.
- [ ] Support filters for minimum free memory, maximum utilization, and top-N trimming.
- [ ] Re-run recommendation tests and make them pass.

### Task 3: Integrate recommendations into renderer and CLI

**Files:**
- Modify: `src/ssh_gpu_checker/render.py`
- Modify: `src/ssh_gpu_checker/cli.py`

- [ ] Add recommendation summary rendering before the detailed host section.
- [ ] Add CLI arguments for recommendation mode and sorting/filtering.
- [ ] Include recommendations in JSON output.
- [ ] Re-run the full test suite and make it pass.

### Task 4: Upgrade the skill and README

**Files:**
- Modify: `skills/check-ssh-gpu/SKILL.md`
- Modify: `README.md`

- [ ] Rewrite the skill so it recommends command patterns for “find best host” workflows.
- [ ] Update README examples to show recommendation mode and top-N filtering.
- [ ] Install the updated skill locally.

### Task 5: Verify against real hosts

**Files:**
- Modify: `README.md` if smoke testing reveals unclear behavior

- [ ] Run `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
- [ ] Run a real smoke test such as `bash ./bin/check-ssh-gpu --match THUSZ --top 3`.
- [ ] If available, run a one-host JSON smoke test and confirm recommendation payload shape.
- [ ] Commit the completed implementation.
