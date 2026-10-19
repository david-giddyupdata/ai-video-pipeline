"""Upload a render to YouTube as a PRIVATE video (David, 2026-10-06: private only).

    python -m pipeline.publish.youtube <video.mp4> --title="..." [--description="..."]

Sign-in is shared with GiddyUpSocial (src/youtube_manager/auth.py): the OAuth client config comes from AWS Secrets
Manager giddyup/config -> youtube_oauth, and the token is cached at ~/.giddyup/youtube_token.json (off OneDrive). The
first run, or a run after the token expires (the client is in Testing mode: 7-day refresh tokens), opens a browser for
David to sign in. An upload costs 1,600 of the 10,000 daily quota units. Each upload is logged next to the video in
youtube_uploads.json.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from pipeline.config import get_section

SCOPES = ["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.force-ssl"]  # = GiddyUpSocial
TOKEN = Path.home() / ".giddyup" / "youtube_token.json"
PRIVACY = "private"                       # fixed: this module never publishes publicly or unlisted
EDUCATION = "27"


def service():
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as err:
            print(f"token refresh failed ({type(err).__name__}); signing in again")
            creds = None
    if not creds or not creds.valid:
        print("A browser window opens for the Google sign-in (pick the GiddyUp Data channel's account).", flush=True)
        creds = InstalledAppFlow.from_client_config(get_section("youtube_oauth"), SCOPES).run_local_server(port=0)
    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def upload(video, title, description=""):
    video = Path(video).resolve()
    yt = service()
    channel = yt.channels().list(part="snippet", mine=True).execute()["items"][0]
    print(f"channel: {channel['snippet']['title']} ({channel['id']})", flush=True)
    body = {"snippet": {"title": title[:100], "description": description, "categoryId": EDUCATION},
            "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": False}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  uploaded {status.progress():.0%}", flush=True)
    vid = resp["id"]
    privacy = resp["status"]["privacyStatus"]
    if privacy != PRIVACY:                # belt and braces: never leave a non-private upload
        yt.videos().update(part="status", body={"id": vid, "status": {"privacyStatus": PRIVACY}}).execute()
    rec = {"video_id": vid, "url": f"https://youtu.be/{vid}", "studio": f"https://studio.youtube.com/video/{vid}/edit",
           "title": title, "file": video.name, "privacy": PRIVACY, "channel_id": channel["id"],
           "uploaded": datetime.now().astimezone().isoformat(timespec="seconds")}
    log = video.parent / "youtube_uploads.json"
    rows = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    log.write_text(json.dumps(rows + [rec], indent=2), encoding="utf-8")
    return rec


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = lambda k: next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith(f"--{k}=")), None)
    if not args or not opt("title"):
        sys.exit(__doc__)
    print(json.dumps(upload(args[0], opt("title"), opt("description") or ""), indent=2))
