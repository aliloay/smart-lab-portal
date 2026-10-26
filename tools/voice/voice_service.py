"""
Local voice for the AI assistant (2026-10-26): speech-to-text (faster-whisper) and text-to-speech (Piper), both on
this laptop's CPU - no audio leaves the lab, nothing is stored. The portal backend is the only client
(/api/voice/*, same login + limits as typed questions); the spoken question then goes through the SAME assistant
path as a typed one (same tools, same permissions; door / robot commands are never possible from the assistant).

Cameras keep the GPU: Whisper runs int8 on the CPU with 2 threads, ONE transcription at a time (busy -> 429, the
browser says "busy, try again"); Piper likewise one at a time.

    py -3.12 tools/voice/voice_service.py         # 127.0.0.1:5320, key VOICE_KEY (tools/voice/voice.env)
Models (git-ignored): Whisper from Hugging Face (Systran/faster-whisper-<model>, cached on first start),
Piper voice in tools/voice/models/ (README.md).
"""
from __future__ import annotations

import hmac
import io
import json
import os
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_AUDIO_BYTES = 2_000_000          # ~2 min of opus; the browser caps a question at 30 s anyway
MAX_AUDIO_S = 30.0
MAX_TEXT = 600                       # spoken answers are the short summary, never a whole report
PROMPT = ("Smart Lab portal at GIU: robotics lab, UR5e, FANUC, booking, equipment, door, alerts, temperature, "
          "humidity, consumables bin, soldering station, 3D printer.")


def decode(data: bytes) -> np.ndarray:
    """Any browser recording (webm/opus, ogg, mp4/aac, wav) -> 16 kHz mono float32. PyAV, in memory only."""
    import av
    out = []
    with av.open(io.BytesIO(data)) as c:
        rs = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for f in c.decode(audio=0):
            for g in rs.resample(f):
                out.append(g.to_ndarray().reshape(-1))
        for g in rs.resample(None):
            out.append(g.to_ndarray().reshape(-1))
    if not out:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(out).astype(np.float32) / 32768.0


class Voice:
    def __init__(self, model: str = "base.en", threads: int = 2, voice_path: str = ""):
        self.model_name, self.threads = model, threads
        self.voice_path = voice_path or os.path.join(HERE, "models", "en_US-lessac-medium.onnx")
        self.stt = self.tts = None
        self.stt_slot, self.tts_slot = threading.Semaphore(1), threading.Semaphore(1)
        self.stats = {"transcribed": 0, "spoken": 0, "busy": 0}

    def load(self) -> None:
        from faster_whisper import WhisperModel
        self.stt = WhisperModel(self.model_name, device="cpu", compute_type="int8", cpu_threads=self.threads)
        if os.path.isfile(self.voice_path):
            from piper import PiperVoice
            self.tts = PiperVoice.load(self.voice_path)
        self.transcribe_pcm(np.zeros(16000, dtype=np.float32))      # warm-up: the first real question is fast

    def transcribe_pcm(self, pcm: np.ndarray) -> str:
        segs, _ = self.stt.transcribe(pcm, language="en", beam_size=1, vad_filter=True, initial_prompt=PROMPT,
                                      condition_on_previous_text=False)
        return " ".join(s.text.strip() for s in segs).strip()

    def transcribe(self, data: bytes) -> tuple[int, dict]:
        if len(data) > MAX_AUDIO_BYTES:
            return 413, {"error": "recording too large"}
        if not self.stt_slot.acquire(blocking=False):
            self.stats["busy"] += 1
            return 429, {"error": "busy - one question at a time"}
        try:
            t0 = time.perf_counter()
            try:
                pcm = decode(data)
            except Exception:
                return 422, {"error": "could not read the recording"}
            dur = len(pcm) / 16000
            if dur > MAX_AUDIO_S + 1:
                return 413, {"error": f"question longer than {MAX_AUDIO_S:.0f} s"}
            if dur < 0.3:
                return 200, {"text": "", "audio_s": round(dur, 2), "ms": 0, "model": self.model_name}
            t1 = time.perf_counter()
            text = self.transcribe_pcm(pcm)
            self.stats["transcribed"] += 1
            return 200, {"text": text[:1000], "audio_s": round(dur, 2), "decode_ms": round((t1 - t0) * 1000),
                         "ms": round((time.perf_counter() - t0) * 1000), "model": self.model_name}
        finally:
            self.stt_slot.release()

    def speak(self, text: str) -> tuple[int, bytes | dict]:
        text = " ".join((text or "").split())[:MAX_TEXT]
        if not text:
            return 422, {"error": "no text"}
        if self.tts is None:
            return 503, {"error": "no Piper voice installed - the browser speaks instead"}
        if not self.tts_slot.acquire(blocking=False):
            self.stats["busy"] += 1
            return 429, {"error": "busy"}
        try:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                self.tts.synthesize_wav(text, w)
            self.stats["spoken"] += 1
            return 200, buf.getvalue()
        finally:
            self.tts_slot.release()


def serve(v: Voice, key: str, port: int = 5320) -> None:
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype if isinstance(body, bytes) else "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _auth(self):
            return bool(key) and hmac.compare_digest(self.headers.get("X-Voice-Key", ""), key)

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, {"ok": True, "stt": v.model_name if v.stt else None,
                                        "tts": os.path.basename(v.voice_path) if v.tts else None, **v.stats})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._auth():
                return self._send(401, {"error": "key"})
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_AUDIO_BYTES:
                return self._send(413, {"error": "too large"})
            body = self.rfile.read(n)
            if self.path == "/transcribe":
                return self._send(*v.transcribe(body))
            if self.path == "/speak":
                try:
                    text = json.loads(body or b"{}").get("text", "")
                except ValueError:
                    return self._send(400, {"error": "bad json"})
                code, out = v.speak(str(text))
                return self._send(code, out, "audio/wav")
            self._send(404, {"error": "not found"})

        def log_message(self, *a):
            pass

    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    envf = os.path.join(HERE, "voice.env")
    if os.path.isfile(envf):
        for line in open(envf, encoding="utf-8"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, val = line.strip().split("=", 1)
                os.environ.setdefault(k.strip(), val.strip())
    key = os.environ.get("VOICE_KEY", "")
    if not key:
        raise SystemExit("VOICE_KEY missing (tools/voice/voice.env) - refusing to start without a key")
    v = Voice(os.environ.get("VOICE_STT_MODEL", "base.en"), int(os.environ.get("VOICE_THREADS", "2")))
    t0 = time.time()
    v.load()
    print(f"Voice service: STT {v.model_name} (CPU int8, {v.threads} threads), TTS "
          f"{'Piper ' + os.path.basename(v.voice_path) if v.tts else 'none (browser voice)'} | loaded in "
          f"{time.time() - t0:.1f} s | 127.0.0.1:5320")
    serve(v, key)
