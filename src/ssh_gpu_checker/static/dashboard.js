(() => {
  "use strict";

  const POLL_INTERVAL_MS = 2000;
  const elements = {
    connection: document.getElementById("connection-status"),
    freshness: document.getElementById("freshness"),
    refresh: document.getElementById("refresh-button"),
    hostList: document.getElementById("host-list"),
    hostsOnline: document.getElementById("hosts-online"),
    hostsTotal: document.getElementById("hosts-total"),
    gpusTotal: document.getElementById("gpus-total"),
    gpusIdle: document.getElementById("gpus-idle"),
    hostsStale: document.getElementById("hosts-stale"),
  };

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) {
      element.className = className;
    }
    if (text !== undefined) {
      element.textContent = text;
    }
    return element;
  }

  function numberOrDash(value) {
    return Number.isFinite(value) ? String(value) : "—";
  }

  function memoryLabel(value) {
    if (!Number.isFinite(value)) {
      return "—";
    }
    if (value >= 1024) {
      return `${(value / 1024).toFixed(1)} GiB`;
    }
    return `${value} MiB`;
  }

  function shortTime(value) {
    if (!value) {
      return "not yet scanned";
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return "time unavailable";
    }
    return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function gpuState(gpu) {
    const utilization = gpu.utilization_gpu_percent;
    const total = gpu.total_memory_mb;
    const used = gpu.used_memory_mb;
    if (!Number.isFinite(utilization) || !Number.isFinite(total) || total <= 0 || !Number.isFinite(used)) {
      return "unknown";
    }
    const memoryRatio = used / total;
    if (utilization < 10 && memoryRatio < 0.1) {
      return "free";
    }
    if (memoryRatio >= 0.9) {
      return "constrained";
    }
    return "busy";
  }

  function stateLabel(state) {
    return {
      free: "Idle",
      busy: "Busy",
      constrained: "Memory full",
      unknown: "Unknown",
    }[state] || "Unknown";
  }

  function hostStatusLabel(status) {
    return {
      pending: "Pending",
      scanning: "Scanning",
      ok: "Online",
      unreachable: "Unreachable",
      auth_failed: "Auth failed",
      no_nvidia_smi: "No nvidia-smi",
      no_gpu_data: "No GPU data",
      parse_error: "Parse error",
      error: "Error",
    }[status] || "Unknown";
  }

  function metric(label, value) {
    const wrapper = node("div", "metric");
    wrapper.append(node("span", "metric-label", label));
    wrapper.append(node("strong", "metric-value", value));
    return wrapper;
  }

  function renderSummary(summary) {
    elements.hostsOnline.textContent = numberOrDash(summary.hosts_online);
    elements.hostsTotal.textContent = `of ${numberOrDash(summary.hosts_total)} configured`;
    elements.gpusTotal.textContent = numberOrDash(summary.gpus_total);
    elements.gpusIdle.textContent = numberOrDash(summary.gpus_idle);
    elements.hostsStale.textContent = numberOrDash(summary.hosts_stale);
  }

  function renderGpu(gpu) {
    const state = gpuState(gpu);
    const card = node("article", `gpu-card gpu-${state}`);
    const header = node("div", "gpu-header");
    header.append(node("span", "gpu-index", `GPU ${gpu.index ?? "?"}`));
    header.append(node("span", `gpu-state ${state}`, stateLabel(state)));
    card.append(header);
    card.append(node("p", "gpu-name", gpu.name || "Unknown NVIDIA GPU"));

    const metrics = node("div", "metric-grid");
    const utilization = Number.isFinite(gpu.utilization_gpu_percent)
      ? `${gpu.utilization_gpu_percent}%`
      : "N/A";
    const temperature = Number.isFinite(gpu.temperature_celsius)
      ? `${gpu.temperature_celsius}°C`
      : "N/A";
    metrics.append(metric("Util", utilization));
    metrics.append(metric("Free", memoryLabel(gpu.free_memory_mb)));
    metrics.append(metric("Total", memoryLabel(gpu.total_memory_mb)));
    metrics.append(metric("Temp", temperature));
    card.append(metrics);

    const progress = node("progress", "memory-progress");
    progress.max = Number.isFinite(gpu.total_memory_mb) && gpu.total_memory_mb > 0
      ? gpu.total_memory_mb
      : 1;
    progress.value = Number.isFinite(gpu.used_memory_mb) ? Math.max(0, gpu.used_memory_mb) : 0;
    progress.setAttribute(
      "aria-label",
      `${memoryLabel(gpu.used_memory_mb)} of ${memoryLabel(gpu.total_memory_mb)} GPU memory used`,
    );
    card.append(progress);

    const processes = Array.isArray(gpu.processes) ? gpu.processes : [];
    if (processes.length) {
      const processSection = node("div", "processes");
      processSection.append(node("p", "process-heading", `${processes.length} compute process${processes.length === 1 ? "" : "es"}`));
      const list = node("ul", "process-list");
      processes.forEach((process) => {
        const username = process.username || "unknown";
        const pid = Number.isFinite(process.pid) ? process.pid : "?";
        list.append(node("li", "", `${username} · PID ${pid} · ${memoryLabel(process.used_memory_mb)}`));
      });
      processSection.append(list);
      card.append(processSection);
    }
    return card;
  }

  function renderHost(host) {
    const status = host.status || "error";
    const strip = node("article", `host-strip status-${status}`);
    const header = node("div", "host-header");
    const title = node("div", "host-title");
    title.append(node("h3", "", host.alias || "Unnamed host"));
    title.append(node("span", `status-badge ${status}`, hostStatusLabel(status)));
    header.append(title);

    const meta = node("div", "host-meta");
    if (host.stale) {
      meta.append(node("span", "stale-badge", "Stale data"));
    }
    let timing = status === "ok"
      ? `Updated ${shortTime(host.last_success_at)}`
      : `Last success ${shortTime(host.last_success_at)}`;
    const isFailure = !["ok", "pending", "scanning"].includes(status);
    if (isFailure && Number.isFinite(host.next_retry_seconds) && host.next_retry_seconds > 0) {
      timing += ` · Retry in ${host.next_retry_seconds}s`;
    }
    meta.append(node("span", "host-timing", timing));
    header.append(meta);
    strip.append(header);

    const gpus = Array.isArray(host.gpus) ? host.gpus : [];
    if (gpus.length) {
      const grid = node("div", "gpu-grid");
      gpus.forEach((gpu) => grid.append(renderGpu(gpu)));
      strip.append(grid);
    } else {
      const fallback = host.message || (status === "scanning" ? "Scanning host…" : "Waiting for GPU data");
      const messageClass = status === "pending" || status === "scanning"
        ? "host-message neutral"
        : "host-message";
      strip.append(node("p", messageClass, fallback));
    }
    return strip;
  }

  function renderSnapshot(snapshot) {
    if (snapshot.schema_version !== 1) {
      throw new Error("Unsupported snapshot schema");
    }
    renderSummary(snapshot.summary || {});
    const hosts = Array.isArray(snapshot.hosts) ? snapshot.hosts : [];
    const fragment = document.createDocumentFragment();
    hosts.forEach((host) => fragment.append(renderHost(host)));
    if (!hosts.length) {
      fragment.append(node("div", "initial-state", "No hosts matched the configured allowlist"));
    }
    elements.hostList.replaceChildren(fragment);
    elements.connection.className = "connection-status is-live";
    elements.connection.textContent = snapshot.active ? "Live" : "Paused";
    elements.freshness.textContent = `Snapshot ${shortTime(snapshot.generated_at)}`;
  }

  async function fetchSnapshot() {
    const response = await fetch("/api/v1/snapshot", {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`Snapshot request failed (${response.status})`);
    }
    renderSnapshot(await response.json());
  }

  async function loadSnapshot() {
    try {
      await fetchSnapshot();
    } catch (error) {
      elements.connection.className = "connection-status is-error";
      elements.connection.textContent = "Connection lost";
      elements.freshness.textContent = error instanceof Error ? error.message : "Snapshot unavailable";
    } finally {
      window.setTimeout(loadSnapshot, POLL_INTERVAL_MS);
    }
  }

  async function requestRefresh() {
    elements.refresh.disabled = true;
    elements.refresh.textContent = "Refreshing…";
    try {
      const response = await fetch("/api/v1/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        throw new Error(`Refresh request failed (${response.status})`);
      }
      elements.connection.className = "connection-status is-live";
      elements.connection.textContent = "Refresh queued";
      await fetchSnapshot();
    } catch (error) {
      elements.connection.className = "connection-status is-error";
      elements.connection.textContent = "Refresh failed";
      elements.freshness.textContent = error instanceof Error ? error.message : "Refresh unavailable";
    } finally {
      elements.refresh.disabled = false;
      elements.refresh.textContent = "Refresh now";
    }
  }

  elements.refresh.addEventListener("click", requestRefresh);
  loadSnapshot();
})();
