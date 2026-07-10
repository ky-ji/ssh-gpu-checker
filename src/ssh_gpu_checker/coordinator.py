import copy
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Sequence, Set

from ssh_gpu_checker.models import HostInspectionResult
from ssh_gpu_checker.snapshot import HostState, serialize_snapshot


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
        unique_hosts = list(dict.fromkeys(hosts))
        if not unique_hosts:
            raise ValueError("coordinator requires at least one host")
        if workers < 1:
            raise ValueError("coordinator requires at least one worker")
        if interval_seconds <= 0 or inactive_after_seconds <= 0:
            raise ValueError("coordinator intervals must be positive")

        self._hosts = unique_hosts
        self._collector = collector
        self._interval = interval_seconds
        self._timeout = timeout_seconds
        self._inactive_after = inactive_after_seconds
        self._monotonic = monotonic
        self._now = now
        self._condition = threading.Condition()
        self._states = {host: HostState(host) for host in self._hosts}
        self._next_due = {host: 0.0 for host in self._hosts}
        self._busy: Set[str] = set()
        self._refresh_pending: Set[str] = set()
        self._last_client_seen: Optional[float] = None
        self._stop_requested = False
        self._executor = ThreadPoolExecutor(
            max_workers=min(workers, len(self._hosts)),
            thread_name_prefix="ssh-gpu",
        )
        self._thread: Optional[threading.Thread] = None
        self._executor_shutdown = False

    def start(self) -> None:
        with self._condition:
            if self._stop_requested:
                raise RuntimeError("stopped coordinator cannot be restarted")
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run,
                name="ssh-gpu-coordinator",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._condition:
            self._stop_requested = True
            self._condition.notify_all()
        if self._thread:
            self._thread.join(timeout=5)
        if not self._executor_shutdown:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor_shutdown = True

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

    def _is_active(self, now_value: float) -> bool:
        return (
            self._last_client_seen is not None
            and now_value - self._last_client_seen <= self._inactive_after
        )

    def _due_hosts(self, now_value: float) -> List[str]:
        return [
            host
            for host in self._hosts
            if host not in self._busy and self._next_due[host] <= now_value
        ]

    @staticmethod
    def _retry_delay(failure_number: int) -> int:
        return (15, 30, 60)[min(max(failure_number, 1) - 1, 2)]

    def _apply_result(
        self,
        host: str,
        result: HostInspectionResult,
        observed_monotonic: float,
    ) -> None:
        state = self._states[host]
        delay = (
            self._interval
            if result.status == "ok"
            else self._retry_delay(state.failure_count + 1)
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
            result = HostInspectionResult(
                host=host,
                status="error",
                message=type(exc).__name__,
            )
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

    def _next_wait(self, now_value: float) -> Optional[float]:
        deadlines = [
            due
            for host, due in self._next_due.items()
            if host not in self._busy
        ]
        if self._last_client_seen is not None:
            deadlines.append(self._last_client_seen + self._inactive_after)
        if not deadlines:
            return None
        return max(0.01, min(deadlines) - now_value)

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
                self._condition.wait(timeout=self._next_wait(now_value))
