from typing import List

from ssh_gpu_checker.models import HostInspectionResult


def render_report(results: List[HostInspectionResult]) -> str:
    sorted_results = sorted(
        results,
        key=lambda item: (item.status != "ok", -item.best_free_memory_mb, item.host),
    )
    lines = ["Host Summary"]
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
                f"  GPU {gpu.gpu_index} | {gpu.name} | free {gpu.free_memory_mb} MiB / {gpu.total_memory_mb} MiB | util {gpu.utilization_gpu_percent}%"
            )
    return "\n".join(lines)
