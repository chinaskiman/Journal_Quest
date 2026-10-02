"""Desktop (pywebview) entry point for Trade Quest V2 - Phase C build spike.

Responsibilities, in order:

1. Import ``app2.config`` FIRST (Phase A frozen path resolution) and only then
   ``app2.db`` / ``app2.main`` - ``db`` builds its engine from ``config.DB_URL``
   at import time.
2. Guard the port so a second launch fails loudly instead of opening a blank
   window (Phase B found two launches collide on 8001).
3. Start Uvicorn in a background thread using the FastAPI **app object** (never
   an "module:attr" string, which cannot resolve inside a frozen bundle).
4. Wait for real readiness - poll ``/api/system/health`` - with a bounded
   timeout. No arbitrary sleep decides readiness.
5. Open the bundled SPA in a native pywebview window (WebView2 backend).
6. When the window closes, ask Uvicorn to stop and join the thread, so no
   orphaned backend thread/process survives.

Security: binds only to ``config.HOST`` (``127.0.0.1``, hard-coded, no env
override). No Python<->JS bridge is exposed - the frontend talks to the local
HTTP API exactly as it does in the browser.
"""
from __future__ import annotations

import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request

APP_TITLE = "Trade Quest"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 860
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 600
READY_TIMEOUT_SECONDS = 30.0
READY_POLL_SECONDS = 0.25
SHUTDOWN_GRACE_SECONDS = 15.0


def _message_box(title: str, message: str) -> None:
    """Best-effort native dialog; silently skipped if unavailable."""
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:  # noqa: BLE001 - never let reporting break reporting
        pass


def _fatal(title: str, detail: str = "") -> None:
    print("")
    print("=" * 70)
    print(f"[Trade Quest] {title}")
    print("=" * 70)
    if detail:
        print(detail)
    print("")
    sys.stdout.flush()
    sys.stderr.flush()
    _message_box(f"{APP_TITLE} - startup failed", f"{title}\n\n{detail}".strip())


def port_is_available(host: str, port: int) -> bool:
    """True when nothing is currently listening on host:port.

    On Windows SO_EXCLUSIVEADDRUSE makes the probe honest (no shared-bind or
    TIME_WAIT surprises).  There is an unavoidable tiny race between closing the
    probe socket and Uvicorn binding; that is acceptable for this spike and is
    documented rather than hidden behind a complex mechanism.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform == "win32":
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except OSError:
                pass
        sock.bind((host, port))
    except OSError:
        return False
    finally:
        sock.close()
    return True


def wait_until_ready(host: str, port: int, timeout: float) -> bool:
    """Poll the real health endpoint until it answers, or time out."""
    url = f"http://{host}:{port}/api/system/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(READY_POLL_SECONDS)
    return False


def main() -> int:
    # --- 1. import order: config -> db -> app -----------------------------
    try:
        from app2 import config
    except Exception:  # noqa: BLE001
        _fatal("Could not load application configuration.",
               traceback.format_exc())
        return 1
    try:
        from app2.main import app
    except Exception:  # noqa: BLE001
        _fatal("Could not load the Trade Quest backend.",
               traceback.format_exc())
        return 1

    host = config.HOST
    port = config.DEFAULT_PORT

    try:
        import uvicorn
    except Exception:  # noqa: BLE001
        _fatal("uvicorn is missing from the bundle.", traceback.format_exc())
        return 1
    try:
        import webview
    except Exception:  # noqa: BLE001
        _fatal("pywebview is missing from the bundle.", traceback.format_exc())
        return 1

    url = f"http://{host}:{port}"

    print("[Trade Quest] mode      : frozen desktop")
    print(f"[Trade Quest] host      : {host}")
    print(f"[Trade Quest] data dir  : {config.DATA_DIR}")
    print(f"[Trade Quest] static dir: {config.static_dir()}")
    sys.stdout.flush()

    # --- 2. second-launch guard ------------------------------------------
    if not port_is_available(host, port):
        _fatal(
            f"{APP_TITLE} is already running (port {port} is in use).",
            "No new window was opened. Switch to the running window, or close "
            "it first if it is not responding.",
        )
        return 1

    # --- 3. backend in a background thread (app OBJECT) ------------------
    server = uvicorn.Server(
        uvicorn.Config(
            app, host=host, port=port, log_level="warning", access_log=False,
        )
    )
    thread = threading.Thread(target=server.run, name="tq-backend", daemon=True)
    thread.start()

    try:
        # --- 4. readiness before navigating the window --------------------
        if not wait_until_ready(host, port, READY_TIMEOUT_SECONDS):
            _fatal(
                "The Trade Quest backend did not become ready in time.",
                f"Waited {READY_TIMEOUT_SECONDS:.0f}s for {url}/api/system/health."
                "\nRun the development launcher (start_tradequest_v2.bat) to see "
                "the full error output.",
            )
            return 1

        print(f"[Trade Quest] backend ready at {url}")
        sys.stdout.flush()

        # --- 5. native window over the bundled SPA -----------------------
        webview.create_window(
            APP_TITLE, url,
            width=WINDOW_WIDTH, height=WINDOW_HEIGHT,
            min_size=(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT),
            confirm_close=False,
        )
        webview.start()  # blocks until the window is closed
    except Exception:  # noqa: BLE001
        _fatal("The Trade Quest desktop window failed.", traceback.format_exc())
        return 1
    finally:
        # --- 6. always stop the backend (no orphan thread/process) -------
        server.should_exit = True
        thread.join(timeout=SHUTDOWN_GRACE_SECONDS)
        if thread.is_alive():  # pragma: no cover - defensive
            print("[Trade Quest] backend thread did not stop in time; "
                  "the process will exit.")
        print("[Trade Quest] backend stopped.")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())