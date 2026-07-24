#!/usr/bin/env python3
"""
Download YouTube videos for short transcripts (< 50 chars).

Usage:
    python download_videos.py
    python download_videos.py --limit 10
    python download_videos.py --force
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_short_video_ids(transcripts_dir: Path, master_dir: Path) -> list:
    """Get video IDs with transcripts < 50 chars."""
    short_ids = []
    
    # Check short_videos.json first
    short_videos_file = master_dir / "short_videos.json"
    if short_videos_file.exists():
        try:
            data = json.loads(short_videos_file.read_text(encoding="utf-8"))
            for item in data:
                short_ids.append(item.get("video_id"))
            print(f"Found {len(short_ids)} videos in short_videos.json")
            return short_ids
        except Exception as e:
            print(f"Error reading short_videos.json: {e}")
    
    # Scan .txt files for short transcripts
    print("Scanning .txt files for short transcripts...")
    for txt_file in transcripts_dir.glob("*.txt"):
        if txt_file.name.lower() in {"summary.txt", "scan_log.txt", "failed.txt", "to_process.txt"}:
            continue
        
        try:
            content = txt_file.read_text(encoding="utf-8", errors="ignore")
            if len(content.strip()) < 50:
                video_id = txt_file.stem
                short_ids.append(video_id)
        except Exception:
            continue
    
    print(f"Found {len(short_ids)} videos with transcripts < 50 chars")
    return short_ids


def download_video(video_id: str, output_dir: Path) -> bool:
    """Download a single YouTube video using yt-dlp."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_path = output_dir / f"{video_id}.%(ext)s"
    
    cmd = [
        "yt-dlp",
        "-f", "best[height<=720]",  # Limit to 720p for faster download
        "--no-playlist",
        "-o", str(output_path),
        "--no-warnings",
        "--quiet",
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return True
        else:
            print(f"  Error: {result.stderr[:100]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  Timeout downloading {video_id}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download YouTube videos for short transcripts")
    parser.add_argument("--transcripts-dir", type=Path, default=Path("C:\\Users\\ROHIT\\projects\\INSTAGPT\\transcripts"))
    parser.add_argument("--master-dir", type=Path, default=Path("C:\\Users\\ROHIT\\projects\\INSTAGPT\\transcripts\\analyzed"))
    parser.add_argument("--output-dir", type=Path, default=Path("C:\\Users\\ROHIT\\projects\\INSTAGPT\\videos"))
    parser.add_argument("--limit", type=int, default=0, help="Limit number of videos to download (0=all)")
    parser.add_argument("--force", action="store_true", help="Re-download even if exists")
    
    args = parser.parse_args()
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get short video IDs
    short_ids = get_short_video_ids(args.transcripts_dir, args.master_dir)
    
    if not short_ids:
        print("No short videos found to download")
        return
    
    # Apply limit
    if args.limit > 0:
        short_ids = short_ids[:args.limit]
        print(f"Limiting to {args.limit} videos")
    
    # Filter out already downloaded
    if not args.force:
        existing = {f.stem for f in args.output_dir.glob("*.*")}
        before = len(short_ids)
        short_ids = [vid for vid in short_ids if vid not in existing]
        print(f"Skipping {before - len(short_ids)} already downloaded")
    
    if not short_ids:
        print("All videos already downloaded")
        return
    
    print(f"\nDownloading {len(short_ids)} videos...")
    
    # Download videos
    downloaded = 0
    failed = 0
    
    for i, video_id in enumerate(short_ids, 1):
        print(f"[{i}/{len(short_ids)}] Downloading {video_id}...")
        
        if download_video(video_id, args.output_dir):
            downloaded += 1
            print(f"  ✓ Downloaded")
        else:
            failed += 1
            print(f"  ✗ Failed")
    
    print(f"\nSummary:")
    print(f"  Downloaded: {downloaded}")
    print(f"  Failed: {failed}")
    print(f"  Output: {args.output_dir}")


if __name__ == "__main__":
    main()
