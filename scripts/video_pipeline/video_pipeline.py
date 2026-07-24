#!/usr/bin/env python3
"""
Video Frame Extraction & OCR Pipeline

Full pipeline:
1. Download videos with short transcripts (< 50 chars)
2. Extract frames at scene changes
3. Remove duplicate/similar frames
4. Extract text from frames using OCR
5. Add to JSON with categorization

Usage:
    python video_pipeline.py
    python video_pipeline.py --limit 5
    python video_pipeline.py --skip-download
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime


SCRIPTS_DIR = Path(__file__).parent


def run_step(script_name: str, args: list = None) -> bool:
    """Run a pipeline step."""
    script_path = SCRIPTS_DIR / script_name
    
    if not script_path.exists():
        print(f"Error: Script not found: {script_path}")
        return False
    
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    print(f"\n{'='*60}")
    print(f"Running: {script_name}")
    print(f"{'='*60}\n")
    
    try:
        result = subprocess.run(cmd, cwd=str(SCRIPTS_DIR))
        return result.returncode == 0
    except Exception as e:
        print(f"Error running {script_name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Video Frame Extraction & OCR Pipeline")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of videos to process (0=all)")
    parser.add_argument("--skip-download", action="store_true", help="Skip video download step")
    parser.add_argument("--skip-extract", action="store_true", help="Skip frame extraction step")
    parser.add_argument("--skip-dedup", action="store_true", help="Skip deduplication step")
    parser.add_argument("--skip-ocr", action="store_true", help="Skip OCR step")
    parser.add_argument("--skip-json", action="store_true", help="Skip JSON processing step")
    parser.add_argument("--threshold", type=float, default=0.4, help="Scene change threshold")
    parser.add_argument("--lang", default="eng", help="OCR language")
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"Video Frame Extraction & OCR Pipeline")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    start_time = datetime.now()
    steps_completed = 0
    steps_failed = 0
    
    # Step 1: Download videos
    if not args.skip_download:
        download_args = []
        if args.limit > 0:
            download_args.extend(["--limit", str(args.limit)])
        
        if run_step("download_videos.py", download_args):
            steps_completed += 1
        else:
            steps_failed += 1
            print("Warning: Download step failed, continuing with existing videos...")
    else:
        print("Skipping download step")
    
    # Step 2: Extract frames
    if not args.skip_extract:
        extract_args = ["--threshold", str(args.threshold)]
        
        if run_step("extract_frames.py", extract_args):
            steps_completed += 1
        else:
            steps_failed += 1
            print("Error: Frame extraction failed")
            return
    else:
        print("Skipping extraction step")
    
    # Step 3: Deduplicate frames
    if not args.skip_dedup:
        if run_step("deduplicate_frames.py"):
            steps_completed += 1
        else:
            steps_failed += 1
            print("Warning: Deduplication failed, using all frames...")
    else:
        print("Skipping deduplication step")
    
    # Step 4: OCR frames
    if not args.skip_ocr:
        ocr_args = ["--lang", args.lang]
        
        if run_step("ocr_frames.py", ocr_args):
            steps_completed += 1
        else:
            steps_failed += 1
            print("Error: OCR failed")
            return
    else:
        print("Skipping OCR step")
    
    # Step 5: Process to JSON
    if not args.skip_json:
        if run_step("process_ocr_to_json.py"):
            steps_completed += 1
        else:
            steps_failed += 1
            print("Warning: JSON processing failed")
    else:
        print("Skipping JSON processing step")
    
    # Summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n{'='*60}")
    print(f"Pipeline Complete")
    print(f"Duration: {str(duration).split('.')[0]}")
    print(f"Steps completed: {steps_completed}")
    print(f"Steps failed: {steps_failed}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
