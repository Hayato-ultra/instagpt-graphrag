#!/usr/bin/env python3
"""
Process OCR text files and add to JSON with categorization.

Usage:
    python process_ocr_to_json.py
    python process_ocr_to_json.py --category "content creation"
"""

import argparse
import json
from datetime import datetime
from pathlib import Path


# Category keywords for auto-classification
CATEGORY_KEYWORDS = {
    "app_development": ["android", "ios", "flutter", "react native", "swift", "kotlin", "mobile app"],
    "web_development": ["html", "css", "javascript", "react", "vue", "angular", "website", "frontend", "backend"],
    "ai_agent_upskilling": ["ai", "llm", "gpt", "claude", "agent", "machine learning", "deep learning"],
    "system_performance_enhance": ["docker", "kubernetes", "aws", "azure", "cloud", "server", "devops"],
    "life_lessons": ["mindset", "habit", "productivity", "motivation", "success", "failure"],
    "financial_advice": ["money", "invest", "trading", "stock", "crypto", "income", "profit"],
    "database_technology": ["sql", "mysql", "postgresql", "mongodb", "database", "redis"],
    "productivity": ["tool", "workflow", "automation", "shortcut", "efficiency", "todo"],
    "freelancing": ["client", "freelance", "remote", "upwork", "fiverr", "contract"],
    "marketing": ["seo", "social media", "content", "audience", "brand", "campaign"],
    "education_and_learning": ["tutorial", "course", "learn", "teach", "education", "training"],
    "ai_and_technology": ["tech", "software", "programming", "code", "developer", "coding"],
    "content_creation": ["video", "youtube", "editing", "premiere", "davinci", "after effects", "production"],
}


def classify_text(text: str) -> str:
    """Classify text into a category based on keywords."""
    text_lower = text.lower()
    
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[category] = score
    
    if scores:
        return max(scores, key=scores.get)
    return "other"


def extract_key_info(text: str) -> dict:
    """Extract key information from OCR text."""
    # Simple extraction based on common patterns
    lines = text.split("\n")
    
    # Try to find title (first non-empty line usually)
    title = ""
    for line in lines:
        if line.strip() and len(line.strip()) > 3:
            title = line.strip()
            break
    
    # Find URLs
    import re
    urls = re.findall(r'https?://[^\s<>"]+', text)
    
    # Find tool/software names (common patterns)
    tools = []
    tool_patterns = [
        r'(?:using|use|try|download)\s+([A-Z][a-zA-Z]+)',
        r'([A-Z][a-zA-Z]+)\s+(?:tool|software|app)',
    ]
    for pattern in tool_patterns:
        matches = re.findall(pattern, text)
        tools.extend(matches)
    
    return {
        "title": title,
        "urls": urls[:5],  # Limit to 5 URLs
        "tools": list(set(tools))[:5],  # Limit to 5 unique tools
        "word_count": len(text.split()),
        "line_count": len(lines)
    }


def process_ocr_texts(input_dir: Path, output_file: Path, category: str = None):
    """Process all OCR text files and create JSON entries."""
    entries = []
    
    # Process each video folder
    video_folders = [d for d in input_dir.iterdir() if d.is_dir()]
    
    if not video_folders:
        video_folders = [input_dir]
    
    for video_folder in video_folders:
        print(f"\nProcessing: {video_folder.name}")
        
        # Get all text files
        txt_files = sorted([f for f in video_folder.glob("*.txt") if not f.name.endswith("_combined.txt")])
        
        if not txt_files:
            print("  No text files found")
            continue
        
        # Combine all text from this video
        combined_text = []
        for txt_file in txt_files:
            try:
                text = txt_file.read_text(encoding="utf-8")
                if text.strip():
                    combined_text.append(text)
            except Exception:
                continue
        
        if not combined_text:
            continue
        
        full_text = "\n\n".join(combined_text)
        
        # Extract information
        info = extract_key_info(full_text)
        
        # Classify
        detected_category = category or classify_text(full_text)
        
        # Create entry
        entry = {
            "video_id": video_folder.name,
            "youtube_url": f"https://www.youtube.com/watch?v={video_folder.name}",
            "theme": info["title"][:100] if info["title"] else video_folder.name,
            "topic": info["title"],
            "category": detected_category,
            "extracted_text_preview": full_text[:500],  # First 500 chars
            "word_count": info["word_count"],
            "urls_found": info["urls"],
            "tools_mentioned": info["tools"],
            "source": "ocr_frame_extraction",
            "processed_at": datetime.now().strftime("%Y-%m-%d")
        }
        
        entries.append(entry)
        print(f"  Category: {detected_category}, Words: {info['word_count']}")
    
    # Save to JSON
    if entries:
        # Load existing data if file exists
        existing_data = []
        if output_file.exists():
            try:
                existing_data = json.loads(output_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        
        # Add new entries (skip duplicates)
        existing_ids = {e.get("video_id") for e in existing_data}
        new_entries = [e for e in entries if e["video_id"] not in existing_ids]
        
        all_data = existing_data + new_entries
        
        output_file.write_text(
            json.dumps(all_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        print(f"\nSaved {len(new_entries)} new entries to {output_file}")
        print(f"Total entries: {len(all_data)}")
    
    return entries


def main():
    parser = argparse.ArgumentParser(description="Process OCR texts and add to JSON")
    parser.add_argument("--input-dir", type=Path, default=Path("C:\\Users\\ROHIT\\projects\\INSTAGPT\\ocr_texts"))
    parser.add_argument("--output-file", type=Path, default=Path("C:\\Users\\ROHIT\\projects\\INSTAGPT\\transcripts\\analyzed\\ocr_extracted.json"))
    parser.add_argument("--category", help="Force specific category (skip auto-detection)")
    
    args = parser.parse_args()
    
    if not args.input_dir.exists():
        print(f"Error: Input directory not found: {args.input_dir}")
        return
    
    print(f"Input: {args.input_dir}")
    print(f"Output: {args.output_file}")
    
    entries = process_ocr_texts(args.input_dir, args.output_file, args.category)
    
    print(f"\nSummary:")
    print(f"  Videos processed: {len(entries)}")
    
    # Category breakdown
    categories = {}
    for entry in entries:
        cat = entry.get("category", "other")
        categories[cat] = categories.get(cat, 0) + 1
    
    if categories:
        print(f"\nCategory breakdown:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
