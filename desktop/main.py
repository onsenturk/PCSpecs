"""PCSpecs — Privacy-first hardware specs viewer.

Launches a local web server on 127.0.0.1 (random port) and opens the
dashboard in a native app window. No data leaves your machine.
"""

from __future__ import annotations

import socket
import sys
import threading

import uvicorn
import webview


def get_free_port() -> int:
    """Get a random free port on localhost without network calls."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    port = get_free_port()
    url = f"http://127.0.0.1:{port}"

    print(r"""
    ____  ______   _____                    
   / __ \/ ____/  / ___/____  ___  __________
  / /_/ / /       \__ \/ __ \/ _ \/ ___/ ___/
 / ____/ /___    ___/ / /_/ /  __/ /__(__  ) 
/_/    \____/   /____/ .___/\___/\___/____/  
                    /_/                      
    """)
    print(f"  PCSpecs is running at: {url}")
    print(f"  Close the window or press Ctrl+C to exit.\n")
    print(f"  Privacy: bound to 127.0.0.1 only — no external access.\n")

    # Start uvicorn in a daemon thread so the native window is the main thread
    server_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={
            "app": "app:app",
            "host": "127.0.0.1",
            "port": port,
            "log_level": "warning",
            "access_log": False,
        },
        daemon=True,
    )
    server_thread.start()

    # Open native app window (blocks until closed)
    webview.create_window(
        "PCSpecs",
        url,
        width=1200,
        height=850,
        min_size=(800, 600),
        background_color="#0a0e1a",
    )
    webview.start()

    print("\n  PCSpecs stopped. Goodbye!")
    sys.exit(0)


if __name__ == "__main__":
    main()
