"""Check markers on a built project's full sequence (R106): "Round N check" at the timecodes David should look at.

    python -m pipeline.edit.ppro.markers <project.prproj> <markers.json> [--sequence=<name>]

markers.json: {"sequence": "<name>", "markers": [{"t": <seconds on that sequence>, "name": "Round 4 check",
"comment": "..."}]}. Opens the project through the AIDV bridge, only when no project is open in Premiere (R104: never
touch a project it didn't open), adds each marker, saves and closes it. Round 3's markers were added this way by hand;
this is the same ExtendScript, kept.
"""
import json
import sys
from pathlib import Path

from pipeline.edit.ppro.bridge import call, start


def add(prproj, sequence, markers):
    prproj = str(Path(prproj).resolve())
    code = """(function () {
      if (app.projects.numProjects > 0) { throw new Error("a project is open in Premiere (" + app.projects[0].path + ")"); }
      if (!app.openDocument(%s)) { throw new Error("Premiere wouldn't open " + %s); }
      var s = aidvFindSequence(%s);
      if (!s) { throw new Error("no sequence named " + %s); }
      var ms = %s, n = 0;
      for (var i = 0; i < ms.length; i++) {
        var m = s.markers.createMarker(ms[i].t);
        m.name = ms[i].name;
        m.comments = ms[i].comment || "";
        n++;
      }
      app.project.save();
      var path = app.project.path;
      app.project.closeDocument(true, false);
      return {added: n, project: path, markers: s.markers.numMarkers};
    })()""" % (json.dumps(prproj), json.dumps(prproj), json.dumps(sequence), json.dumps(sequence),
               json.dumps([{"t": float(m["t"]), "name": m["name"], "comment": m.get("comment", "")} for m in markers]))
    return call(code, timeout=300)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    job = json.loads(Path(args[1]).read_text(encoding="utf-8"))
    seq = next((a.split("=", 1)[1] for a in argv if a.startswith("--sequence=")), job.get("sequence"))
    print(json.dumps(start(), ensure_ascii=False))
    r = add(args[0], seq, job["markers"])
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main(sys.argv[1:]))
