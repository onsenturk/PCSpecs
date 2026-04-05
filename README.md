# PCSpecs

A free, portable Windows tool that shows your complete PC hardware specs with live monitoring — in a native app window. No install required. No data leaves your machine.

## Features

- **CPU** — model, cores/threads, frequency, per-core usage bars
- **GPU** — name, VRAM, temperature, load (NVIDIA via GPUtil + WMI fallback for AMD/Intel)
- **RAM** — total, speed, slot layout, live usage
- **Storage** — NVMe / SSD / HDD detection, capacity, read/write rates
- **Motherboard & BIOS** — manufacturer, model, version
- **Network** — adapters, IPs, MAC addresses, link speed
- **Battery** — charge level, plugged-in status, time remaining
- **Live Metrics** — real-time CPU, RAM, GPU, disk I/O, and network streamed over WebSocket

## How It Works

PCSpecs opens a native desktop window via [pywebview](https://pywebview.flowrl.com/) and reads your hardware specs directly using OS-level APIs (WMI, psutil, GPUtil). Live metrics update in real time. Everything runs locally — no data leaves your machine.

## Quick Start

### Option A: Download the portable `.exe`

Grab the latest release from the [Releases page](https://github.com/onsenturk/PCSpecs/releases/latest) and run it. No installation needed — Windows 10/11.

### Option B: Run from source

```bash
cd desktop
pip install -r requirements.txt
python main.py
```

Requires Python 3.12+.

### Build the `.exe` yourself

```bash
cd desktop
pip install -r requirements.txt
pyinstaller pcspecs.spec --noconfirm
# Output: desktop/dist/PCSpecs.exe
```

## Project Structure

```text
desktop/            # Desktop application (Python)
  main.py           # Entry point — starts server + native window
  app.py            # FastAPI app with REST + WebSocket endpoints
  pcspecs.spec      # PyInstaller build spec
  requirements.txt  # Python dependencies
  specs/
    base.py         # Platform-agnostic dataclasses & abstract collector
    windows.py      # Windows collector (WMI, psutil, GPUtil, py-cpuinfo)
    __init__.py     # Auto-detects platform, returns correct collector
  static/           # Frontend dashboard (HTML/CSS/JS)

web/                # Landing page (static site)
  index.html        # Marketing page hosted on Azure Static Web Apps
  staticwebapp.config.json
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, uvicorn, WebSocket |
| Hardware detection | psutil, WMI, GPUtil, py-cpuinfo |
| Native window | pywebview (Edge Chromium) |
| Packaging | PyInstaller |
| Landing page | Azure Static Web Apps |
| CI/CD | GitHub Actions |

## CI/CD

- **`build-desktop.yml`** — builds the `.exe` on push to `desktop/`, uploads artifact, creates a GitHub Release on version tags
- **`deploy-web.yml`** — deploys the landing page to Azure Static Web Apps on push to `web/`

## Privacy

- The server binds to `127.0.0.1` only — no external network access
- CORS restricted to localhost origins
- Security headers enforced (CSP, X-Frame-Options, X-Content-Type-Options)
- No analytics, no telemetry, no data collection

## Platform Support

| Platform | Status |
|---|---|
| Windows 10/11 | Supported |
| macOS | Not yet — contributions welcome (`specs/macos.py`) |
| Linux | Not yet — contributions welcome (`specs/linux.py`) |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

macOS and Linux collector implementations are the most impactful contributions right now — see [specs/\_\_init\_\_.py](desktop/specs/__init__.py) for the expected interface.
