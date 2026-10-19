"""R139: generated art for overlays (a drop-in still where the layout has leeway) through OpenRouter's image models.

    python tools/gen_image.py <out.png> --model=<id> --prompt="..." [--from=<in.png>] [--cutout | --key-white]
                              [--log=<costs.json>] [--aspect=16:9] [--size=1K|2K|4K] [--api=chat|images] [--force]

One call: the prompt (and, with --from, an image to edit, so two states of one object match) goes to the model; the
first image in the reply is saved to out.png, and the call's cost as OpenRouter reported it is appended to the log
(default: costs.json beside out.png).

Art for compositing (an object on plain white) gets <out>_alpha.png beside it, its background transparent:
  --cutout     the way to cut art out (R227): BiRefNet through pipeline.ml.cutout, with rembg's -dc (the white pulled
               out of the soft edge, so no pale rim over a dark screen). It finds the object itself, so white the
               object encloses (the padlock's shackle, David's note 11) goes too, and the edge is soft. About 1 s on
               the GPU after 6 to 7 s loading. Look at the result over a dark and a light frame, as for any keyed art:
               BiRefNet can drop thin, pale or detached strokes (research/huggingface/INSTALL_r1.md, item 3).
  --key-white  the fallback: the white connected to the image's edges made transparent by a flood fill (hard edges;
               enclosed white stays, which tools/key_enclosed.py then keys). For a flat drawing on clean white, or
               when the ML venv isn't there.
The cost row is written before either runs, so a failed cutout never loses it; the paid image is kept, and its
cutout can be made again from it (python -m pipeline.ml.cutout <out.png>). Neither is for a background or a plate.

--aspect and --size go to OpenRouter's image_config (aspect_ratio, image_size; the Gemini image models take both),
for a frame-shaped plate such as an avatar's background. --api=images uses OpenRouter's image endpoint, the only one serving Krea and FLUX (--from there becomes
input_references); --from may repeat. An existing out.png is never replaced without --force (each is paid), and the
cost log gets a row for every reply that arrived and every failure after sending ("error", "file": null), since a
reply with no image in it may still be billed. The key is read through pipeline.config.get_section (R4) and never
written or printed.
"""
import argparse
import base64
import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
URL = "https://openrouter.ai/api/v1/chat/completions"
IMAGES_URL = "https://openrouter.ai/api/v1/images"
RETRIES, RETRY_S = 2, 20            # a 429 from an upstream pool: wait 20 s, then 40 s


def _data_url(path):
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(Path(path).suffix.lower(),
                                                                                   "image/png")
    return f"data:{mime};base64,{base64.b64encode(Path(path).read_bytes()).decode()}"


def key_white(src, dst, tol=18):
    """The white background connected to the image's edges made transparent; the object keeps its own whites."""
    from PIL import Image
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    px = im.load()
    seen = bytearray(w * h)
    stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    mp = mask.load()
    while stack:
        x, y = stack.pop()
        i = y * w + x
        if seen[i]:
            continue
        seen[i] = 1
        r, g, b, _ = px[x, y]
        if min(r, g, b) < 255 - tol:
            continue
        mp[x, y] = 255
        if x > 0: stack.append((x - 1, y))
        if x < w - 1: stack.append((x + 1, y))
        if y > 0: stack.append((x, y - 1))
        if y < h - 1: stack.append((x, y + 1))
    alpha = Image.eval(mask, lambda v: 255 - v)
    im.putalpha(alpha)
    im.save(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--from", dest="src", action="append", default=[])
    keying = ap.add_mutually_exclusive_group()
    keying.add_argument("--cutout", action="store_true", help="BiRefNet -dc cutout to <out>_alpha.png (R227)")
    keying.add_argument("--key-white", action="store_true", help="the flood-fill fallback to <out>_alpha.png")
    ap.add_argument("--log")
    ap.add_argument("--aspect")
    ap.add_argument("--size")
    ap.add_argument("--api", choices=("chat", "images"), default="chat")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    from pipeline.config import get_section
    out = Path(a.out)
    if out.exists() and not a.force:                 # a paid image is never replaced by a re-typed command
        raise SystemExit(f"{out} exists (paid); --force to make it again")
    out.parent.mkdir(parents=True, exist_ok=True)
    refs = [{"type": "image_url", "image_url": {"url": _data_url(p)}} for p in a.src]
    if a.api == "images":                            # the image endpoint: Krea, FLUX and most image-only models
        url = IMAGES_URL
        sent = {k: v for k, v in (("aspect_ratio", a.aspect), ("resolution", a.size)) if v}
        payload = {"model": a.model, "prompt": a.prompt, "n": 1, **sent,
                   **({"input_references": refs} if refs else {})}
    else:
        url = URL
        sent = {k: v for k, v in (("aspect_ratio", a.aspect), ("image_size", a.size)) if v}
        payload = {"model": a.model, "modalities": ["image", "text"], "usage": {"include": True},
                   "messages": [{"role": "user", "content": [{"type": "text", "text": a.prompt}, *refs]}]}
        if sent:
            payload["image_config"] = sent
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Authorization": f"Bearer {get_section('openrouter')['api_key']}",
                                          "Content-Type": "application/json", "X-Title": "AIDV overlay art"})
    log = Path(a.log) if a.log else out.parent / "costs.json"
    t0 = time.time()

    def record(resp=None, error=None):
        """The call in the cost log: every reply that arrived (it may have been billed with no image in it), and
        every failure after the request left (timeouts too, cost unknown), so the log and OpenRouter's ledger agree."""
        u = (resp or {}).get("usage") or {}
        rec = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "file": None if error else out.name,
               "model": (resp or {}).get("model", a.model), "api": a.api,
               "from": [Path(p).name for p in a.src] or None, "params": sent or None, "prompt": a.prompt,
               "seconds": round(time.time() - t0, 1), "prompt_tokens": u.get("prompt_tokens"),
               "completion_tokens": u.get("completion_tokens"), "cost_usd": u.get("cost"),
               **({"error": error[:300]} if error else {})}
        rows = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
        rows.append(rec)
        log.write_text(json.dumps(rows, indent=1), encoding="utf-8")
        return rec

    resp = None
    for attempt in range(RETRIES + 1):
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=300))
            break
        except urllib.error.HTTPError as e:          # the reason OpenRouter gives (a rate limit, the cap, a refusal)
            body = e.read().decode("utf-8", "replace")[:500]
            if e.code == 429 and attempt < RETRIES:  # an upstream pool's rate limit clears in seconds
                time.sleep(RETRY_S * (attempt + 1))
                continue
            raise SystemExit(f"OpenRouter HTTP {e.code}: {body}")    # refused before any work: nothing billed
        except (urllib.error.URLError, TimeoutError, OSError) as e:   # the model may have run: log it, cost unknown
            record(error=f"{type(e).__name__}: {e}")
            raise SystemExit(f"OpenRouter call failed after sending: {e}")
    try:
        if a.api == "images":
            data = resp.get("data") or []
            if not data:
                raise ValueError(f"no image in the reply: {json.dumps(resp)[:300]}")
            raw = base64.b64decode(data[0]["b64_json"])
        else:
            msg = resp["choices"][0]["message"]
            imgs = msg.get("images") or []
            if not imgs:
                raise ValueError(f"no image in the reply: {str(msg.get('content'))[:300]}")
            raw = base64.b64decode(imgs[0]["image_url"]["url"].split(",", 1)[1])
    except (ValueError, KeyError, IndexError, TypeError) as e:       # billed, maybe, but no image: logged first
        record(resp, error=str(e))
        raise SystemExit(str(e))
    from PIL import Image
    im = Image.open(io.BytesIO(raw))                 # the format from the bytes, not the reply's label
    if out.suffix.lower() == ".png" and im.format != "PNG":
        im.save(out)
    else:
        out.write_bytes(raw)
    rec = record(resp)                               # before any cutout: a failed cutout never loses the cost row
    print(f"{out}: {rec['model']}, ${rec['cost_usd'] or 0:.4f}, {rec['seconds']} s")
    alpha = out.with_name(out.stem + "_alpha.png")
    if a.key_white:
        key_white(out, alpha)
        print(f"{alpha}: white flood fill (the fallback)")
    elif a.cutout:
        from pipeline.ml import cutout
        try:
            cutout.cutout(out, alpha, decontaminate=True)
        except Exception as e:                       # the paid image is saved: say how to finish without paying again
            raise SystemExit(f"the cutout failed ({type(e).__name__}: {str(e)[-400:]}); {out} is saved and its cost "
                             f"logged. Cut it out again with: python -m pipeline.ml.cutout {out}  (or the flood fill: "
                             f"python tools/key_enclosed.py {out})")
        print(f"{alpha}: BiRefNet cutout (R227)")


if __name__ == "__main__":
    main()
