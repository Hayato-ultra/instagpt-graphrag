from faster_whisper import WhisperModel


def transcribe_audio_segments(audio_path: str, model_size: str = "base") -> list[dict]:
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, info = model.transcribe(audio_path, word_timestamps=True)

    results = []
    for segment in segments:
        results.append({
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip(),
        })

    return results
