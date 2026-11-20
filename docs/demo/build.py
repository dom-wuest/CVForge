"""Rebuild the previews in docs/images/ from the demo data next to this file.

    uv run python docs/demo/build.py              # CV, letter, dashboard
    uv run python docs/demo/build.py --website    # plus a screenshot of the live site

Everything runs in a throwaway home: the demo applications, sender.yaml as its
private.yaml and the invented signature are copied into a temporary folder,
and CVFORGE_HOME points there. The real home is never read, and nothing is
written to out/. The CV is resolved with the public profile, exactly what the
website publishes, so no private value can reach a preview.

Screenshots need Microsoft Edge or Chrome; the PDFs and page images need only
Typst. Rebuild after a change to the templates or to data/cv-en.yaml.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGES = HERE.parent / "images"
SLUG = "2026-10-acme-rendering-engineer"
# The dashboard's "today". Pinned so the screenshot does not change with the
# day it is rebuilt; the demo dossiers' dates are set around it.
NOW = dt.datetime(2026, 11, 20, 9, 0)
WEBSITE = "https://dom-wuest.de/about/"
PPI = "110"

BROWSERS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge",
    "google-chrome",
    "chromium",
)


def make_home() -> Path:
    home = Path(tempfile.mkdtemp(prefix="cvforge-demo-"))
    shutil.copytree(HERE / "home" / "applications", home / "applications")
    (home / "private").mkdir()
    shutil.copyfile(HERE / "sender.yaml", home / "private.yaml")
    shutil.copyfile(HERE / "signature.svg", home / "private" / "signature.svg")
    return home


def browser() -> str | None:
    for candidate in BROWSERS:
        found = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if found:
            return found
    return None


def screenshot(exe: str, url: str, target: Path, size: str, dark: bool = False) -> None:
    profile = tempfile.mkdtemp(prefix="cvforge-shot-")
    cmd = [
        exe,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--force-device-scale-factor=1.5",
        f"--user-data-dir={profile}",
        f"--window-size={size}",
        f"--screenshot={target}",
        f"--blink-settings=preferredColorScheme={0 if dark else 1}",
        "--virtual-time-budget=4000",
        url,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    shutil.rmtree(profile, ignore_errors=True)
    print(f"  wrote {target.relative_to(HERE.parent.parent).as_posix()}")


# ─── A screenshot that starts at an element ─────────────────────────────────
# `--screenshot` always shows the top of the page, and the website's CV heading
# has no id to jump to. So the browser is driven over the DevTools protocol:
# load the page, ask where the heading is, capture from just above it. The
# protocol is JSON over a websocket; the client below is the few lines of
# RFC 6455 that this needs, so the script stays on the standard library.


class _Socket:
    def __init__(self, url: str) -> None:
        rest = url.removeprefix("ws://")
        hostport, _, path = rest.partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n".encode()
        )
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.sock.recv(1)
        if b" 101 " not in response.split(b"\r\n")[0]:
            raise RuntimeError(f"websocket handshake failed: {response[:80]!r}")
        self.next_id = 0

    def _exact(self, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("browser closed the connection")
            data += chunk
        return data

    def _send(self, text: str) -> None:
        payload = text.encode()
        n = len(payload)
        header = bytes([0x81])  # FIN, text frame
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 1 << 16:
            header += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)  # a client must mask every frame
        self.sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _receive(self) -> str:
        message = b""
        while True:
            first, second = self._exact(2)
            n = second & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._exact(8))[0]
            message += self._exact(n)
            if first & 0x80:  # FIN: the last fragment
                return message.decode()

    def call(self, method: str, **params) -> dict:
        self.next_id += 1
        self._send(json.dumps({"id": self.next_id, "method": method, "params": params}))
        while True:  # events arrive in between; skip them
            reply = json.loads(self._receive())
            if reply.get("id") == self.next_id:
                if "error" in reply:
                    raise RuntimeError(f"{method}: {reply['error']}")
                return reply["result"]


def screenshot_from(exe: str, url: str, target: Path, top_js: str, size=(1280, 1000)) -> None:
    """Capture `size` CSS pixels of `url`, starting 32 px above the y that
    `top_js` evaluates to."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    profile = tempfile.mkdtemp(prefix="cvforge-shot-")
    proc = subprocess.Popen(
        [
            exe,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list") as r:
                    pages = [t for t in json.load(r) if t["type"] == "page"]
                if pages:
                    break
            except OSError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("the browser did not open its debugging port")
        ws = _Socket(pages[0]["webSocketDebuggerUrl"])
        width, height = size
        ws.call(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=height,
            deviceScaleFactor=1.5,
            mobile=False,
        )
        ws.call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "light"}],
        )
        ws.call("Page.navigate", url=url)
        expression = (
            "new Promise(done => { const go = () => document.fonts.ready.then("
            "() => setTimeout(() => done(" + top_js + "), 500));"
            " document.readyState === 'complete' ? go() : addEventListener('load', go); })"
        )
        time.sleep(0.5)  # let the navigation replace about:blank
        top = ws.call("Runtime.evaluate", expression=expression, awaitPromise=True)
        y = max(0, top["result"]["value"] - 32)
        shot = ws.call(
            "Page.captureScreenshot",
            format="png",
            captureBeyondViewport=True,
            clip={"x": 0, "y": y, "width": width, "height": height, "scale": 1},
        )
        target.write_bytes(base64.b64decode(shot["data"]))
        ws.sock.close()
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(profile, ignore_errors=True)
    print(f"  wrote {target.relative_to(HERE.parent.parent).as_posix()}")


# Where the CV starts on the website: the heading that says so.
CV_HEADING = (
    "[...document.querySelectorAll('h1, h2')]"
    ".find(h => h.textContent.trim() === 'Curriculum Vitae')"
    ".getBoundingClientRect().top + scrollY"
)


def pages_to_png(service, paths, main: Path, inputs: dict[str, str], stem: str) -> None:
    for old in IMAGES.glob(f"{stem}-*.png"):
        old.unlink()
    target = IMAGES / f"{stem}-{{p}}.png"
    cmd = [service.typst(), "compile", str(main.relative_to(paths.ROOT)), str(target)]
    cmd += service._typst_args(main, inputs) + ["--format", "png", "--ppi", PPI]
    subprocess.run(cmd, cwd=paths.ROOT, check=True)
    for png in sorted(IMAGES.glob(f"{stem}-*.png")):
        print(f"  wrote {png.relative_to(paths.ROOT).as_posix()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--website", action="store_true", help=f"also screenshot {WEBSITE}")
    args = parser.parse_args()

    home = make_home()
    os.environ["CVFORGE_HOME"] = str(home)
    # Typst stamps each PDF with the build time; pinned, a rebuild with nothing
    # changed writes byte-identical PDFs and git sees no change.
    os.environ["SOURCE_DATE_EPOCH"] = str(int(NOW.replace(tzinfo=dt.UTC).timestamp()))
    # paths resolves the home on import, so import only after setting it.
    from cvforge import dashboard, letter, paths, resolve, service

    IMAGES.mkdir(exist_ok=True)
    artifact = paths.BUILD / "demo" / "cv-en.json"
    written = [artifact, paths.letter_resolved(SLUG)]
    try:
        # The CV, public profile: what the website shows.
        resolve.write("en", "public", target=artifact)
        inputs = service._cv_inputs("en", artifact)
        service.compile_typst(paths.CV_MAIN, IMAGES / "cv-en.pdf", inputs)
        pages_to_png(service, paths, paths.CV_MAIN, inputs, "cv-en")

        # The letter, from the demo application.
        letter.write_letter(SLUG)
        written.append(paths.BUILD / "private" / "signature.svg")
        inputs = {"slug": SLUG, "lang": "en"}
        service.compile_letter(SLUG, "en", IMAGES / "letter-en.pdf")
        pages_to_png(service, paths, paths.LETTER_MAIN, inputs, "letter-en")

        # The dashboard, light and dark, overview and one application.
        exe = browser()
        if exe is None:
            print("  note: no Edge or Chrome found; skipping the screenshots", file=sys.stderr)
            return 0
        page = dashboard.write(NOW).as_uri()
        for dark in (False, True):
            theme = "dark" if dark else "light"
            screenshot(exe, page, IMAGES / f"dashboard-{theme}.png", "1280,1300", dark)
            screenshot(
                exe,
                f"{page}#/app/{SLUG}",
                IMAGES / f"dashboard-app-{theme}.png",
                "1280,1300",
                dark,
            )
        if args.website:
            screenshot_from(exe, WEBSITE, IMAGES / "website.png", CV_HEADING)
    finally:
        shutil.rmtree(home, ignore_errors=True)
        for path in written:
            path.unlink(missing_ok=True)
        (paths.BUILD / "demo").rmdir() if (paths.BUILD / "demo").is_dir() else None
    return 0


if __name__ == "__main__":
    sys.exit(main())
