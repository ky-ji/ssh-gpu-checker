import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import List

from ssh_gpu_checker.models import GpuInfo, HostInspectionResult

GPU_QUERY = (
    "nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu "
    "--format=csv,noheader,nounits"
)


def parse_nvidia_smi_csv(output: str) -> List[GpuInfo]:
    gpus: List[GpuInfo] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        index, name, total, used, utilization = [part.strip() for part in raw_line.split(',', 4)]
        total_mb = int(total)
        used_mb = int(used)
        utilization_percent = None if utilization in {'[N/A]', 'N/A'} else int(utilization)
        gpus.append(
            GpuInfo(
                gpu_index=index,
                name=name,
                total_memory_mb=total_mb,
                used_memory_mb=used_mb,
                free_memory_mb=total_mb - used_mb,
                utilization_gpu_percent=utilization_percent,
            )
        )
    return gpus


def classify_ssh_failure(returncode: int, stderr: str) -> str:
    message = stderr.lower()
    if 'command not found' in message and 'nvidia-smi' in message:
        return 'no_nvidia_smi'
    if 'permission denied' in message:
        return 'auth_failed'
    if (
        'timed out' in message
        or 'could not resolve hostname' in message
        or 'connection refused' in message
        or 'no route to host' in message
        or 'operation timed out' in message
    ):
        return 'unreachable'
    if returncode == 255:
        return 'unreachable'
    return 'error'


def build_ssh_command(host: str, timeout: int) -> List[str]:
    return [
        'ssh',
        '-o',
        'BatchMode=yes',
        '-o',
        f'ConnectTimeout={timeout}',
        host,
        GPU_QUERY,
    ]


def inspect_host(host: str, timeout: int) -> HostInspectionResult:
    command = build_ssh_command(host, timeout)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout + 2,
        )
    except subprocess.TimeoutExpired as exc:
        return HostInspectionResult(host=host, status='unreachable', message=str(exc))

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode == 0:
        gpus = parse_nvidia_smi_csv(stdout)
        if not gpus:
            return HostInspectionResult(host=host, status='no_gpu_data', message='No GPU rows returned')
        return HostInspectionResult(host=host, status='ok', gpus=gpus, message='')

    status = classify_ssh_failure(completed.returncode, stderr)
    return HostInspectionResult(host=host, status=status, message=stderr or 'SSH command failed')


def inspect_many_hosts(hosts: List[str], timeout: int, workers: int) -> List[HostInspectionResult]:
    if not hosts:
        return []
    max_workers = max(1, min(workers, len(hosts)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(lambda host: inspect_host(host, timeout), hosts))
