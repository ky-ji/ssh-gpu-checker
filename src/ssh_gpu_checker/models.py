from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class GpuInfo:
    gpu_index: str
    name: str
    total_memory_mb: int
    used_memory_mb: int
    free_memory_mb: int
    utilization_gpu_percent: Optional[int]


@dataclass(frozen=True)
class HostInspectionResult:
    host: str
    status: str
    gpus: List[GpuInfo] = field(default_factory=list)
    message: str = ""

    @property
    def best_free_memory_mb(self) -> int:
        if not self.gpus:
            return -1
        return max(gpu.free_memory_mb for gpu in self.gpus)
