from typing import List, Dict, Any
from datetime import datetime, UTC
from pathlib import Path
from collections import defaultdict

from src.config.models import CategorizedItem, ProcessingResult
from loguru import logger


class MarkdownGenerator:
    def generate(
        self,
        items: List[CategorizedItem],
        source_url: str = "",
        steps: List[str] = None,
        carousel_data: List[dict] = None,
    ) -> str:
        """Generate markdown output from categorized items."""
        if not items:
            return "# No Content Extracted\n\nNo entities were found in the source."
        
        md = []
        md.append(f"# Knowledge Extract: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        md.append("")
        
        if source_url:
            md.append(f"**Source:** [{source_url}]({source_url})")
            md.append("")
        
        # Step-by-step guide (if available)
        if steps:
            # Generate topic from main entities
            if items:
                main_entities = [item.entity.name for item in items[:3]]
                if len(main_entities) == 1:
                    topic = f"Using {main_entities[0]}"
                elif len(main_entities) == 2:
                    topic = f"Using {main_entities[0]} and {main_entities[1]}"
                else:
                    topic = f"Using {', '.join(main_entities[:-1])}, and {main_entities[-1]}"
            else:
                topic = "Key Steps"
            
            md.append(f"## Step-by-Step Guide: {topic}")
            md.append("")
            for i, step in enumerate(steps, 1):
                md.append(f"{i}. {step}")
            md.append("")
        
        # Single overall summary
        md.append("## Summary")
        md.append("")
        summary_parts = []
        seen_summaries = set()
        for item in items:
            if item.summary:
                # Skip template text summaries
                template_patterns = [
                    "EntityType.", "in the source content", "mentioned in the source",
                    "is a EntityType", "is a tool in", "is a framework in",
                ]
                is_template = any(p in item.summary.lower() for p in template_patterns)
                if is_template:
                    continue
                # Deduplicate similar summaries (check first 80 chars)
                summary_key = item.summary[:80].lower().strip()
                if summary_key not in seen_summaries:
                    seen_summaries.add(summary_key)
                    summary_parts.append(item.summary)
        if summary_parts:
            # Take only unique summaries, max 3 sentences
            unique_summaries = list(dict.fromkeys(summary_parts))[:3]
            md.append(" ".join(unique_summaries))
        else:
            md.append(f"Extracted {len(items)} items from the source.")
        md.append("")
        
        md.append(f"**Items Found:** {len(items)}")
        md.append("")

        # Carousel breakdown (if available)
        if carousel_data:
            md.append("## Carousel Breakdown")
            md.append("")
            for img in carousel_data:
                img_num = img.get("image_number", "?")
                category = img.get("category", "other")
                entities = img.get("entities", [])
                summary = img.get("summary", "")
                relation = img.get("relation_to_previous", "")
                entities_str = ", ".join(entities) if entities else "none"
                md.append(f"### Image {img_num}: {category.title()}")
                md.append(f"**Entities:** {entities_str}")
                md.append(f"{summary}")
                if relation:
                    md.append(f"**Relation:** {relation}")
                md.append("")
        
        # Group by primary topic
        by_topic = self._group_by_topic(items)
        
        for topic, topic_items in sorted(by_topic.items()):
            md.append(f"## {topic.value.replace('_', ' ').title()}")
            md.append("")
            
            for item in topic_items:
                md.append(self._render_item(item, source_url))
                md.append("---")
                md.append("")
        
        # Add index
        md.append("## Index")
        md.append("")
        for topic, topic_items in sorted(by_topic.items()):
            md.append(f"### {topic.value.replace('_', ' ').title()}")
            for item in topic_items:
                md.append(f"- [{item.entity.name}](#{self._slugify(item.entity.name)}) (`{item.entity.type.value}`)")
            md.append("")
        
        return "\n".join(md)
    
    def _group_by_topic(self, items: List[CategorizedItem]) -> Dict[Any, List[CategorizedItem]]:
        grouped = {}
        for item in items:
            topic = item.primary_topic
            if topic not in grouped:
                grouped[topic] = []
            grouped[topic].append(item)
        return grouped
    
    def _group_by_subtopic(self, items: List[CategorizedItem]) -> Dict[str, List[CategorizedItem]]:
        grouped = defaultdict(list)
        for item in items:
            sub = item.sub_topics[0] if item.sub_topics else "general"
            grouped[sub].append(item)
        return grouped
    
    def _render_item(self, item: CategorizedItem, source_url: str = "") -> str:
        lines = []
        
        # Header with anchor
        anchor = self._slugify(item.entity.name)
        lines.append(f"#### {item.entity.name} {{#{anchor}}}")
        lines.append("")
        
        # Badges
        badges = [
            f"`{item.entity.type.value}`",
            f"`{item.content_type.value}`",
            f"Confidence: {item.topic_confidence:.0%}"
        ]
        lines.append(" | ".join(badges))
        lines.append("")
        
        # Description
        if item.entity.description:
            lines.append(f"**Description:** {item.entity.description[:500]}")
            lines.append("")
        
        # Key points
        if item.key_points:
            lines.append("**Key Points:**")
            for point in item.key_points:
                lines.append(f"- {point}")
            lines.append("")
        
        # Web references (website links spoken in video)
        if item.entity.web_info:
            lines.append("**Website:**")
            seen_urls = set()
            for ref in item.entity.web_info[:5]:  # Show up to 5 URLs
                url = ref.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    title = ref.get("title", url)
                    lines.append(f"- [{title}]({url})")
            lines.append("")
        
        # Tags
        if item.tags:
            tags_str = ", ".join(f"`{tag}`" for tag in item.tags[:10])
            lines.append(f"**Tags:** {tags_str}")
            lines.append("")
        
        # Don't add source link at end of each entity section - it's redundant
        # The source is already at the top of the file
        
        return "\n".join(lines)
    
    def _slugify(self, text: str) -> str:
        import re
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s-]+", "-", text)
        return text.strip("-")
    
    def save(self, content: str, output_dir: str, filename: str = None) -> Path:
        """Save markdown to file."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"extract_{timestamp}.md"
        
        filepath = output_path / filename
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Saved markdown to {filepath}")
        return filepath


class JSONGenerator:
    def generate(self, items: List[CategorizedItem], source_url: str = "", steps: List[str] = None) -> Dict[str, Any]:
        """Generate JSON output from categorized items."""
        # Collect all unique URLs from all items
        all_urls = []
        seen_urls = set()
        for item in items:
            if item.entity.web_info:
                for ref in item.entity.web_info:
                    url = ref.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_urls.append({
                            "url": url,
                            "title": ref.get("title", url),
                            "entity": item.entity.name
                        })
        
        return {
            "metadata": {
                "generated_at": datetime.now(UTC).isoformat(),
                "source_url": source_url,
                "total_items": len(items),
                "topics": list(set(item.primary_topic.value for item in items)),
                "content_types": list(set(item.content_type.value for item in items)),
                "entity_types": list(set(item.entity.type.value for item in items)),
                "has_steps": bool(steps),
                "steps_count": len(steps) if steps else 0,
                "websites_found": len(all_urls)
            },
            "steps": steps or [],
            "websites": all_urls,
            "items": [self._serialize_item(item) for item in items]
        }
    
    def _serialize_item(self, item: CategorizedItem) -> Dict[str, Any]:
        return {
            "id": item.entity.name.lower().replace(" ", "-"),
            "name": item.entity.name,
            "type": item.entity.type.value,
            "topic": item.primary_topic.value,
            "topic_confidence": item.topic_confidence,
            "sub_topics": item.sub_topics,
            "content_type": item.content_type.value,
            "type_confidence": item.type_confidence,
            "description": item.entity.description,
            "summary": item.summary,
            "key_points": item.key_points,
            "web_info": item.entity.web_info,
            "similar_tools": item.entity.similar_tools,
            "tags": item.tags,
            "confidence": item.entity.confidence,
            "source_url": item.entity.source_url,
            "source_chunk_id": item.entity.source_chunk_id,
            "categorized_at": item.categorized_at.isoformat()
        }
    
    def save(self, data: Dict[str, Any], output_dir: str, filename: str = None) -> Path:
        """Save JSON to file."""
        import orjson
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"extract_{timestamp}.json"
        
        filepath = output_path / filename
        filepath.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
        logger.info(f"Saved JSON to {filepath}")
        return filepath


def generate_outputs(
    items: List[CategorizedItem],
    source_url: str,
    output_dir: str,
    steps: List[str] = None,
    carousel_data: List[dict] = None,
) -> tuple[Path, Path]:
    """Generate both markdown and JSON outputs."""
    md_gen = MarkdownGenerator()
    json_gen = JSONGenerator()
    
    md_content = md_gen.generate(items, source_url, steps=steps, carousel_data=carousel_data)
    json_data = json_gen.generate(items, source_url, steps=steps)
    
    # Extract Instagram reel/post ID from URL for filename
    import re
    ig_match = re.search(r'instagram\.com/(?:reels?|p|tv)/([A-Za-z0-9_-]+)', source_url)
    if ig_match:
        ig_id = ig_match.group(1)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{timestamp}_{ig_id}"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"extract_{timestamp}"
    
    md_path = md_gen.save(md_content, output_dir, f"{base_name}.md")
    json_path = json_gen.save(json_data, output_dir, f"{base_name}.json")
    
    return md_path, json_path