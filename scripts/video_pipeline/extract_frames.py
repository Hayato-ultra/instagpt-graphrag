#!/usr/bin/env python3
"""
Extract frames from videos at scene changes.

Usage:
    python extract_frames.py
    python extract_frames.py --threshold 0.4
    python extract_frames.py --interval 5
"""

import argparse
import cv2
import numpy as np
from pathlib import Path


def calculate_histogram_diff(frame1, frame2) -> float:
    """Calculate difference between two frames using color histograms."""
    # Convert to HSV for better color comparison
    hsv1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2HSV)
    hsv2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2HSV)
    
    # Calculate histograms
    hist1 = cv2.calcHist([hsv1], [0, 1], None, [50, 60], [0, 180, 0, 256])
    hist2 = cv2.calcHist([hsv2], [0, 1], None, [50, 60], [0, 180, 0, 256])
    
    # Normalize histograms
    cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
    cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)
    
    # Compare histograms
    similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
    
    # Return difference (1 - similarity)
    return 1 - similarity


def extract_frames_at_scenes(video_path: Path, output_dir: Path, threshold: float = 0.4, min_interval: float = 1.0):
    """Extract frames when scene changes significantly."""
    cap = cv2.VideoCapture(str(video_path))
    
    if not cap.isOpened():
        print(f"  Error: Cannot open {video_path}")
        return 0
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    
    print(f"  FPS: {fps:.1f}, Duration: {duration:.1f}s, Total frames: {total_frames}")
    
    # Create output directory for this video
    video_output = output_dir / video_path.stem
    video_output.mkdir(parents=True, exist_ok=True)
    
    extracted = 0
    last_extract_time = -min_interval
    
    prev_frame = None
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        current_time = frame_count / fps
        
        if prev_frame is None:
            # First frame - always extract
            frame_path = video_output / f"frame_{extracted:04d}_{current_time:.1f}s.png"
            cv2.imwrite(str(frame_path), frame)
            extracted += 1
            last_extract_time = current_time
        else:
            # Check for scene change
            diff = calculate_histogram_diff(prev_frame, frame)
            
            # Extract if scene changed and enough time has passed
            if diff > threshold and (current_time - last_extract_time) >= min_interval:
                frame_path = video_output / f"frame_{extracted:04d}_{current_time:.1f}s.png"
                cv2.imwrite(str(frame_path), frame)
                extracted += 1
                last_extract_time = current_time
        
        prev_frame = frame.copy()
        frame_count += 1
        
        # Progress indicator
        if frame_count % 100 == 0:
            progress = (frame_count / total_frames) * 100 if total_frames > 0 else 0
            print(f"  Progress: {progress:.1f}% ({extracted} frames extracted)", end="\r")
    
    cap.release()
    print(f"  Extracted {extracted} frames")
    return extracted


def extract_frames_at_interval(video_path: Path, output_dir: Path, interval: float = 5.0):
    """Extract frames at fixed time intervals."""
    cap = cv2.VideoCapture(str(video_path))
    
    if not cap.isOpened():
        print(f"  Error: Cannot open {video_path}")
        return 0
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    
    print(f"  FPS: {fps:.1f}, Duration: {duration:.1f}s")
    
    # Create output directory for this video
    video_output = output_dir / video_path.stem
    video_output.mkdir(parents=True, exist_ok=True)
    
    extracted = 0
    current_time = 0
    
    while current_time < duration:
        frame_number = int(current_time * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        
        ret, frame = cap.read()
        if ret:
            frame_path = video_output / f"frame_{extracted:04d}_{current_time:.1f}s.png"
            cv2.imwrite(str(frame_path), frame)
            extracted += 1
        
        current_time += interval
    
    cap.release()
    print(f"  Extracted {extracted} frames")
    return extracted


def main():
    parser = argparse.ArgumentParser(description="Extract frames from videos at scene changes")
    parser.add_argument("--input-dir", type=Path, default=Path("C:\\Users\\ROHIT\\projects\\INSTAGPT\\videos"))
    parser.add_argument("--output-dir", type=Path, default=Path("C:\\Users\\ROHIT\\projects\\INSTAGPT\\frames"))
    parser.add_argument("--threshold", type=float, default=0.4, help="Scene change threshold (0-1, higher=more sensitive)")
    parser.add_argument("--interval", type=float, default=0, help="Extract at fixed interval (seconds, 0=scene detection)")
    parser.add_argument("--min-interval", type=float, default=1.0, help="Minimum time between scene change extractions")
    
    args = parser.parse_args()
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find video files
    video_extensions = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
    videos = [f for f in args.input_dir.iterdir() if f.suffix.lower() in video_extensions]
    
    if not videos:
        print(f"No video files found in {args.input_dir}")
        return
    
    print(f"Found {len(videos)} videos\n")
    
    total_frames = 0
    
    for i, video in enumerate(videos, 1):
        print(f"[{i}/{len(videos)}] Processing {video.name}...")
        
        if args.interval > 0:
            frames = extract_frames_at_interval(video, args.output_dir, args.interval)
        else:
            frames = extract_frames_at_scenes(video, args.output_dir, args.threshold, args.min_interval)
        
        total_frames += frames
        print()
    
    print(f"Summary:")
    print(f"  Videos processed: {len(videos)}")
    print(f"  Total frames extracted: {total_frames}")
    print(f"  Output: {args.output_dir}")


if __name__ == "__main__":
    main()
