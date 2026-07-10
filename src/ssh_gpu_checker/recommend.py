from dataclasses import dataclass
from typing import List, Optional

from ssh_gpu_checker.models import GpuInfo, HostInspectionResult


@dataclass(frozen=True)
class HostRecommendation:
    host: str
    score: float
    best_gpu_index: str
    best_gpu_name: str
    best_gpu_free_memory_mb: int
    best_gpu_total_memory_mb: int
    best_gpu_utilization_percent: Optional[int]
    reason: str


def _utilization_for_scoring(gpu: GpuInfo) -> int:
    if gpu.utilization_gpu_percent is None:
        return 100
    return max(0, min(gpu.utilization_gpu_percent, 100))


def _format_utilization(utilization: Optional[int]) -> str:
    if utilization is None:
        return 'N/A'
    return f'{utilization}%'


def _gpu_score(gpu: GpuInfo, max_free_memory_mb: int) -> float:
    if max_free_memory_mb <= 0:
        free_memory_score = 0.0
    else:
        free_memory_score = gpu.free_memory_mb / float(max_free_memory_mb)
    free_ratio_score = 0.0
    if gpu.total_memory_mb > 0:
        free_ratio_score = gpu.free_memory_mb / float(gpu.total_memory_mb)
    utilization = _utilization_for_scoring(gpu)
    idle_score = (100.0 - utilization) / 100.0
    return 100.0 * ((0.6 * free_memory_score) + (0.2 * free_ratio_score) + (0.2 * idle_score))


def build_host_recommendations(
    results: List[HostInspectionResult],
    min_free_mb: int = 0,
    max_util: int = 100,
    top: Optional[int] = None,
    sort_by: str = 'score',
) -> List[HostRecommendation]:
    ok_results = [result for result in results if result.status == 'ok' and result.gpus]
    if not ok_results:
        return []

    max_free_memory_mb = max(gpu.free_memory_mb for result in ok_results for gpu in result.gpus)
    recommendations: List[HostRecommendation] = []

    for result in ok_results:
        best_gpu = max(result.gpus, key=lambda gpu: _gpu_score(gpu, max_free_memory_mb))
        if best_gpu.free_memory_mb < min_free_mb:
            continue
        if _utilization_for_scoring(best_gpu) > max_util:
            continue
        score = _gpu_score(best_gpu, max_free_memory_mb)
        recommendations.append(
            HostRecommendation(
                host=result.host,
                score=round(score, 2),
                best_gpu_index=best_gpu.gpu_index,
                best_gpu_name=best_gpu.name,
                best_gpu_free_memory_mb=best_gpu.free_memory_mb,
                best_gpu_total_memory_mb=best_gpu.total_memory_mb,
                best_gpu_utilization_percent=best_gpu.utilization_gpu_percent,
                reason=(
                    f'best GPU free {best_gpu.free_memory_mb} MiB, '
                    f'util {_format_utilization(best_gpu.utilization_gpu_percent)}'
                ),
            )
        )

    if sort_by == 'free':
        recommendations.sort(
            key=lambda item: (
                -item.best_gpu_free_memory_mb,
                100 if item.best_gpu_utilization_percent is None else item.best_gpu_utilization_percent,
                -item.score,
                item.host,
            )
        )
    elif sort_by == 'util':
        recommendations.sort(
            key=lambda item: (
                100 if item.best_gpu_utilization_percent is None else item.best_gpu_utilization_percent,
                -item.best_gpu_free_memory_mb,
                -item.score,
                item.host,
            )
        )
    else:
        recommendations.sort(
            key=lambda item: (
                -item.score,
                -item.best_gpu_free_memory_mb,
                100 if item.best_gpu_utilization_percent is None else item.best_gpu_utilization_percent,
                item.host,
            )
        )

    if top is not None and top >= 0:
        recommendations = recommendations[:top]
    return recommendations
