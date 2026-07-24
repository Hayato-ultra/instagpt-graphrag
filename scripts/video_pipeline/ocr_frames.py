#!/usr/bin/env python3
"""
Extract text from frames using OCR (Tesseract).

Usage:
    python ocr_frames.py
    python ocr_frames.py --lang eng+hin
    python ocr_frames.py --min-confidence 50
"""

import argparse
import sys
from pathlib import Path

try:
    import pytesseract
    from PIL import Image
except ImportError:
    print("Missing dependencies. Install them:")
    print("  pip install pytesseract Pillow")
    sys.exit(1)


def extract_text_from_image(image_path: Path, lang: str = "eng", min_confidence: int = 0) -> dict:
    """Extract text from a single image with confidence scores."""
    try:
        img = Image.open(image_path)
        
        # Get detailed data with confidence
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
        
        # Filter by confidence and combine text
        texts = []
        total_confidence = 0
        word_count = 0
        
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            conf = int(data["conf"][i])
            
            if text and conf >= min_confidence:
                texts.append(text)
                total_confidence += conf
                word_count += 1
        
        full_text = " ".join(texts)
        avg_confidence = total_confidence / word_count if word_count > 0 else 0
        
        return {
            "text": full_text,
            "word_count": word_count,
            "avg_confidence": avg_confidence
        }
    except Exception as e:
        return {
            "text": "",
            "word_count": 0,
            "avg_confidence": 0,
            "error": str(e)
        }


def process_frames(input_dir: Path, output_dir: Path, lang: str = "eng", min_confidence: int = 0):
    """Process all frames and extract text."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process each video folder
    video_folders = [d for d in input_dir.iterdir() if d.is_dir()]
    
    if not video_folders:
        video_folders = [input_dir]
    
    total_images = 0
    total_with_text = 0
    total_words = 0
    
    for video_folder in video_folders:
        print(f"\nProcessing: {video_folder.name}")
        
        # Get all image files
        image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
        images = sorted([f for f in video_folder.iterdir() if f.suffix.lower() in image_extensions])
        
        if not images:
            print("  No images found")
            continue
        
        print(f"  Found {len(images)} frames")
        
        # Create output folder for this video
        if video_folder == input_dir:
            out_folder = output_dir
        else:
            out_folder = output_dir / video_folder.name
            out_folder.mkdir(parents=True, exist_ok=True)
        
        # Process each image
        video_text = []
        
        for i, img_path in enumerate(images, 1):
            result = extract_text_from_image(img_path, lang, min_confidence)
            
            if result["text"].strip():
                total_with_text += 1
                total_words += result["word_count"]
                
                # Save text to file
                txt_filename = img_path.stem + ".txt"
                txt_path = out_folder / txt_filename
                txt_path.write_text(result["text"], encoding="utf-8")
                
                video_text.append({
                    "frame": img_path.name,
                    "text": result["text"],
                    "confidence": result["avg_confidence"]
                })
            
            # Progress indicator
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(images)}", end="\r")
        
        # Save combined text for video
        if video_text:
            combined_path = out_folder / f"{video_folder.name}_combined.txt"
            with open(combined_path, "w", encoding="utf-8") as f:
                for item in video_text:
                    f.write(f"--- {item['frame']} (confidence: {item['confidence']:.0f}%) ---\n")
                    f.write(item["text"] + "\n\n")
        
        print(f"  Frames with text: {sum(1 for t in video_text if t['text'].strip())}/{len(images)}")
        total_images += len(images)
    
    return total_images, total_with_text, total_words


def main():
    parser = argparse.ArgumentParser(description="Extract text from frames using OCR")
    parser.add_argument("--input-dir", type=Path, default=Path("C:\\Users\\ROHIT\\projects\\INSTAGPT\\frames_deduped"))
    parser.add_argument("--output-dir", type=Path, default=Path("C:\\Users\\ROHIT\\projects\\INSTAGPT\\ocr_texts"))
    parser.add_argument("--lang", default="eng", help="OCR language(s) (e.g., eng+hin)")
    parser.add_argument("--min-confidence", type=int, default=30, help="Minimum confidence threshold (0-100)")
    
    args = parser.parse_args()
    
    if not args.input_dir.exists():
        print(f"Error: Input directory not found: {args.input_dir}")
        return
    
    print(f"Input: {args.input_dir}")
    print(f"Output: {args.output_dir}")
    print(f"Language: {args.lang}, Min confidence: {args.min_confidence}")
    
    total_images, total_with_text, total_words = process_frames(
        args.input_dir, args.output_dir, args.lang, args.min_confidence
    )
    
    print(f"\nSummary:")
    print(f"  Total frames processed: {total_images}")
    print(f"  Frames with text: {total_with_text}")
    print(f"  Total words extracted: {total_words}")
    print(f"  Output: {args.output_dir}")


if __name__ == "__main__":
    main()
