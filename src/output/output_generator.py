from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from src.config.models import CategorizedItem, ProcessingResult
from loguru import logger


class MarkdownGenerator:
    def generate(self, items: List[CategorizedItem], source_url: str = "") -> str:
        """Generate markdown output from categorized items."""
        if not items:
            return "# No Content Extracted\n\nNo entities were found in the source."
        
        md = []
        md.append(f"# Knowledge Extract: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        md.append("")
        
        if source_url:
            md.append(f"**Source:** [{source_url}]({source_url})")
            md.append("")
        
        md.append(f"**Items Found:** {len(items)}")
        md.append("")
        
        # Group by primary topic
        by_topic = self._group_by_topic(items)
        
        for topic, topic_items in sorted(by_topic.items()):
            md.append(f"## {topic.value.replace('_', ' ').title()}")
            md.append("")
            
            # Group by sub-topic
            by_subtopic = self._group_by_subtopic(topic_items)
            
            for subtopic, sub_items in sorted(by_subtopic.items()):
                if subtopic:
                    md.append(f"### {subtopic.replace('-', ' ').title()}")
                    md.append("")
                
                for item in sub_items:
                    md.append(self._render_item(item))
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
    
    def _render_item(self, item: CategorizedItem) -> str:
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
        
        # Summary
        if item.summary:
            lines.append(f"**Summary:** {item.summary}")
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
        
        # Similar tools
        if item.entity.similar_tools:
            lines.append("**Similar Tools / Alternatives:**")
            for tool in item.entity.similar_tools[:5]:
                name = tool.get("name", "Unknown")
                desc = tool.get("description", "")[:100]
                url = tool.get("url", "")
                if url:
                    lines.append(f"- [{name}]({url}): {desc}")
                else:
                    lines.append(f"- {name}: {desc}")
            lines.append("")
        
        # Web references
        if item.entity.web_info:
            lines.append("**References:**")
            seen_urls = set()
            for ref in item.entity.web_info[:5]:
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
    def generate(self, items: List[CategorizedItem], source_url: str = "") -> Dict[str, Any]:
        """Generate JSON output from categorized items."""
        return {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "source_url": source_url,
                "total_items": len(items),
                "topics": list(set(item.primary_topic.value for item in items)),
                "content_types": list(set(item.content_type.value for item in items)),
                "entity_types": list(set(item.entity.type.value for item in items))
            },
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
    output_dir: str
) -> tuple[Path, Path]:
    """Generate both markdown and JSON outputs."""
    md_gen = MarkdownGenerator()
    json_gen = JSONGenerator()
    
    md_content = md_gen.generate(items, source_url)
    json_data = json_gen.generate(items, source_url)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"extract_{timestamp}"
    
    md_path = md_gen.save(md_content, output_dir, f"{base_name}.md")
    json_path = json_gen.save(json_data, output_dir, f"{base_name}.json")
    
    return md_path, json_path