from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from ssh_gpu_checker.models import GpuInfo, HostInspectionResult


PUBLIC_MESSAGES = {
    "unreachable": "Host unreachable",
    "auth_failed": "SSH authentication failed",
    "no_nvidia_smi": "nvidia-smi is unavailable",
    "no_gpu_data": "No GPU data returned",
    "parse_error": "GPU data could not be parsed",
    "error": "Unexpected collection error",
}


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


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

    def apply_result(
        self,
        result: HostInspectionResult,
        observed_at: datetime,
        next_delay_seconds: float,
    ) -> None:
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


def serialize_snapshot(
    states: Sequence[HostState], active: bool, generated_at: datetime
) -> Dict[str, object]:
    hosts = [
        {
            "alias": state.alias,
            "status": state.status,
            "message": PUBLIC_MESSAGES.get(state.status, ""),
            "last_attempt_at": _iso(state.last_attempt_at),
            "last_success_at": _iso(state.last_success_at),
            "stale": state.stale,
            "next_retry_seconds": state.next_retry_seconds,
            "gpus": [asdict(gpu) for gpu in state.gpus],
        }
        for state in states
    ]
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
