"""Narration on Modal: Qwen3-TTS "design then clone" (Apache-2.0), two voices in parallel, 2 takes per line,
each take transcribed with faster-whisper (CPU int8) so we can check words and the product name.

  modal run demo/modal_tts.py
Outputs: demo/out/tts/<voice>/<line>-t<k>.wav + demo/out/tts/<voice>/transcripts.json
"""
import json
import pathlib
import time

import modal

app = modal.App("haelt-das-tts")
hf_cache = modal.Volume.from_name("astrolab-hf-cache", create_if_missing=True)
OUT = pathlib.Path(__file__).resolve().parent / "out" / "tts"
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1", "git", "sox")
    .pip_install("qwen-tts", "soundfile", "huggingface_hub[hf_transfer]", "faster-whisper")
    .env({"HF_HOME": "/cache/hf", "HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

# "Helt das" is the phonetic spelling of "Hält das" for an English voice; captions show "Hält das?".
LINES = [
    {"id": "hook", "text": "I once bought a cordless drill with four point seven stars. Six weeks later, it broke. "
                           "Then I found the same drill, sold under other names."},
    {"id": "how", "text": "So we built an agent for exactly this. You paste a listing, and an agent checks it the way an experienced "
                          "buyer would. It reads the listing with a model on Nebius Token Factory, looks it up on "
                          "idealo, and searches the web in three languages."},
    {"id": "flags", "text": "No idealo shop sells this drill. The twenty-one volts on the box are really an eighteen "
                            "volt pack. And the same tool shows up under three brand names."},
    {"id": "receipt", "text": "Then it prints a receipt from the future. Spread over the life you can really expect, "
                              "the cheap drill costs seventy-three cents a day. The Bosch costs two cents."},
    {"id": "reasons", "text": "Every reason links to a source you can check, and hard facts count for more than "
                              "star ratings."},
    {"id": "reports", "text": "It finds the people whose drill broke, and the same story told in two languages is "
                              "counted only once."},
    {"id": "calls", "text": "A live call on Nebius Token Factory makes the decision, and every model call is shown."},
    {"id": "end", "text": "Know what lasts, before you pay."},
]
VOICES = {
    "f-calm": "A warm, calm female presenter in her late thirties. Grounded and friendly, a gentle smile in her voice, "
              "unhurried conversational pace, clear neutral English accent. Never shouting.",
    "m-calm": "A warm, calm male narrator in his forties. Grounded baritone, friendly and assured, unhurried "
              "conversational pace, clear neutral English accent. Never shouting.",
}
TAKES = 2


@app.function(image=image, gpu="L40S", volumes={"/cache": hf_cache}, timeout=2400)
def voice(name: str, instruct: str, ref_wav: bytes = b"", only: str = "") -> dict:
    import io
    import tempfile

    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    ref_text = LINES[0]["text"]
    if ref_wav:
        ref = io.BytesIO(ref_wav)
    else:
        design = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", device_map="cuda:0",
                                               dtype=torch.bfloat16, attn_implementation="sdpa")
        torch.manual_seed(1)
        wavs, sr = design.generate_voice_design(text=ref_text, language="English", instruct=instruct)
        ref = io.BytesIO(); sf.write(ref, wavs[0], sr, format="WAV")
        del design
        torch.cuda.empty_cache()

    base = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base", device_map="cuda:0",
                                         dtype=torch.bfloat16, attn_implementation="sdpa")
    with tempfile.NamedTemporaryFile(suffix=".wav") as fh:
        fh.write(ref.getvalue()); fh.flush()
        prompt = base.create_voice_clone_prompt(ref_audio=fh.name, ref_text=ref_text, x_vector_only_mode=False)
    out = {"ref": ref.getvalue()}
    for ln in [l for l in LINES if not only or l["id"] in only.split(",")]:
        for k in range(TAKES):
            torch.manual_seed(100 + k)
            w, sr = base.generate_voice_clone(text=ln["text"], language="English", voice_clone_prompt=prompt)
            buf = io.BytesIO(); sf.write(buf, w[0], sr, format="WAV")
            out[f"{ln['id']}-t{k}"] = buf.getvalue()
    hf_cache.commit()

    from faster_whisper import WhisperModel
    asr = WhisperModel("small.en", device="cpu", compute_type="int8", download_root="/cache/whisper")
    transcripts = {}
    for key, b in out.items():
        with tempfile.NamedTemporaryFile(suffix=".wav") as fh:
            fh.write(b); fh.flush()
            segs, info = asr.transcribe(fh.name, language="en")
            transcripts[key] = {"text": " ".join(s.text.strip() for s in segs), "dur": round(info.duration, 2)}
    out["transcripts"] = json.dumps(transcripts).encode()
    return out


@app.local_entrypoint()
def main(voices: str = "", only: str = ""):
    t0 = time.time()
    chosen = {v: i for v, i in VOICES.items() if not voices or v in voices.split(",")}
    handles = {}
    for v, instr in chosen.items():
        ref = OUT / v / "ref.wav"
        handles[v] = voice.spawn(v, instr, ref.read_bytes() if ref.exists() else b"", only)
    for v, h in handles.items():
        try:
            res = h.get()
        except Exception as e:  # noqa: BLE001 - keep the other voice
            print("FAILED", v, repr(e))
            continue
        dest = OUT / v
        dest.mkdir(parents=True, exist_ok=True)
        for k, b in res.items():
            if k == "ref" and (dest / "ref.wav").exists():
                continue
            if k == "transcripts":
                old = json.loads((dest / "transcripts.json").read_text()) if (dest / "transcripts.json").exists() else {}
                old.update(json.loads(b))
                (dest / "transcripts.json").write_text(json.dumps(old, indent=1))
                continue
            (dest / f"{k}.wav").write_bytes(b)
        print(v, "->", dest)
    print({"wall_s": round(time.time() - t0)})
