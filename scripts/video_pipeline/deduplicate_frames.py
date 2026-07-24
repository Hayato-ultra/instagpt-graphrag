#!/usr/bin/env python3
"""
Remove duplicate and similar frames by comparing colors.

Usage:
    python deduplicate_frames.py
    python deduplicate_frames.py --hash-size 16
    python deduplicate_frames.py --threshold 10
"""

import argparse
import imagehash
from PIL import Image
from pathlib import Path


def calculate_color_histogram(img_path: Path) -> list:
    """Calculate color histogram for an image."""
    img = Image.open(img_path).convert("RGB")
    histogram = img.histogram()
    
    # Normalize
    total = sum(histogram)
    if total > 0:
        histogram = [h / total for h in histogram]
    
    return histogram


def compare_histograms(hist1: list, hist2: list) -> float:
    """Compare two histograms using correlation."""
    if len(hist1) != len(hist2):
        return 0
    
    # Calculate correlation
    n = len(hist1)
    mean1 = sum(hist1) / n
    mean2 = sum(hist2) / n
    
    numerator = sum((h1 - mean1) * (h2 - mean2) for h1, h2 in zip(hist1, hist2))
    denom1 = sum((h1 - mean1) ** 2 for h1 in hist1) ** 0.5
    denom2 = sum((h2 - mean2) ** 2 for h2 in hist2) ** 0.5
    
    if denom1 * denom2 == 0:
        return 0
    
    return numerator / (denom1 * denom2)


def calculate_perceptual_hash(img_path: Path, hash_size: int = 16) -> imagehash.ImageHash:
    """Calculate perceptual hash for an image."""
    img = Image.open(img_path)
    return imagehash.phash(img, hash_size=hash_size)


def is_duplicate(img1_path: Path, img2_path: Path, hash_size: int = 16, threshold: int = 10) -> bool:
    """Check if two images are duplicates or very similar."""
    # Method 1: Perceptual hash
    hash1 = calculate_perceptual_hash(img1_path, hash_size)
    hash2 = calculate_perceptual_hash(img2_path, hash_size)
    hash_diff = hash1 - hash2
    
    if hash_diff <= threshold:
        return True
    
    # Method 2: Color histogram
    hist1 = calculate_color_histogram(img1_path)
    hist2 = calculate_color_histogram(img2_path)
    similarity = compare_histograms(hist1, hist2)
    
    # High similarity (>0.95) means likely duplicate
    if similarity > 0.95:
        return True
    
    return False


def deduplicate_frames(input_dir: Path, output_dir: Path, hash_size: int = 16, threshold: int = 10):
    """Remove duplicate frames from each video folder."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process each video folder
    video_folders = [d for d in input_dir.iterdir() if d.is_dir()]
    
    if not video_folders:
        # If no subfolders, process all images in input_dir
        video_folders = [input_dir]
    
    total_original = 0
    total_kept = 0
    
    for video_folder in video_folders:
        print(f"\nProcessing: {video_folder.name}")
        
        # Get all image files
        image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
        images = sorted([f for f in video_folder.iterdir() if f.suffix.lower() in image_extensions])
        
        if not images:
            print("  No images found")
            continue
        
        total_original += len(images)
        print(f"  Found {len(images)} frames")
        
        # Create output folder for this video
        if video_folder == input_dir:
            out_folder = output_dir
        else:
            out_folder = output_dir / video_folder.name
            out_folder.mkdir(parents=True, exist_ok=True)
        
        # Keep track of unique frames
        kept_images = []
        
        for img_path in images:
            is_dup = False
            
            # Compare with already kept images
            for kept_img in kept_images:
                if is_duplicate(img_path, kept_img, hash_size, threshold):
                    is_dup = True
                    break
            
            if not is_dup:
                kept_images.append(img_path)
                # Copy unique frame to output
                output_path = out_folder / img_path.name
                img = Image.open(img_path)
                img.save(output_path)
        
        kept_count = len(kept_images)
        removed = len(images) - kept_count
        total_kept += kept_count
        
        print(f"  Kept: {kept_count}, Removed: {removed} duplicates")
    
    return total_original, total_kept


def main():
    parser = argparse.ArgumentParser(description="Remove duplicate frames by color similarity")
    parser.add_argument("--input-dir", type=Path, default=Path("C:\\Users\\ROHIT\\projects\\INSTAGPT\\frames"))
    parser.add_argument("--output-dir", type=Path, default=Path("C:\\Users\\ROHIT\\projects\\INSTAGPT\\frames_deduped"))
    parser.add_argument("--hash-size", type=int, default=16, help="Perceptual hash size (higher=more precise)")
    parser.add_argument("--threshold", type=int, default=10, help="Hash difference threshold (lower=more strict)")
    
    args = parser.parse_args()
    
    if not args.input_dir.exists():
        print(f"Error: Input directory not found: {args.input_dir}")
        return
    
    print(f"Input: {args.input_dir}")
    print(f"Output: {args.output_dir}")
    print(f"Hash size: {args.hash_size}, Threshold: {args.threshold}")
    
    total_original, total_kept = deduplicate_frames(
        args.input_dir, args.output_dir, args.hash_size, args.threshold
    )
    
    removed = total_original - total_kept
    
    print(f"\nSummary:")
    print(f"  Original frames: {total_original}")
    print(f"  Unique frames: {total_kept}")
    print(f"  Removed duplicates: {removed}")
    print(f"  Reduction: {(removed/total_original*100):.1f}%" if total_original > 0 else "")


if __name__ == "__main__":
    main()
