import os
import subprocess
import yt_dlp
from dotenv import load_dotenv

load_dotenv()

COOKIES_PATH = os.getenv("COOKIES_PATH", r"C:\Users\ROHIT\projects\INSTAGPT\cookies.txt")


def download_reel(url: str, output_dir: str = "temp_media") -> str:
    os.makedirs(output_dir, exist_ok=True)
    output_template = os.path.join(output_dir, "reel.%(ext)s")

    ydl_opts = {
        "format": "best[ext=mp4]",
        "outtmpl": output_template,
        "cookiesfrombrowser": None,
        "cookiefile": COOKIES_PATH,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    video_path = filename
    if not os.path.exists(video_path):
        for f in os.listdir(output_dir):
            if f.startswith("reel") and f.endswith(".mp4"):
                video_path = os.path.join(output_dir, f)
                break

    return video_path


def extract_audio(video_path: str, output_dir: str = "temp_media") -> str:
    os.makedirs(output_dir, exist_ok=True)
    audio_path = os.path.join(output_dir, "audio.wav")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-y",
        audio_path,
    ]

    subprocess.run(cmd, check=True, capture_output=True)
    return audio_path
