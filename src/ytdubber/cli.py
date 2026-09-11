from __future__ import annotations
import argparse
import sys
from . import __version__
from .pipeline import run_pipeline
from .preflight import run_preflight
from .models import PROFILES


def main(argv=None):
    p = argparse.ArgumentParser(description="Local YouTube -> Spanish dubbing for Windows/NVIDIA")
    p.add_argument("--version", action="version", version=f"ytdubber {__version__}")
    sub = p.add_subparsers(dest="cmd")
    pre = sub.add_parser("doctor", help="check installation")
    pre.add_argument("--model", default="qwen3:8b")
    dub = sub.add_parser("dub", help="dub a YouTube URL or local video")
    dub.add_argument("source")
    dub.add_argument("--profile", choices=PROFILES.keys(), default="balanced")
    dub.add_argument("--source-lang", default=None, help="e.g. en; omit for auto-detect")
    dub.add_argument("--voice-ref", default=None, help="optional clean voice WAV")
    dub.add_argument("--original-speech-level", type=float, default=0.12,
                     help="original soundtrack gain under dubbed speech, 0.0..1.0")
    dub.add_argument("--tts-takes", type=int, default=None,
                     help="override the profile's TTS takes per block; 1 disables retakes")
    dub.add_argument("--max-speedup", type=float, default=None,
                     help="override the profile's speed-up cap, e.g. 1.30")
    web = sub.add_parser("web", help="local control panel in the browser")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    args = p.parse_args(argv)
    if args.cmd == "doctor":
        return 0 if run_preflight(args.model) else 1
    if args.cmd == "dub":
        run_pipeline(args.source, args.profile, args.source_lang, args.voice_ref,
                     args.original_speech_level, tts_takes=args.tts_takes,
                     max_speedup=args.max_speedup)
        return 0
    if args.cmd == "web":
        from .webapp import serve
        if not args.no_browser:
            import threading
            import webbrowser
            threading.Timer(1.2, webbrowser.open, (f"http://{args.host}:{args.port}",)).start()
        serve(args.host, args.port)
        return 0
    p.print_help(); return 2

if __name__ == "__main__":
    raise SystemExit(main())
