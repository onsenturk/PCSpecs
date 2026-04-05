/* ==========================================================================
   PCSpecs — WebSocket client & UI updater
   Uses .textContent exclusively (no .innerHTML) for XSS prevention.
   ========================================================================== */

(function () {
    "use strict";

    const RECONNECT_DELAY_MS = 2000;
    const GAUGE_CIRCUMFERENCE = 314; // 2 * PI * 50

    let ws = null;
    let reconnectTimer = null;

    // --- Helpers ---

    function formatBytes(bytes) {
        if (bytes === 0) return "0 B";
        const units = ["B", "KB", "MB", "GB", "TB"];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        const value = bytes / Math.pow(1024, i);
        return value.toFixed(i > 0 ? 1 : 0) + " " + units[i];
    }

    function formatRate(bytesPerSec) {
        return formatBytes(bytesPerSec) + "/s";
    }

    function formatFreq(mhz) {
        if (mhz >= 1000) return (mhz / 1000).toFixed(2) + " GHz";
        return mhz.toFixed(0) + " MHz";
    }

    function setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function setGauge(id, percent) {
        const el = document.getElementById(id);
        if (!el) return;
        const offset = GAUGE_CIRCUMFERENCE * (1 - Math.min(percent, 100) / 100);
        el.style.strokeDashoffset = offset;
    }

    // --- Fetch static specs once ---

    async function loadStaticSpecs() {
        try {
            const res = await fetch("/api/specs");
            const data = await res.json();
            renderStaticSpecs(data);
        } catch (err) {
            console.error("Failed to load specs:", err);
        }
    }

    function renderStaticSpecs(specs) {
        // CPU
        const cpu = specs.cpu || {};
        setText("cpu-brand", cpu.brand || "Unknown");
        setText("cpu-cores", (cpu.cores || "?") + " / " + (cpu.threads || "?"));
        setText("cpu-freq", cpu.frequency_mhz ? formatFreq(cpu.frequency_mhz) : "—");
        setText("cpu-arch", cpu.architecture || "—");

        // Build core bars
        const coreContainer = document.getElementById("cpu-core-bars");
        if (coreContainer && cpu.threads) {
            coreContainer.replaceChildren(); // clear safely
            for (let i = 0; i < cpu.threads; i++) {
                const bar = document.createElement("div");
                bar.className = "core-bar";

                const track = document.createElement("div");
                track.className = "core-bar-track";

                const fill = document.createElement("div");
                fill.className = "core-bar-fill";
                fill.id = "core-" + i;
                fill.style.height = "0%";

                const label = document.createElement("div");
                label.className = "core-bar-label";
                label.textContent = i;

                track.appendChild(fill);
                bar.appendChild(track);
                bar.appendChild(label);
                coreContainer.appendChild(bar);
            }
        }

        // GPU
        renderGpuStatic(specs.gpu || []);

        // Memory
        const mem = specs.memory || {};
        setText("mem-total", formatBytes(mem.total_bytes || 0));
        setText("mem-speed", mem.speed_mhz ? mem.speed_mhz + " MHz" : "—");

        // Memory slots
        const slotContainer = document.getElementById("mem-slots");
        if (slotContainer && mem.slots && mem.slots.length > 0) {
            slotContainer.replaceChildren();
            mem.slots.forEach(function (s) {
                const el = document.createElement("span");
                el.className = "mem-slot";
                el.textContent =
                    (s.slot || "DIMM") + ": " +
                    formatBytes(s.capacity_bytes || 0) +
                    (s.speed_mhz ? " @ " + s.speed_mhz + "MHz" : "");
                slotContainer.appendChild(el);
            });
        }

        // Storage
        renderStorage(specs.storage || []);

        // Motherboard + BIOS
        const mobo = specs.motherboard || {};
        const bios = specs.bios || {};
        setText("mobo-mfr", mobo.manufacturer || "—");
        setText("mobo-model", mobo.model || "—");
        setText("bios-version", bios.version || "—");
        setText("bios-date", bios.release_date || "—");

        // OS
        const os = specs.os || {};
        setText("os-name", os.name || "—");
        setText("os-version", os.version || "—");
        setText("os-arch", os.architecture || "—");

        // Network
        renderNetwork(specs.network || []);

        // Battery
        const bat = specs.battery || {};
        if (bat.has_battery) {
            document.getElementById("battery-card").style.display = "";
        }
    }

    function renderGpuStatic(gpus) {
        const body = document.getElementById("gpu-body");
        if (!body) return;
        body.replaceChildren();

        if (gpus.length === 0) {
            const p = document.createElement("p");
            p.className = "loading";
            p.textContent = "No GPU detected";
            body.appendChild(p);
            return;
        }

        gpus.forEach(function (gpu, idx) {
            const section = document.createElement("div");
            section.className = "gpu-section";

            // Name
            addSpecRow(section, "Model", gpu.name || "Unknown");
            addSpecRow(section, "VRAM", gpu.vram_total_mb ? formatBytes(gpu.vram_total_mb * 1024 * 1024) : "—");
            if (gpu.driver_version) addSpecRow(section, "Driver", gpu.driver_version);

            // Gauge for GPU load (if available)
            if (gpu.load_percent !== null && gpu.load_percent !== undefined) {
                const gaugeSection = document.createElement("div");
                gaugeSection.className = "gauge-section";

                const gaugeContainer = document.createElement("div");
                gaugeContainer.className = "gauge-container";

                const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                svg.setAttribute("class", "gauge");
                svg.setAttribute("viewBox", "0 0 120 120");

                const bgCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                bgCircle.setAttribute("cx", "60");
                bgCircle.setAttribute("cy", "60");
                bgCircle.setAttribute("r", "50");
                bgCircle.setAttribute("class", "gauge-bg");

                const fillCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                fillCircle.setAttribute("cx", "60");
                fillCircle.setAttribute("cy", "60");
                fillCircle.setAttribute("r", "50");
                fillCircle.setAttribute("class", "gauge-fill gauge-fill-purple");
                fillCircle.id = "gpu-gauge-" + idx;

                const valueText = document.createElementNS("http://www.w3.org/2000/svg", "text");
                valueText.setAttribute("x", "60");
                valueText.setAttribute("y", "55");
                valueText.setAttribute("class", "gauge-value");
                valueText.id = "gpu-usage-text-" + idx;
                valueText.textContent = "0%";

                const subText = document.createElementNS("http://www.w3.org/2000/svg", "text");
                subText.setAttribute("x", "60");
                subText.setAttribute("y", "72");
                subText.setAttribute("class", "gauge-sub");
                subText.textContent = "GPU";

                svg.append(bgCircle, fillCircle, valueText, subText);
                gaugeContainer.appendChild(svg);
                gaugeSection.appendChild(gaugeContainer);
                section.appendChild(gaugeSection);
            }

            // Temp
            if (gpu.temperature_c !== null && gpu.temperature_c !== undefined) {
                const tempRow = document.createElement("div");
                tempRow.className = "spec-row";
                const tempLabel = document.createElement("span");
                tempLabel.className = "label";
                tempLabel.textContent = "Temperature";
                const tempValue = document.createElement("span");
                tempValue.className = "value live";
                tempValue.id = "gpu-temp-" + idx;
                tempValue.textContent = gpu.temperature_c + "°C";
                tempRow.append(tempLabel, tempValue);
                section.appendChild(tempRow);
            }

            // VRAM usage bar
            if (gpu.vram_total_mb > 0) {
                const vramRow = document.createElement("div");
                vramRow.className = "spec-row";
                const vramLabel = document.createElement("span");
                vramLabel.className = "label";
                vramLabel.textContent = "VRAM Used";
                const vramValue = document.createElement("span");
                vramValue.className = "value live";
                vramValue.id = "gpu-vram-text-" + idx;
                vramValue.textContent = "—";
                vramRow.append(vramLabel, vramValue);
                section.appendChild(vramRow);

                const bar = document.createElement("div");
                bar.className = "progress-bar";
                const fill = document.createElement("div");
                fill.className = "progress-fill";
                fill.id = "gpu-vram-bar-" + idx;
                fill.style.width = "0%";
                bar.appendChild(fill);
                section.appendChild(bar);
            }

            body.appendChild(section);
        });
    }

    function renderStorage(drives) {
        const body = document.getElementById("storage-body");
        if (!body) return;
        body.replaceChildren();

        if (drives.length === 0) {
            const p = document.createElement("p");
            p.className = "loading";
            p.textContent = "No drives detected";
            body.appendChild(p);
            return;
        }

        drives.forEach(function (d) {
            const card = document.createElement("div");
            card.className = "sub-card";

            const title = document.createElement("div");
            title.className = "sub-card-title";
            title.textContent = d.mountpoint + " (" + (d.drive_type || "Unknown") + ")";
            card.appendChild(title);

            addSpecRow(card, "Filesystem", d.filesystem || "—");
            addSpecRow(card, "Capacity", formatBytes(d.total_bytes || 0));
            addSpecRow(card, "Used", formatBytes(d.used_bytes || 0) + " (" + (d.percent || 0).toFixed(1) + "%)");
            addSpecRow(card, "Free", formatBytes(d.free_bytes || 0));

            const bar = document.createElement("div");
            bar.className = "progress-bar";
            const fill = document.createElement("div");
            fill.className = "progress-fill" + (d.percent > 85 ? " warn" : "");
            fill.style.width = (d.percent || 0) + "%";
            bar.appendChild(fill);
            card.appendChild(bar);

            body.appendChild(card);
        });
    }

    function renderNetwork(adapters) {
        const body = document.getElementById("network-body");
        if (!body) return;
        body.replaceChildren();

        // Only show active adapters with an IP
        const active = adapters.filter(function (a) { return a.ip_address && a.is_up; });

        if (active.length === 0) {
            const p = document.createElement("p");
            p.className = "loading";
            p.textContent = "No active adapters";
            body.appendChild(p);
            return;
        }

        active.forEach(function (a) {
            const card = document.createElement("div");
            card.className = "sub-card";

            const title = document.createElement("div");
            title.className = "sub-card-title";
            title.textContent = a.name;
            card.appendChild(title);

            addSpecRow(card, "IP", a.ip_address || "—");
            if (a.mac_address) addSpecRow(card, "MAC", a.mac_address);
            if (a.speed_mbps) addSpecRow(card, "Speed", a.speed_mbps + " Mbps");

            body.appendChild(card);
        });
    }

    function addSpecRow(container, label, value) {
        const row = document.createElement("div");
        row.className = "spec-row";
        const l = document.createElement("span");
        l.className = "label";
        l.textContent = label;
        const v = document.createElement("span");
        v.className = "value";
        v.textContent = value;
        row.append(l, v);
        container.appendChild(row);
    }

    // --- WebSocket live metrics ---

    function connectWebSocket() {
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const url = protocol + "//" + location.host + "/ws/metrics";

        ws = new WebSocket(url);

        ws.onopen = function () {
            console.log("WebSocket connected");
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
        };

        ws.onmessage = function (event) {
            try {
                var msg = JSON.parse(event.data);
                if (msg.type === "metrics") {
                    updateLiveMetrics(msg.data);
                }
            } catch (e) {
                console.error("Parse error:", e);
            }
        };

        ws.onclose = function () {
            console.log("WebSocket closed, reconnecting...");
            scheduleReconnect();
        };

        ws.onerror = function () {
            ws.close();
        };
    }

    function scheduleReconnect() {
        if (!reconnectTimer) {
            reconnectTimer = setTimeout(function () {
                reconnectTimer = null;
                connectWebSocket();
            }, RECONNECT_DELAY_MS);
        }
    }

    function updateLiveMetrics(m) {
        // CPU
        setText("cpu-usage-text", Math.round(m.cpu_usage_percent || 0) + "%");
        setGauge("cpu-gauge", m.cpu_usage_percent || 0);
        setText("cpu-current-freq", m.cpu_frequency_mhz ? formatFreq(m.cpu_frequency_mhz) : "—");

        // Per-core bars
        if (m.cpu_per_core) {
            m.cpu_per_core.forEach(function (pct, i) {
                var fill = document.getElementById("core-" + i);
                if (fill) fill.style.height = pct + "%";
            });
        }

        // RAM
        setText("mem-usage-text", Math.round(m.ram_percent || 0) + "%");
        setGauge("mem-gauge", m.ram_percent || 0);
        var ramUsed = m.ram_used_bytes || 0;
        // We got total from static, compute available
        setText("mem-used", formatBytes(ramUsed));

        // GPU live
        if (m.gpu_metrics) {
            m.gpu_metrics.forEach(function (g, idx) {
                setText("gpu-usage-text-" + idx, Math.round(g.load_percent || 0) + "%");
                setGauge("gpu-gauge-" + idx, g.load_percent || 0);

                if (g.temperature_c !== null && g.temperature_c !== undefined) {
                    setText("gpu-temp-" + idx, g.temperature_c + "°C");
                }

                if (g.vram_total_mb && g.vram_used_mb !== undefined) {
                    setText("gpu-vram-text-" + idx,
                        formatBytes(g.vram_used_mb * 1024 * 1024) + " / " +
                        formatBytes(g.vram_total_mb * 1024 * 1024));

                    var pct = (g.vram_used_mb / g.vram_total_mb) * 100;
                    var bar = document.getElementById("gpu-vram-bar-" + idx);
                    if (bar) {
                        bar.style.width = pct + "%";
                        bar.className = "progress-fill" + (pct > 85 ? " warn" : "");
                    }
                }
            });
        }

        // Disk I/O
        setText("disk-read", formatRate(m.disk_read_bytes_sec || 0));
        setText("disk-write", formatRate(m.disk_write_bytes_sec || 0));

        // Network
        setText("net-sent", formatRate(m.net_sent_bytes_sec || 0));
        setText("net-recv", formatRate(m.net_recv_bytes_sec || 0));

        // Battery
        if (m.battery && m.battery.has_battery) {
            document.getElementById("battery-card").style.display = "";
            var batPct = m.battery.percent || 0;
            setText("bat-text", Math.round(batPct) + "%");
            setGauge("bat-gauge", batPct);
            setText("bat-status", m.battery.plugged_in ? "CHARGING" : "BAT");

            if (m.battery.time_remaining_sec) {
                var hrs = Math.floor(m.battery.time_remaining_sec / 3600);
                var mins = Math.floor((m.battery.time_remaining_sec % 3600) / 60);
                setText("bat-time", hrs + "h " + mins + "m");
            } else {
                setText("bat-time", m.battery.plugged_in ? "Plugged in" : "—");
            }
        }
    }

    // --- Init ---
    loadStaticSpecs();
    connectWebSocket();
})();
