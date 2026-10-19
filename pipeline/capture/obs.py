"""OBS control through obs-websocket v5.

The pipeline records in its own OBS profile and scene collection ("AIDV"), so David's "Untitled" setup is never
edited. OBSCapture switches to AIDV for the take and switches back afterwards, even if the take fails.

Capture is a Display Capture of the right-hand monitor, with the cursor off. That monitor has no taskbar, and Edge is
maximized on it, so the 1920x1080 frame is exactly the browser window (tabs and address bar included). Display capture
is used rather than Window Capture because OBS finds windows by title, and Edge's title changes on every page.

OBS quirks handled here: switching a profile restarts video, so replies can arrive after the client gives up, and a
late reply then gets matched to the next request. Every call therefore reconnects after a timeout, and retries while
OBS answers 207 ("not ready").
"""
import logging
import time
from pathlib import Path

import obsws_python as obs

logging.getLogger("obsws_python").setLevel(logging.CRITICAL)   # it logs every handled timeout as a traceback
from obsws_python.error import OBSSDKRequestError, OBSSDKTimeoutError

from pipeline.config import (CAPTURE_MONITOR_X, FRAME, OBS_COLLECTION, OBS_HOST, OBS_PORT, OBS_PROFILE, OBS_SCENE,
                             OBS_SOURCE, RUNS, get_section)

FPS = 30
PROFILE_PARAMS = [                      # Simple output mode: MKV (survives a crash), high quality, GPU encoder
    ("Output", "Mode", "Simple"),
    ("SimpleOutput", "RecFormat2", "mkv"),
    ("SimpleOutput", "RecQuality", "HQ"),
    ("SimpleOutput", "RecEncoder", "nvenc"),
]


class OBSCapture:
    def __init__(self):
        self._password = get_section("obs")["websocket_password"]
        self._connect()
        self.prev_profile = self.call("get_profile_list").current_profile_name
        self.prev_collection = self.call("get_scene_collection_list").current_scene_collection_name

    def _connect(self):
        self.c = obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=self._password, timeout=10)

    def call(self, name, *args, tries=40):
        """Request with reconnect-on-timeout and retry-while-not-ready."""
        for _ in range(tries):
            try:
                return getattr(self.c, name)(*args)
            except OBSSDKTimeoutError:
                time.sleep(1.0)
                self._connect()
            except OBSSDKRequestError as e:
                if getattr(e, "code", None) != 207:
                    raise
                time.sleep(0.5)
        raise RuntimeError(f"OBS request {name} kept failing")

    # -- setup -------------------------------------------------------------------------------------------------
    def setup(self, record_dir: Path):
        if self.call("get_record_status").output_active:
            raise RuntimeError("OBS is already recording; stop it first")
        if OBS_PROFILE in self.call("get_profile_list").profiles:
            self._switch("profile", OBS_PROFILE)
        else:
            self.call("create_profile", OBS_PROFILE)          # creating also switches to it
            self._wait_for("profile", OBS_PROFILE)
        for cat, name, value in PROFILE_PARAMS:
            self.call("set_profile_parameter", cat, name, value)
        self.call("set_video_settings", FPS, 1, FRAME[0], FRAME[1], FRAME[0], FRAME[1])
        record_dir.mkdir(parents=True, exist_ok=True)
        self.call("set_record_directory", str(record_dir))

        if OBS_COLLECTION in self.call("get_scene_collection_list").scene_collections:
            self._switch("collection", OBS_COLLECTION)
        else:
            self.call("create_scene_collection", OBS_COLLECTION)
            self._wait_for("collection", OBS_COLLECTION)
        if OBS_SCENE not in [s["sceneName"] for s in self.call("get_scene_list").scenes]:
            self.call("create_scene", OBS_SCENE)
        if OBS_SOURCE not in [i["inputName"] for i in self.call("get_input_list").inputs]:
            self.call("create_input", OBS_SCENE, OBS_SOURCE, "monitor_capture", {"capture_cursor": False}, True)
            time.sleep(0.5)
        self.call("set_input_settings", OBS_SOURCE, {"monitor_id": self._monitor_id(), "capture_cursor": False}, True)
        self.call("set_current_program_scene", OBS_SCENE)
        return self

    def _monitor_id(self):
        items = self.call("get_input_properties_list_property_items", OBS_SOURCE, "monitor_id").property_items
        for it in items:                                        # names look like "Dell ...: 1920x1080 @ 1920,0"
            if f"@ {CAPTURE_MONITOR_X},0" in it["itemName"]:
                return it["itemValue"]
        raise RuntimeError("capture monitor not found among: " + "; ".join(i["itemName"] for i in items))

    def _current(self, kind):
        return (self.call("get_profile_list").current_profile_name if kind == "profile"
                else self.call("get_scene_collection_list").current_scene_collection_name)

    def _wait_for(self, kind, name, wait=30):
        t0 = time.time()
        while time.time() - t0 < wait:
            if self._current(kind) == name:
                time.sleep(0.5)
                return
            time.sleep(0.5)
        raise RuntimeError(f"OBS did not switch {kind} to {name!r} within {wait}s")

    def _switch(self, kind, name):
        if self._current(kind) == name:
            return
        try:
            getattr(self.c, "set_current_profile" if kind == "profile" else "set_current_scene_collection")(name)
        except OBSSDKTimeoutError:
            self._connect()                                      # reply may still arrive; never reuse that socket
        except OBSSDKRequestError as e:
            if getattr(e, "code", None) != 207:
                raise
        self._wait_for(kind, name)

    # -- recording ---------------------------------------------------------------------------------------------
    def start(self, timeout=10):
        self.call("start_record")
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.call("get_record_status").output_active:
                return
            time.sleep(0.05)
        raise RuntimeError("OBS did not start recording")

    def stop(self) -> Path:
        path = Path(self.call("stop_record").output_path)
        for _ in range(100):                                    # wait until the file is closed
            if not self.call("get_record_status").output_active:
                break
            time.sleep(0.1)
        time.sleep(1.0)
        return path

    def versions(self):
        v = self.call("get_version")
        return {"obs": v.obs_version, "obs_websocket": v.obs_web_socket_version}

    # -- restore -----------------------------------------------------------------------------------------------
    def restore(self):
        try:
            if self.call("get_record_status").output_active:
                self.call("stop_record")
                time.sleep(1.0)
        finally:
            self._switch("collection", self.prev_collection)
            self._switch("profile", self.prev_profile)


if __name__ == "__main__":                                      # dry setup check: switch, report, switch back
    o = OBSCapture()
    if o.prev_profile == OBS_PROFILE:                           # left over from an interrupted run
        o.prev_profile = "Untitled"
    try:
        o.setup(RUNS / "_obs_check")
        v = o.call("get_video_settings")
        print("AIDV ready:", v.base_width, v.base_height, f"{v.fps_numerator} fps", "| monitor ok |", o.versions())
    finally:
        o.restore()
        print("restored:", o._current("profile"), "/", o._current("collection"))
