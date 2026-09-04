#!/usr/bin/env python3
"""Exercise the Docker desktop/control/reset contract without an LLM."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import ImageChops, ImageStat

from sci.vm import VManager


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="scienceboard:0.1")
    parser.add_argument("--startup-timeout", type=int, default=240)
    parser.add_argument(
        "--screenshot",
        default=".artifacts/runtime-smoke.png",
        help="path used to retain a visual smoke-test artifact",
    )
    parser.add_argument(
        "--app-screenshot",
        default=".artifacts/runtime-vscode.png",
        help="path used to retain the VS Code launch artifact",
    )
    parser.add_argument(
        "--launcher-screenshot",
        default=".artifacts/runtime-launcher.png",
        help="path used to retain the GNOME Alt+F2 launcher artifact",
    )
    parser.add_argument(
        "--browser-screenshot",
        default=".artifacts/runtime-firefox.png",
        help="path used to retain the Firefox launch artifact",
    )
    parser.add_argument(
        "--browser-search-screenshot",
        default=".artifacts/runtime-firefox-search.png",
        help="path used to retain the GNOME Firefox search artifact",
    )
    parser.add_argument(
        "--browser-home-screenshot",
        default=".artifacts/runtime-firefox-home.png",
        help="path used to retain the no-onboarding Firefox home artifact",
    )
    args = parser.parse_args()

    report = {}
    manager = VManager(
        version="0.1",
        provider_name="docker",
        docker_image=args.image,
        docker_startup_timeout=args.startup_timeout,
    )
    with manager:
        first_container = manager.env.container_id
        first_machine_id = (manager.read_file("/etc/machine-id") or "").strip()
        assert re.fullmatch(r"[0-9a-f]{32}", first_machine_id), (
            "container did not receive a fresh machine ID"
        )
        screenshot = manager.screenshot()
        report["screen_size"] = list(screenshot.size)
        assert screenshot.size == (1280, 800)
        screenshot_path = Path(args.screenshot)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot.save(screenshot_path)
        report["screenshot"] = str(screenshot_path)

        raw_tree = manager.controller.get_accessibility_tree()
        assert isinstance(raw_tree, str) and "<desktop" in raw_tree
        report["accessibility_bytes"] = len(raw_tree.encode())

        wm_probe = manager._request("POST/execute", {
            "json": {
                "command": ["bash", "-lc", "pgrep -x gnome-shell"],
                "shell": False,
            }
        }).json()
        assert wm_probe["returncode"] == 0, wm_probe
        changed_pixels = 0
        launcher_after = None
        # Mutter registers global keybindings just after the control service
        # becomes healthy. Retry across that small startup race.
        for _ in range(10):
            launcher_before = manager.screenshot().convert("RGB")
            manager("pyautogui.click(640, 400); pyautogui.hotkey('alt', 'f2')")
            time.sleep(1)
            candidate = manager.screenshot().convert("RGB")
            launcher_diff = ImageChops.difference(launcher_before, candidate)
            changed_pixels = launcher_diff.convert("L").point(
                lambda value: 255 if value > 8 else 0
            ).histogram()[255]
            if changed_pixels > 5_000:
                launcher_after = candidate
                break
            manager("pyautogui.press('esc')")
            time.sleep(1)
        assert launcher_after is not None, (
            f"Alt+F2 changed only {changed_pixels} pixels; launcher not visible"
        )
        launcher_screenshot_path = Path(args.launcher_screenshot)
        launcher_screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        launcher_after.save(launcher_screenshot_path)
        manager("pyautogui.press('esc')")
        report["gnome_launcher"] = "passed"
        report["gnome_launcher_changed_pixels"] = changed_pixels
        report["gnome_launcher_screenshot"] = str(launcher_screenshot_path)

        # Cross-application tasks often find a browser through Activities
        # rather than typing its executable into Alt+F2.  The reference VM's
        # distro desktop file is marked NoDisplay because snapd normally
        # publishes a second entry, so explicitly guard the replacement entry
        # supplied by the Docker image.
        manager(
            "pyautogui.click(49, 14); time.sleep(1); "
            "pyautogui.write('firefox', interval=0.08)"
        )
        search_deadline = time.monotonic() + 15
        browser_search_tree = ""
        while time.monotonic() < search_deadline:
            browser_search_tree = manager.controller.get_accessibility_tree()
            if (
                isinstance(browser_search_tree, str)
                and "Firefox Web Browser" in browser_search_tree
            ):
                break
            time.sleep(0.5)
        assert (
            isinstance(browser_search_tree, str)
            and "Firefox Web Browser" in browser_search_tree
        ), "Firefox is not discoverable through GNOME Activities"
        browser_search_screenshot_path = Path(args.browser_search_screenshot)
        browser_search_screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        manager.screenshot().save(browser_search_screenshot_path)
        report["firefox_app_search"] = "passed"
        report["firefox_app_search_screenshot"] = str(
            browser_search_screenshot_path
        )

        manager("pyautogui.press('enter')")
        browser_home_deadline = time.monotonic() + 45
        browser_home_tree = ""
        onboarding_markers = (
            "Skip this step",
            "Start browsing",
            "Firefox has your back",
        )
        while time.monotonic() < browser_home_deadline:
            browser_home_tree = manager.controller.get_accessibility_tree()
            if not isinstance(browser_home_tree, str):
                time.sleep(1)
                continue
            if any(marker in browser_home_tree for marker in onboarding_markers):
                break
            if "Firefox" in browser_home_tree and (
                "New Tab" in browser_home_tree
                or "Search with" in browser_home_tree
            ):
                break
            time.sleep(1)
        assert isinstance(browser_home_tree, str)
        assert not any(
            marker in browser_home_tree for marker in onboarding_markers
        ), "Firefox displayed first-run onboarding"
        assert "Firefox" in browser_home_tree and (
            "New Tab" in browser_home_tree or "Search with" in browser_home_tree
        ), "Firefox did not reach a ready home page within 45s"
        browser_home_screenshot_path = Path(args.browser_home_screenshot)
        browser_home_screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        manager.screenshot().save(browser_home_screenshot_path)
        report["firefox_onboarding"] = "absent"
        report["firefox_home_screenshot"] = str(browser_home_screenshot_path)

        probe = manager._request("POST/execute", {
            "json": {
                "command": [
                    "bash", "-lc",
                    "set -e; command -v chimerax; test -x /app/bin/kalgebra; "
                    "test -x /app/bin/celestia-qt6; command -v grass; "
                    "command -v texstudio; command -v code; "
                    "/home/user/.elan/bin/lean --version; glxinfo -B",
                ],
                "shell": False,
            }
        }).json()
        assert probe["returncode"] == 0, probe
        report["binary_and_glx_probe"] = "passed"

        launch = manager._request("POST/setup/launch", {
            "json": {
                "command": "code /home/user/sci /home/user/sci/Sci/Basic.lean",
                "shell": True,
            }
        })
        launch.raise_for_status()
        deadline = time.monotonic() + 45
        app_screenshot = None
        while time.monotonic() < deadline:
            candidate = manager.screenshot().convert("RGB")
            app_tree = manager.controller.get_accessibility_tree()
            # GNOME's wallpaper is already non-uniform, so require both a
            # rendered window and an application-specific accessibility node.
            has_code_window = (
                "Basic.lean" in app_tree or "Visual Studio Code" in app_tree
            )
            if has_code_window and max(ImageStat.Stat(candidate).stddev) > 8:
                app_screenshot = candidate
                break
            time.sleep(1)
        assert app_screenshot is not None, "VS Code did not render within 45s"
        app_screenshot_path = Path(args.app_screenshot)
        app_screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        app_screenshot.save(app_screenshot_path)
        report["vscode_launch"] = "passed"
        report["vscode_screenshot"] = str(app_screenshot_path)

        # Firefox was launched through Activities above. Switch back from VS
        # Code and exercise a real cross-application browser navigation while
        # both accessibility trees are present.
        manager(
            "pyautogui.hotkey('alt', 'tab'); time.sleep(1); "
            "pyautogui.hotkey('ctrl', 'l'); "
            "pyautogui.write('https://example.com', interval=0.02); "
            "pyautogui.press('enter')"
        )
        deadline = time.monotonic() + 45
        browser_screenshot = None
        while time.monotonic() < deadline:
            browser_tree = manager.controller.get_accessibility_tree()
            if not isinstance(browser_tree, str):
                time.sleep(1)
                continue
            page_ready = "Example Domain" in browser_tree
            keyring_prompt = (
                "Authentication required" in browser_tree
                or "Unlock Login Keyring" in browser_tree
            )
            if page_ready and not keyring_prompt:
                browser_screenshot = manager.screenshot().convert("RGB")
                break
            time.sleep(1)
        assert browser_screenshot is not None, (
            "Firefox did not load the smoke page without a keyring prompt "
            "within 45s"
        )
        browser_screenshot_path = Path(args.browser_screenshot)
        browser_screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        browser_screenshot.save(browser_screenshot_path)
        report["firefox_launch"] = "passed"
        report["firefox_launch_method"] = "gnome-activities"
        report["firefox_keyring_prompt"] = "absent"
        report["firefox_screenshot"] = str(browser_screenshot_path)

        marker = "/home/user/.scienceboard-reset-probe"
        assert manager.write_file(marker, "must disappear")
        assert manager.read_file(marker) == "must disappear"

        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as source:
            source.write("binary-upload-contract")
            source.flush()
            uploaded = "/home/user/.scienceboard-upload-probe"
            assert manager.upload_file(source.name, uploaded)
            assert manager.read_file(uploaded) == "binary-upload-contract"
        report["binary_upload"] = "passed"

        with tempfile.TemporaryDirectory() as directory:
            recording = str(Path(directory) / "record.mp4")
            manager.record_start()
            manager("pyautogui.moveTo(100, 100, duration=0.2)")
            time.sleep(2)
            manager.record_stop(recording)
            report["recording_bytes"] = Path(recording).stat().st_size
            assert report["recording_bytes"] > 1000

        assert manager.revert("sci_bench")
        second_container = manager.env.container_id
        assert second_container != first_container
        second_machine_id = (manager.read_file("/etc/machine-id") or "").strip()
        assert re.fullmatch(r"[0-9a-f]{32}", second_machine_id)
        assert second_machine_id != first_machine_id
        assert manager.read_file(marker) is None
        assert manager.screenshot().size == (1280, 800)
        report["fresh_machine_identity"] = "passed"
        report["immutable_reset"] = "passed"

    report["cleanup"] = "passed"
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
