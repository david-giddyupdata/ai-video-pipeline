"""A generated image's subject on a transparent background: rembg with BiRefNet (MIT), beside the white flood fill.

    cutout(src_png, dst_png, decontaminate=False) -> dst_png
    cutout_many([(src, dst), ...]) -> [dst], one model load for all

    python -m pipeline.ml.cutout <art.png> [...] [--suffix=_alpha] [--no-dc] [--cpu] [--force]
        each picture's cutout beside it, <name><suffix>.png, with -dc unless --no-dc; an existing file is kept
        unless --force (R154). tools/gen_image.py --cutout runs this on new art (R227).

Why: tools/gen_image.py --key-white and tools/key_enclosed.py key the white around generated art by flood fill (now
the fallback; R227 made this the way generated art is cut out).
That misses white a shape encloses (the padlock's shackle, David's note 11) unless key_enclosed finds it, and it
leaves hard edges. BiRefNet finds the subject itself, so enclosed background goes too and the edge is soft.
decontaminate (rembg's -dc) pulls the old background's colour out of those soft edge pixels, so a white backdrop
doesn't leave a pale rim over a dark screen. Compared on our art: research/huggingface/INSTALL_r1.md.

Where it can fail: BiRefNet looks for "the main object", so thin, pale or detached strokes (text, sparkles, a shadow)
can be dropped. Look at the result over a dark and a light frame, as for any keyed art, and keep flood fill when the
art is a flat drawing on clean white.

model: "birefnet-general" (the default here, about 0.97 GB). Never rembg's own default (bria-rmbg, RMBG-2.0,
non-commercial); the worker refuses anything but BiRefNet. For photos of David (hair), BiRefNet_HR-matting is the
better model (MIT; not installed). Runs in the ML venv through pipeline.ml.paths.run, CPU or "cuda".
"""
import argparse
import sys
from pathlib import Path

from pipeline.ml import paths


def cutout_many(pairs, model="birefnet-general", device="cuda", decontaminate=False, stats=None):
    """[(src png, dst png)] -> [dst]: each source's subject, RGBA, written to its destination."""
    items = [{"src": str(Path(s).resolve()), "dst": str(Path(d).resolve())} for s, d in pairs]
    if not items:
        return []
    reply = paths.run("cutout_worker", {"model": model, "device": device, "decontaminate": decontaminate,
                                        "items": items})
    if stats is not None:
        stats.update({k: reply[k] for k in ("device", "providers", "load_s")})
        stats["seconds"] = [it["seconds"] for it in reply["items"]]
    return [it["dst"] for it in reply["items"]]


def cutout(src, dst, model="birefnet-general", device="cuda", decontaminate=False):
    """One image's subject on transparency, written to dst."""
    return cutout_many([(src, dst)], model, device, decontaminate)[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description="BiRefNet cutouts of pictures, each written beside it (R227)")
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--suffix", default="_alpha", help="appended to the name (default _alpha, gen_image's)")
    ap.add_argument("--no-dc", action="store_true", help="leave the edge pixels' old background colour in")
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--force", action="store_true", help="replace an existing cutout")
    a = ap.parse_args(argv)
    pairs = [(f, f.with_name(f.stem + a.suffix + ".png")) for f in a.files]
    kept = [d for _, d in pairs if d.exists() and not a.force]
    for d in kept:
        print(f"{d} exists; kept (--force to replace it)")
    pairs = [(s_, d) for s_, d in pairs if d not in kept]
    st = {}
    for d in cutout_many(pairs, device="cpu" if a.cpu else "cuda", decontaminate=not a.no_dc, stats=st):
        print(d)
    if pairs:
        print(f"{len(pairs)} cutout(s) on {st['device']} ({st['load_s']} s loading, {sum(st['seconds']):.1f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
