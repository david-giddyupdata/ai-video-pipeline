"""R119: delete only the Quick Sight datasets, analyses and dashboards a run of ours created, and nothing else.

    python tools/qs_cleanup.py snapshot <file.json>                       # the account's assets before a run
    python tools/qs_cleanup.py diff <file.json>                           # what appeared since the snapshot
    python tools/qs_cleanup.py delete <file.json> --names=A,B,C [--data-sources] [--yes]   # those, if named A, B or C
    python tools/qs_cleanup.py orphans --name=<name> --before=<date> [--yes]   # R245's one-off: older copies of a name

An asset is ours only when all three hold: its id isn't in the snapshot, it was created after the snapshot was taken,
and its name is one the run typed (--names: Section A's are Uploaded-MonthlySummary, A-FirstBuild and
A-FirstBuild-Dashboard). A snapshot from another account or region is refused. Only the three kinds R119 names are
deleted, dashboards first; if a dashboard can't be deleted, its analysis and dataset are kept, so nothing is left
broken. New data sources (an upload leaves a file data source behind, even a cancelled one) and users are listed for
David, never deleted, unless --data-sources. Analyses keep Quick Sight's recovery window (no force). On the Standard
edition DeleteDashboard is Enterprise-only, so a dashboard is deleted from the Dashboards page in the Quick Sight
profile (off camera), and only when its name is unique. Without --yes, delete only prints what it would do. The
account id is never printed.

--data-sources (R245: a retake's Athena data source): a new data source that passes the same three tests is deleted
too, after the run's datasets, and only when no other dataset uses it (each dataset's DataSourceArn, from
DescribeDataSet). The API hides an upload dataset's source, so such a dataset keeps every file data source (and none of
another type); a dataset that can't be described keeps them all.

orphans (R245's one-off: the manual walk's "Athena-Feb2021Flights" copies): the datasets of exactly that name created
before the date, then its data sources, printed; with --yes deleted, each logged in runs/qs_cleanup_log.jsonl (kind,
name, id, creation time, result). A date alone is midnight on this machine's clock: the walk's second pair was made at
22:54 on 2026-10-13 in Texas, the 14th in UTC. A dataset that a live analysis or dashboard or another dataset uses is
kept, and so is a data source that a dataset left in the account uses.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3

REGION = "us-east-1"
LOG = Path(__file__).resolve().parents[1] / "runs" / "qs_cleanup_log.jsonl"   # orphans --yes: what it deleted
TWELVE_DIGITS = re.compile(r"\d{12}")
KINDS = {   # kind: (list call, list key, id field, delete call, id argument)
    "dashboard": ("list_dashboards", "DashboardSummaryList", "DashboardId", "delete_dashboard", "DashboardId"),
    "analysis": ("list_analyses", "AnalysisSummaryList", "AnalysisId", "delete_analysis", "AnalysisId"),
    "dataset": ("list_data_sets", "DataSetSummaries", "DataSetId", "delete_data_set", "DataSetId"),
    "data source": ("list_data_sources", "DataSources", "DataSourceId", None, None),
}


def client():
    return boto3.client("sts").get_caller_identity()["Account"], boto3.client("quicksight", region_name=REGION)


def inventory(acct, qs):
    """Every asset of each kind, deleted analyses included (one restored later must not look new)."""
    out = {}
    for kind, (call, key, idf, _, _) in KINDS.items():
        items, token = [], None
        while True:
            r = getattr(qs, call)(AwsAccountId=acct, **({"NextToken": token} if token else {}))
            items += [{"id": i[idf], "name": i.get("Name"), "status": i.get("Status"),
                       "created": i["CreatedTime"].isoformat() if i.get("CreatedTime") else None}
                      for i in r.get(key, [])]
            token = r.get("NextToken")
            if not token:
                break
        out[kind] = items
    return out


def new_since(path, acct, qs):
    try:
        snap = json.loads(Path(path).read_text(encoding="utf-8"))
        taken = datetime.fromisoformat(snap["taken"])
        assert snap["account"] == acct and snap["region"] == REGION and taken.tzinfo and "assets" in snap
    except Exception:
        raise SystemExit(f"{path} is not a snapshot of this account and region (or an old format); nothing done")
    now = inventory(acct, qs)
    new = {}
    for k in KINDS:
        known = {b["id"] for b in snap["assets"].get(k, [])}
        unknown = [i for i in now[k] if i["id"] not in known and i["status"] != "DELETED"]
        new[k] = [i for i in unknown if i["created"] and datetime.fromisoformat(i["created"]) > taken]
        for i in unknown:
            if i not in new[k]:                        # never ours to delete, but say so: silence looks clean
                print(f"not in the snapshot but not newer than it (left alone): {k} {i['name']}")
    return new, now


def quiet(err, acct):
    """An error's message without the account id (an ARN in it carries it), shortened."""
    return TWELVE_DIGITS.sub("<account>", str(err).replace(acct, "<account>"))[:200]


def made(i):
    """An asset's creation time on this machine's clock, for printing."""
    return datetime.fromisoformat(i["created"]).astimezone().strftime("%Y-%m-%d %H:%M %z") if i["created"] else "?"


def last(arn):
    return arn.rsplit("/", 1)[-1]                   # an ARN's id: never print the ARN itself (the account id)


def uses(acct, qs, datasets):
    """What the datasets given are built on, from DescribeDataSet: {data source id: [dataset names]}, {dataset id:
    [names of the datasets built on it]}, the datasets whose source the API hides and those that couldn't be
    described. Hidden: a physical table naming no data source (an upload's, as this account's read), or no data source
    named at all (DescribeDataSet's partial answer for a dataset with an uploaded file: no physical table)."""
    sources, parents, hidden, unread = {}, {}, [], []
    for d in datasets:
        try:
            ds = qs.describe_data_set(AwsAccountId=acct, DataSetId=d["id"])["DataSet"]
        except Exception as err:
            print(f"couldn't describe dataset {d['name']}: {type(err).__name__}: {quiet(err, acct)}")
            unread.append(d["name"])
            continue
        named = False
        for t in (ds.get("PhysicalTableMap") or {}).values():
            arns = [v["DataSourceArn"] for v in t.values() if isinstance(v, dict) and v.get("DataSourceArn")]
            if not arns and d["name"] not in hidden:
                hidden.append(d["name"])
            for a in arns:
                sources.setdefault(last(a), []).append(d["name"])
            named = named or bool(arns)
        if not named and d["name"] not in hidden:
            hidden.append(d["name"])
        for t in (ds.get("LogicalTableMap") or {}).values():
            if (t.get("Source") or {}).get("DataSetArn"):
                parents.setdefault(last(t["Source"]["DataSetArn"]), []).append(d["name"])
    return sources, parents, hidden, unread


def source_users(acct, qs, src, use):
    """The datasets that use (or may use) a data source: by DataSourceArn; an upload's dataset, whose source the API
    hides, for a file data source (or one whose type can't be read); and any dataset that couldn't be described."""
    sources, _, hidden, unread = use
    by = list(sources.get(src["id"], []))
    if hidden:
        try:
            kind = qs.describe_data_source(AwsAccountId=acct, DataSourceId=src["id"])["DataSource"].get("Type")
        except Exception as err:
            print(f"couldn't describe data source {src['name']}: {type(err).__name__}: {quiet(err, acct)}")
            kind = None
        if kind in (None, "FILE"):
            by += [f"{n} (an upload: its source unknown)" for n in hidden]
    by += [f"{n} (not described)" for n in unread]
    return sorted(set(by))


def delete_sources(acct, qs, items, datasets, yes, log=None):
    """R245: delete each data source given that none of `datasets` (those left in the account once the run's are
    gone) uses. Datasets always go first: a data source is never deleted from under one."""
    unsettled = [i for i in items if i["status"] == "DELETED" or (i["status"] or "").endswith("_IN_PROGRESS")]
    for i in unsettled:                                 # gone already, or mid-change: not touched (a failed create
        print(f"left alone ({i['status']}): data source {i['name']} ({i['id']})")   # or update is still ours)
    items = [i for i in items if i not in unsettled]
    use = uses(acct, qs, datasets) if items else None
    for i in items:
        by = source_users(acct, qs, i, use)
        if by:
            print(f"kept data source {i['name']} ({i['id']}, made {made(i)}): dataset {', '.join(by)} uses it")
            continue
        if not yes:
            print(f"would delete data source {i['name']} ({i['id']}, made {made(i)})")
            continue
        try:
            qs.delete_data_source(AwsAccountId=acct, DataSourceId=i["id"])
            print(f"deleted data source {i['name']} ({i['id']})")
            result = "deleted"
        except Exception as err:
            result = f"failed: {type(err).__name__}: {quiet(err, acct)}"
            print(f"NOT deleted: data source {i['name']} ({i['id']}): {result[8:]}")
        if log:
            log("data source", i, result)


def viewers(acct, qs, now):
    """{dataset id: [names of the live analyses and dashboards using it]}, and those that couldn't be described."""
    used, unread = {}, []
    for kind, call, idarg, key in (("analysis", "describe_analysis", "AnalysisId", "Analysis"),
                                   ("dashboard", "describe_dashboard", "DashboardId", "Dashboard")):
        for a in now[kind]:
            if a["status"] == "DELETED":                 # in the recovery window: nothing on show to break
                continue
            try:
                r = getattr(qs, call)(AwsAccountId=acct, **{idarg: a["id"]})[key]
            except Exception as err:
                print(f"couldn't describe {kind} {a['name']}: {type(err).__name__}: {quiet(err, acct)}")
                unread.append(f"{kind} {a['name']}")
                continue
            for arn in r.get("DataSetArns") or (r.get("Version") or {}).get("DataSetArns") or []:
                used.setdefault(last(arn), []).append(f"{kind} {a['name']}")
    return used, unread


def orphans(argv, acct, qs):
    """R245's one-off: the datasets, then the data sources, of exactly --name created before --before."""
    opt = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in argv if a.startswith("--") and "=" in a}
    name, when = opt.get("--name", "").strip(), opt.get("--before", "").strip()
    try:
        before = datetime.fromisoformat(when)
    except ValueError:
        before = None
    if not name or before is None:
        print("orphans needs --name=<the exact name> and --before=<date or ISO time>")
        return 2
    if before.tzinfo is None:
        before = before.astimezone()                     # a date alone: midnight on this machine's clock
    yes = "--yes" in argv
    now = inventory(acct, qs)
    pick = {}
    for kind in ("dataset", "data source"):
        pick[kind] = []
        for i in now[kind]:
            if i["name"] != name:
                continue
            if i["created"] and datetime.fromisoformat(i["created"]) < before:
                pick[kind].append(i)
                print(f"orphan {kind}: {name} ({i['id']}, made {made(i)})")
            else:                                        # never an orphan, but say so: silence looks clean
                print(f"left alone (made {made(i)}, not before {when}): {kind} {name}")
    if not any(pick.values()):
        print(f"no {name!r} dataset or data source made before {when}")
        return 0

    def log(kind, i, result):
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "cmd": "orphans", "kind": kind,
                                 "name": i["name"], "id": i["id"], "created": i["created"], "result": result}) + "\n")

    gone = set()
    if pick["dataset"]:
        mine = {d["id"] for d in pick["dataset"]}
        on_view, unread = viewers(acct, qs, now)
        _, parents, _, ds_unread = uses(acct, qs, [d for d in now["dataset"] if d["id"] not in mine])
        unread += [f"dataset {n}" for n in ds_unread]   # (a dataset not described may be built on it)
        for d in pick["dataset"]:
            by = on_view.get(d["id"], []) + [f"dataset {n}" for n in parents.get(d["id"], [])]
            if by or unread:                             # (one that couldn't be described may use it)
                why = []
                if by:
                    why.append(f"{', '.join(by)} uses it")
                if unread:
                    why.append(f"{', '.join(unread)} couldn't be read")
                print(f"kept dataset {name} ({d['id']}): {'; '.join(why)}")
                continue
            if not yes:
                print(f"would delete dataset {name} ({d['id']}, made {made(d)})")
                gone.add(d["id"])
                continue
            try:
                qs.delete_data_set(AwsAccountId=acct, DataSetId=d["id"])
                print(f"deleted dataset {name} ({d['id']})")
                gone.add(d["id"])
                result = "deleted"
            except Exception as err:
                result = f"failed: {type(err).__name__}: {quiet(err, acct)}"
                print(f"NOT deleted: dataset {name} ({d['id']}): {result[8:]}")
            log("dataset", d, result)
    delete_sources(acct, qs, pick["data source"], [d for d in now["dataset"] if d["id"] not in gone], yes,
                   log if yes else None)
    if yes:
        print(f"logged in {LOG}")
    return 0


def delete_in_page(kind, item, now):
    """A dashboard on Standard: deleted from the Dashboards list in the Quick Sight profile (R113, off camera), in a tab
    of its own that is closed after. Only when its name is unique in the account, so the row can't be another's."""
    if kind != "dashboard" or sum(d["name"] == item["name"] for d in now["dashboard"]
                                  if d["status"] != "DELETED") != 1:
        return False
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pipeline.capture import browser
    prof = browser.use("quicksight")
    from pipeline.vendor import cs
    pg = cs.context().new_page()
    try:
        pg.goto(prof["start_url"].replace("/start", "/start/dashboards"), wait_until="domcontentloaded")
        row = pg.locator("[role=row]").filter(has=pg.get_by_text(item["name"], exact=True)).first
        row.wait_for(timeout=20000)
        row.locator("[data-automation-id=card_context_menu_dropdown_button]").click()
        pg.locator("[role=menuitem]").filter(has_text="Delete").locator("visible=true").first.click()
        dlg = pg.locator("[role=dialog]").filter(has_text="Delete Dashboard").locator("visible=true").first
        dlg.get_by_role("button", name="Delete", exact=True).click()
        pg.get_by_text(item["name"], exact=True).wait_for(state="detached", timeout=20000)
        return True
    except Exception as err:                       # a changed page: report it, never abort the rest half-done
        print(f"page delete of {item['name']!r} failed: {type(err).__name__}: "
              f"{TWELVE_DIGITS.sub('<account>', str(err))[:120]}")
        return False
    finally:
        pg.close()


def main(argv):
    """Any error stops the tool with its message alone, the account id taken out: boto3's errors (throttling,
    AccessDenied, a failed delete) carry ARNs, and an ARN carries the account id, so no traceback is printed."""
    try:
        return run(argv)
    except Exception as err:
        print(f"stopped: {type(err).__name__}: {TWELVE_DIGITS.sub('<account>', str(err))[:300]}")
        return 1


def run(argv):
    args = [a for a in argv if not a.startswith("--")]
    if args == ["orphans"]:
        return orphans(argv, *client())
    if len(args) != 2 or args[0] not in ("snapshot", "diff", "delete"):
        print(__doc__)
        return 2
    cmd, path = args
    acct, qs = client()
    if cmd == "snapshot":
        inv = inventory(acct, qs)
        Path(path).write_text(json.dumps({"account": acct, "region": REGION,
                                          "taken": datetime.now(timezone.utc).isoformat(), "assets": inv},
                                         indent=1), encoding="utf-8")
        print("snapshot:", {k: len(v) for k, v in inv.items()})
        return 0
    new, now = new_since(path, acct, qs)
    for k, items in new.items():
        for i in items:
            print(f"new {k}: {i['name']} ({i['id']})")
    if cmd == "diff":
        return 0
    names = {n.strip() for n in next((a.split("=", 1)[1] for a in argv if a.startswith("--names=")), "").split(",")}
    names -= {""}
    if not names:
        print("delete needs --names: the names the run typed (anything else new is left alone)")
        return 2
    kept_dashboard = False
    gone = set()                                               # what was deleted (without --yes: would be)
    for kind in ("dashboard", "analysis", "dataset"):          # dependants first
        call, idarg = KINDS[kind][3], KINDS[kind][4]
        for i in new[kind]:
            if i["name"] not in names:
                print(f"left alone (not a name the run typed): {kind} {i['name']}")
                continue
            if kind != "dashboard" and kept_dashboard:
                print(f"kept {kind} {i['name']}: a dashboard of ours is still there and would break")
                continue
            if "--yes" not in argv:
                print(f"would delete {kind} {i['name']}")
                gone.add(i["id"])
                continue
            try:
                getattr(qs, call)(AwsAccountId=acct, **{idarg: i["id"]})
                print(f"deleted {kind} {i['name']}")
                gone.add(i["id"])
            except qs.exceptions.UnsupportedUserEditionException:   # Standard: DeleteDashboard is Enterprise-only
                if delete_in_page(kind, i, now):
                    print(f"deleted {kind} {i['name']} in the page")
                    gone.add(i["id"])
                else:
                    kept_dashboard = True
                    print(f"NOT deleted: {kind} {i['name']} (delete it by hand)")
    if "--data-sources" not in argv:
        for i in new["data source"]:
            print(f"left for David (R119 doesn't cover data sources): {i['name']}")
        return 0
    ours = []                                                  # R245: the same three tests, then nothing using it
    for i in new["data source"]:
        if i["name"] in names:
            ours.append(i)
        else:
            print(f"left alone (not a name the run typed): data source {i['name']}")
    delete_sources(acct, qs, ours, [d for d in now["dataset"] if d["id"] not in gone], "--yes" in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
