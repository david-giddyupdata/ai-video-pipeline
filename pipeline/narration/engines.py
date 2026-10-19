"""TTS engines behind one interface, so Andrew (Phase 0) can be swapped for the ElevenLabs clone (Phase 1).

Each engine returns MP3 bytes and word boundaries [(text, start_s, end_s)] in the spoken text.
"""
import asyncio
import socket
import time

import aiohttp
import edge_tts
from edge_tts.exceptions import NoAudioReceived

# GOTCHAS (2026-10-18): this PC's IPv6 route resets Microsoft's speech service now and then, as it does Hugging Face's
# (pipeline/hf_ipv4.py): its host resolves over IPv4 only. Every other host is left alone.
_EDGE_HOSTS = ("speech.platform.bing.com",)
_orig_getaddrinfo = socket.getaddrinfo


def _getaddrinfo_ipv4_for_edge(host, port, family=0, type=0, proto=0, flags=0):
    h = host.decode("ascii", "ignore") if isinstance(host, bytes) else host
    if family in (0, socket.AF_UNSPEC) and isinstance(h, str) and any(h == e or h.endswith("." + e)
                                                                       for e in _EDGE_HOSTS):
        family = socket.AF_INET
    return _orig_getaddrinfo(host, port, family, type, proto, flags)


if getattr(socket.getaddrinfo, "__name__", "") != "_getaddrinfo_ipv4_for_edge":
    socket.getaddrinfo = _getaddrinfo_ipv4_for_edge


class EdgeTTS:
    """Microsoft's neural voices through edge-tts. Free and keyless; word boundaries come with the audio."""
    name = "edge-tts"
    uses_neighbours = False                         # no request stitching, so neighbours stay out of the cache key
    output_format = "audio-24khz-48kbitrate-mono-mp3"

    def __init__(self, voice="en-US-AndrewNeural", rate="+0%", pitch="+0Hz", volume="+0%"):
        self.voice, self.rate, self.pitch, self.volume = voice, rate, pitch, volume

    def key_fields(self):
        return {"engine": self.name, "voice": self.voice, "rate": self.rate, "pitch": self.pitch,
                "volume": self.volume, "output_format": self.output_format}

    def synth(self, spoken_text, attempts=6):
        for i in range(attempts):                   # the online service drops connections and answers empty now and
            try:                                    # then (NoAudioReceived, GOTCHAS 2026-10-18)
                return asyncio.run(self._synth(spoken_text))
            except (aiohttp.ClientError, NoAudioReceived):
                if i == attempts - 1:
                    raise
                time.sleep(2 * (i + 1))

    async def _synth(self, text):
        comm = edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch, volume=self.volume,
                                    boundary="WordBoundary")
        audio, words = bytearray(), []
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
            elif chunk["type"] == "WordBoundary":
                s = chunk["offset"] / 1e7               # 100 ns ticks
                words.append((chunk["text"], round(s, 3), round(s + chunk["duration"] / 1e7, 3)))
        return bytes(audio), words


class ElevenLabs:
    """David's clone (R94) through ElevenLabs' own API: `with-timestamps` returns the audio with a time for every
    character of the text sent, which become the word boundaries. Request stitching: the neighbouring lines go along
    as previous_text and next_text, as context (not billed, and not part of the cache key: R99)."""
    name = "elevenlabs"
    uses_neighbours = True
    URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format={fmt}"

    def __init__(self, voice, model="eleven_multilingual_v2", output_format="mp3_44100_128", voice_settings=None):
        self.voice, self.model, self.output_format, self.voice_settings = voice, model, output_format, voice_settings

    def key_fields(self):
        return {"engine": self.name, "voice": self.voice, "model": self.model, "output_format": self.output_format,
                "voice_settings": self.voice_settings}

    def synth(self, spoken_text, previous_text=None, next_text=None, attempts=3):
        import base64
        import json
        import urllib.error
        import urllib.request
        from pipeline.config import get_section
        body = {"text": spoken_text, "model_id": self.model, "previous_text": previous_text, "next_text": next_text}
        if self.voice_settings:
            body["voice_settings"] = self.voice_settings
        req = urllib.request.Request(self.URL.format(voice=self.voice, fmt=self.output_format),
                                     data=json.dumps({k: v for k, v in body.items() if v is not None}).encode("utf-8"),
                                     headers={"xi-api-key": get_section("elevenlabs")["api_key"],
                                              "Content-Type": "application/json"})
        for i in range(attempts):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    res = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:            # rate limit or a server error: try again; else report
                if e.code not in (429, 500, 502, 503, 504) or i == attempts - 1:
                    raise RuntimeError(f"ElevenLabs {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None
            except urllib.error.URLError:
                if i == attempts - 1:
                    raise
            time.sleep(2 * (i + 1))
        return base64.b64decode(res["audio_base64"]), self.words(res["alignment"])

    @staticmethod
    def words(alignment):
        """Character times -> [(word, start_s, end_s)], a word being a run of characters between spaces."""
        out, cur = [], None
        for ch, t0, t1 in zip(alignment["characters"], alignment["character_start_times_seconds"],
                              alignment["character_end_times_seconds"]):
            if ch.isspace():
                if cur:
                    out.append(tuple(cur))
                cur = None
            elif cur:
                cur[0], cur[2] = cur[0] + ch, t1
            else:
                cur = [ch, t0, t1]
        if cur:
            out.append(tuple(cur))
        return [(w, round(a, 3), round(b, 3)) for w, a, b in out]


ENGINES = {"edge-tts": EdgeTTS, "elevenlabs": ElevenLabs}


def make(voice_cfg):
    """voice.json -> engine. Keys starting with label_pause (the respeller's), sentence_pause (the build's check) or
    word_timing (pipeline.narration.timing, R227) are not the engine's, and stay out of the cache key."""
    cfg = {k: v for k, v in voice_cfg.items() if not k.startswith(("label_pause", "sentence_pause", "word_timing"))}
    return ENGINES[cfg.pop("engine")](**cfg)
