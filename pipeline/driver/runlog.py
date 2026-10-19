"""Run log writer (SPEC §5). One header record, then one event record per line. Every record is validated against
schemas/runlog.schema.json as it is written, so a malformed log fails the take immediately rather than in the edit."""
import json
import time
from datetime import datetime, timezone

import jsonschema

from pipeline.config import SCHEMAS

_VALIDATOR = jsonschema.Draft202012Validator(json.loads((SCHEMAS / "runlog.schema.json").read_text(encoding="utf-8")))


def _wall():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


class RunLog:
    def __init__(self, path, origin_epoch=None):
        """A new log, or (origin_epoch: the first log's origin in epoch seconds) the same log continued by the take's
        resume after the Part 5 pause (R70), on the same clock: t_mono runs on from the first recording's."""
        self.path = path
        if origin_epoch is None:
            self.origin, self.origin_epoch = time.perf_counter(), time.time()
            self._f = open(path, "w", encoding="utf-8")
        else:
            self.origin, self.origin_epoch = time.perf_counter() - (time.time() - origin_epoch), origin_epoch
            self._f = open(path, "a", encoding="utf-8")

    def now(self):
        return round(time.perf_counter() - self.origin, 3)

    def _write(self, rec):
        _VALIDATOR.validate(rec)
        self._f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._f.flush()

    def header(self, **fields):
        self._write({"record": "header", **fields})

    def event(self, phase, step_id=None, *, t=None, action=None, tab=None, url_host=None, box=None, frame_chain=(),
              line_id=None, result=None, detail=None):
        rec = {"record": "event", "t_mono": self.now() if t is None else t, "t_wall": _wall(), "step_id": step_id,
               "phase": phase, "action": action, "tab": tab, "url_host": url_host,
               "target_css_box": box, "frame_chain": list(frame_chain), "line_id": line_id, "result": result,
               "detail": detail}
        self._write(rec)
        return rec["t_mono"]

    def close(self):
        self._f.close()
