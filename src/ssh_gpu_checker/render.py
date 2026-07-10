from typing import List, Optional

from ssh_gpu_checker.models import HostInspectionResult
from ssh_gpu_checker.recommend import HostRecommendation


def _format_utilization(utilization: object) -> str:
    if utilization is None:
        return "N/A"
    return f"{utilization}%"


def render_report(
    results: List[HostInspectionResult],
    recommendations: Optional[List[HostRecommendation]] = None,
) -> str:
    sorted_results = sorted(
        results,
        key=lambda item: (item.status != "ok", -item.best_free_memory_mb, item.host),
    )
    lines = []
    if recommendations is not None:
        lines.append("Recommended Hosts")
        if recommendations:
            for index, recommendation in enumerate(recommendations, start=1):
                lines.append(
                    f"{index}. {recommendation.host}  score={recommendation.score:.2f}"
                )
                lines.append(f"   reason: {recommendation.reason}")
        else:
            lines.append("No hosts matched the recommendation filters.")
        lines.append("")
    lines.append("Host Summary")
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
                f"  GPU {gpu.gpu_index} | {gpu.name} | free {gpu.free_memory_mb} MiB / {gpu.total_memory_mb} MiB | util {_format_utilization(gpu.utilization_gpu_percent)}"
            )
    return "\n".join(lines)
