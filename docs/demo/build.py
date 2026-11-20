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
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile
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
            screenshot(exe, WEBSITE, IMAGES / "website.png", "1280,1500")
    finally:
        shutil.rmtree(home, ignore_errors=True)
        for path in written:
            path.unlink(missing_ok=True)
        (paths.BUILD / "demo").rmdir() if (paths.BUILD / "demo").is_dir() else None
    return 0


if __name__ == "__main__":
    sys.exit(main())
