"""Edit + render on Modal (CPU, ffmpeg): real screen recording cut to the narration, burned captions, end card,
loudness-mastered to -14 LUFS. Delivers 16:9 and a 4:5 feed version.

  modal run demo/modal_render.py --voice f-calm
Inputs: demo/clips/demo.mp4, demo/out/tts/<voice>/<line>-t<k>.wav, demo/out/tts/<voice>/picks.json (optional)
Outputs: demo/out/haelt-das-<voice>-16x9.mp4, demo/out/haelt-das-<voice>-4x5.mp4
"""
import json
import pathlib

import modal

app = modal.App("haelt-das-render")
DEMO = pathlib.Path(__file__).resolve().parent
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "fonts-dejavu-core", "fonts-inter")
    .pip_install("soundfile", "numpy")
)

# source ranges in demo/clips/demo.mp4 (seconds, from demo.marks.json) per narration line
CUTS = {
    "hook": (0.0, 5.6),
    "how": (5.6, 51.5),
    "flags": (51.5, 70.9),
    "receipt": (70.9, 81.8),
    "reasons": (81.8, 90.2),
    "reports": (90.2, 108.9),
    "calls": (108.9, 111.5),
}
CAPTIONS = {
    "hook": "I bought a 4.7★ cordless drill. Six weeks later it broke.\nThen I found the same drill under other names.",
    "how": "Hält das? checks any listing like an experienced buyer:\nNebius Token Factory · idealo · web search in 3 languages",
    "flags": "Not sold by any idealo shop · \"21V\" is really an 18V pack\nSame tool under 3 brand names",
    "receipt": "Receipt from the future:\n€0.73 per day for the cheap drill · €0.02 for the Bosch",
    "reasons": "Every reason links to a source you can check.\nHard facts count more than star ratings.",
    "reports": "Failure reports found on the web.\nThe same story in two languages counts once.",
    "calls": "A live Nebius Token Factory call makes the decision.\nEvery model call is shown.",
}
ORDER = ["hook", "how", "flags", "receipt", "reasons", "reports", "calls", "end"]
END_SECONDS = 5.0
DISCLOSURE = ("Narration: AI-generated voice (Qwen3-TTS). App footage: real screen recording of the prototype. "
              "Built at the Agentic Hackathon Berlin, 27 Nov 2026.")


def _ass_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


@app.function(image=image, cpu=16, memory=16384, timeout=1800)
def render(video: bytes, voices: dict, vname: str) -> dict:
    import io
    import subprocess
    import tempfile

    import numpy as np
    import soundfile as sf

    work = pathlib.Path(tempfile.mkdtemp())
    (work / "demo.mp4").write_bytes(video)
    SR = 48000
    lines = {}
    for lid, b in voices.items():
        a, sr = sf.read(io.BytesIO(b), dtype="float32", always_2d=True)
        a = a.mean(axis=1)
        if sr != SR:
            idx = np.linspace(0, len(a) - 1, int(len(a) * SR / sr))
            a = np.interp(idx, np.arange(len(a)), a).astype("float32")
        nz = np.where(np.abs(a) > 0.01)[0]  # trim leading/trailing silence
        if len(nz):
            a = a[max(0, nz[0] - 1200): nz[-1] + 2400]
        lines[lid] = a

    # timeline: each scene lasts its voice line + breathing room; footage speed adapts to fit
    segs, t, audio = [], 0.0, []
    for lid in ORDER:
        vdur = len(lines[lid]) / SR if lid in lines else 0
        dur = (vdur + 0.9) if lid != "end" else max(END_SECONDS, vdur + 1.5)
        segs.append({"id": lid, "start": t, "dur": dur})
        if lid in lines:
            audio.append((t + 0.35, lines[lid]))
        t += dur
    total = t
    mix = np.zeros(int(total * SR) + SR, dtype="float32")
    for st, a in audio:
        i = int(st * SR)
        mix[i:i + len(a)] += a
    sf.write(work / "voice.wav", mix, SR)

    # video filter graph
    parts, labels = [], []
    for i, s in enumerate(segs):
        if s["id"] == "end":
            continue
        a, b = CUTS[s["id"]]
        speed = (b - a) / s["dur"]
        pad = 0.0
        if speed < 0.6:  # never slow footage below 0.6x; hold the last frame instead
            speed = 0.6
            pad = s["dur"] - (b - a) / speed
        f = f"[0:v]trim=start={a}:end={b},setpts=(PTS-STARTPTS)/{speed:.4f},fps=30"
        if pad > 0:
            f += f",tpad=stop_mode=clone:stop_duration={pad:.3f}"
        f += f",trim=duration={s['dur']:.3f},setpts=PTS-STARTPTS,scale=1920:1080,setsar=1,format=yuv420p[v{i}]"
        parts.append(f)
        labels.append(f"[v{i}]")
    end = segs[-1]
    font_b = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    disc = DISCLOSURE.replace(":", r"\:").replace("'", "")
    parts.append(
        f"color=c=0xf4efe4:s=1920x1080:r=30:d={end['dur']:.3f},"
        f"drawtext=fontfile={font_b}:text='Hält das?':fontsize=150:fontcolor=0x16130f:x=(w-tw)/2:y=330,"
        f"drawtext=fontfile={font}:text='Know what lasts, before you pay.':fontsize=58:fontcolor=0xc8361d:x=(w-tw)/2:y=540,"
        f"drawtext=fontfile={font}:text='Cost per day · clone families · failure reports · live Nebius decision':"
        f"fontsize=34:fontcolor=0x6f675b:x=(w-tw)/2:y=640,"
        f"drawtext=fontfile={font}:text='{disc}':fontsize=22:fontcolor=0x6f675b:x=(w-tw)/2:y=990,"
        f"setsar=1,format=yuv420p[vend]")
    labels.append("[vend]")
    parts.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[vcat]")

    # captions (ASS): bottom box, one per scene
    ass = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "",
           "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
           "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
           "MarginR, MarginV, Encoding",
           "Style: Cap,DejaVu Sans,44,&H00FFFFFF,&H00FFFFFF,&H00000000,&HC0161310,1,0,0,0,100,100,0,0,3,18,0,2,80,80,46,1",
           "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for s in segs:
        if s["id"] in CAPTIONS:
            txt = CAPTIONS[s["id"]].replace("\n", r"\N")
            ass.append(f"Dialogue: 0,{_ass_time(s['start'] + 0.2)},{_ass_time(s['start'] + s['dur'] - 0.1)},Cap,,0,0,0,,{txt}")
    (work / "caps.ass").write_text("\n".join(ass), encoding="utf-8")
    parts.append("[vcat]subtitles=caps.ass[vout]")
    (work / "graph.txt").write_text(";\n".join(parts))

    master = "acompressor=threshold=-20dB:ratio=1.6,loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.8:level=false"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "demo.mp4", "-i", "voice.wav",
                    "-filter_complex_script", "graph.txt", "-map", "[vout]", "-map", "1:a",
                    "-af", master, "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}", "-movflags", "+faststart",
                    "out169.mp4"], cwd=work, check=True)
    # 4:5 feed: the 16:9 film centred on the brand background, title above
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "out169.mp4", "-filter_complex",
                    "color=c=0xf4efe4:s=1080x1350:r=30[bg];[0:v]scale=1080:-2[fg];"
                    f"[bg][fg]overlay=0:(H-h)/2:shortest=1,"
                    f"drawtext=fontfile={font_b}:text='Hält das?':fontsize=84:fontcolor=0x16130f:x=(w-tw)/2:y=150,"
                    f"drawtext=fontfile={font}:text='What a product really costs per day':fontsize=40:"
                    f"fontcolor=0xc8361d:x=(w-tw)/2:y=260[v]",
                    "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "19", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", "out45.mp4"],
                   cwd=work, check=True)
    return {"16x9": (work / "out169.mp4").read_bytes(), "4x5": (work / "out45.mp4").read_bytes(),
            "timeline": json.dumps(segs).encode()}


@app.local_entrypoint()
def main(voice: str = "f-calm"):
    vdir = DEMO / "out" / "tts" / voice
    picks_f = vdir / "picks.json"
    picks = json.loads(picks_f.read_text()) if picks_f.exists() else {}
    voices = {lid: (vdir / f"{lid}-{picks.get(lid, 't0')}.wav").read_bytes() for lid in ORDER}
    res = render.remote((DEMO / "clips" / "demo.mp4").read_bytes(), voices, voice)
    out = DEMO / "out"
    for fmt in ("16x9", "4x5"):
        p = out / f"haelt-das-{voice}-{fmt}.mp4"
        p.write_bytes(res[fmt])
        print("wrote", p)
    (out / f"timeline-{voice}.json").write_bytes(res["timeline"])
