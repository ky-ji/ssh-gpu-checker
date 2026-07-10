import csv
import subprocess
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from typing import Dict, List, Optional

from ssh_gpu_checker.models import GpuInfo, GpuProcessInfo, HostInspectionResult

GPU_QUERY = (
    "nvidia-smi --query-gpu=index,uuid,name,memory.total,memory.used,"
    "utilization.gpu,temperature.gpu "
    "--format=csv,noheader,nounits"
)
PROCESS_QUERY = (
    "nvidia-smi --query-compute-apps=gpu_uuid,pid,used_gpu_memory "
    "--format=csv,noheader,nounits 2>/dev/null | "
    "while IFS=, read -r uuid pid used; do "
    "pid=$(printf '%s' \"$pid\" | tr -d ' '); "
    "case \"$pid\" in ''|*[!0-9]*) continue ;; esac; "
    "user=$(ps -o user= -p \"$pid\" 2>/dev/null | "
    "awk '{$1=$1;print}'); "
    "printf '%s,%s,%s,%s\\n' \"$uuid\" \"$pid\" \"$used\" "
    "\"${user:-unknown}\"; done"
)
REMOTE_QUERY = (
    "printf '__GPU__\\n'; "
    + GPU_QUERY
    + " || exit $?; printf '__PROC__\\n'; "
    + PROCESS_QUERY
)


def _optional_int(value: str) -> Optional[int]:
    normalized = value.strip()
    if (
        normalized in {"", "N/A", "[N/A]"}
        or normalized.startswith("[") and normalized.endswith("]")
    ):
        return None
    return int(normalized)


def parse_nvidia_smi_csv(output: str) -> List[GpuInfo]:
    gpus: List[GpuInfo] = []
    for row in csv.reader(StringIO(output)):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != 5:
            raise ValueError(f"Malformed legacy GPU row: {row!r}")
        index, name, total, used, utilization = [cell.strip() for cell in row]
        total_mb = int(total)
        used_mb = int(used)
        gpus.append(
            GpuInfo(
                gpu_index=index,
                name=name,
                total_memory_mb=total_mb,
                used_memory_mb=used_mb,
                free_memory_mb=total_mb - used_mb,
                utilization_gpu_percent=_optional_int(utilization),
            )
        )
    return gpus


def parse_nvidia_smi_output(output: str) -> List[GpuInfo]:
    if "__GPU__" not in output or "__PROC__" not in output:
        return parse_nvidia_smi_csv(output)

    gpu_part, process_part = output.split("__PROC__", 1)
    gpu_part = gpu_part.split("__GPU__", 1)[1]
    processes_by_uuid: Dict[str, List[GpuProcessInfo]] = {}
    for row in csv.reader(StringIO(process_part)):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != 4:
            raise ValueError(f"Malformed process row: {row!r}")
        uuid, pid, used, username = [cell.strip() for cell in row]
        processes_by_uuid.setdefault(uuid, []).append(
            GpuProcessInfo(
                pid=int(pid),
                username=username or "unknown",
                used_memory_mb=_optional_int(used),
            )
        )

    gpus: List[GpuInfo] = []
    for row in csv.reader(StringIO(gpu_part)):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != 7:
            raise ValueError(f"Malformed GPU row: {row!r}")
        index, uuid, name, total, used, utilization, temperature = [
            cell.strip() for cell in row
        ]
        total_mb = int(total)
        used_mb = int(used)
        gpus.append(
            GpuInfo(
                gpu_index=index,
                name=name,
                total_memory_mb=total_mb,
                used_memory_mb=used_mb,
                free_memory_mb=total_mb - used_mb,
                utilization_gpu_percent=_optional_int(utilization),
                uuid=uuid,
                temperature_celsius=_optional_int(temperature),
                processes=processes_by_uuid.get(uuid, []),
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
        REMOTE_QUERY,
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
    except OSError as exc:
        return HostInspectionResult(host=host, status='error', message=str(exc))

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode == 0:
        try:
            gpus = parse_nvidia_smi_output(stdout)
        except (ValueError, csv.Error) as exc:
            return HostInspectionResult(
                host=host, status="parse_error", message=str(exc)
            )
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
