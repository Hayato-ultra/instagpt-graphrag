import asyncio
import hashlib
import re
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from readability import Document
import trafilatura
from playwright.async_api import async_playwright

from src.config import get_settings
from src.models import (
    ExtractedContent,
    DocumentChunk,
    PipelineStage,
    ProcessingResult,
)
from loguru import logger


settings = get_settings()


class ExtractionStrategy:
    WEBCRAWL = "webcrawl"
    PLAYWRIGHT = "playwright"
    TRAFILATURA = "trafilatura"
    READABILITY = "readability"


class ContentExtractor:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; InstaGPT-GraphRAG/0.1)"}
        )
        self._playwright_browser = None

    async def _get_playwright_browser(self):
        if self._playwright_browser is None:
            playwright = await async_playwright().start()
            self._playwright_browser = await playwright.chromium.launch(
                headless=settings.PLAYWRIGHT_HEADLESS
            )
        return self._playwright_browser

    async def extract(self, url: str) -> ExtractedContent:
        logger.info(f"Extracting content from: {url}")
        
        # Try strategies in order
        strategies = [
            (ExtractionStrategy.TRAFILATURA, self._extract_trafilatura),
            (ExtractionStrategy.READABILITY, self._extract_readability),
            (ExtractionStrategy.WEBCRAWL, self._extract_webcrawl),
            (ExtractionStrategy.PLAYWRIGHT, self._extract_playwright),
        ]
        
        last_error = None
        for strategy_name, strategy_func in strategies:
            try:
                content = await strategy_func(url)
                if content and len(content.raw_text) > 100:
                    logger.success(f"Successfully extracted with {strategy_name}")
                    content.extraction_strategy = strategy_name
                    return content
                else:
                    logger.warning(f"{strategy_name} returned insufficient content")
            except Exception as e:
                last_error = e
                logger.warning(f"{strategy_name} failed: {e}")
                continue
        
        raise RuntimeError(f"All extraction strategies failed. Last error: {last_error}")

    async def _extract_trafilatura(self, url: str) -> ExtractedContent:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            raise ValueError("Failed to download")
        
        # Try different output formats compatible with trafilatura version
        text = None
        markdown = None
        for fmt in ["txt", "markdown", "xml"]:
            try:
                result = trafilatura.extract(
                    downloaded,
                    output_format=fmt,
                    include_links=True,
                    include_images=True,
                    include_tables=True
                )
                if result and len(result) > 100:
                    if fmt == "txt":
                        text = result
                    elif fmt == "markdown":
                        markdown = result
                    break
            except Exception:
                continue
        
        if not text:
            # Fallback: extract without format specification
            text = trafilatura.extract(downloaded)
        
        if not text or len(text) < 100:
            raise ValueError("Insufficient content extracted")
        
        soup = BeautifulSoup(downloaded, "lxml")
        title = soup.title.string if soup.title else urlparse(url).netloc
        
        return ExtractedContent(
            url=url,
            title=title.strip(),
            raw_text=text,
            markdown=markdown or text,
            metadata={"extractor": "trafilatura"},
            content_length=len(text),
            word_count=len(text.split())
        )

    async def _extract_readability(self, url: str) -> ExtractedContent:
        response = await self.client.get(url)
        response.raise_for_status()
        
        doc = Document(response.text)
        title = doc.title()
        html = doc.summary()
        
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator="\n", strip=True)
        
        if len(text) < 100:
            raise ValueError("Insufficient content")
        
        return ExtractedContent(
            url=url,
            title=title,
            raw_text=text,
            markdown=text,
            metadata={"extractor": "readability"},
            content_length=len(text),
            word_count=len(text.split())
        )

    async def _extract_webcrawl(self, url: str) -> ExtractedContent:
        response = await self.client.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "lxml")
        
        # Remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        
        title = soup.title.string if soup.title else urlparse(url).netloc
        
        # Get main content
        main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|main|post"))
        if main:
            text = main.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)
        
        if len(text) < 100:
            raise ValueError("Insufficient content")
        
        return ExtractedContent(
            url=url,
            title=title.strip(),
            raw_text=text,
            markdown=text,
            metadata={"extractor": "webcrawl"},
            content_length=len(text),
            word_count=len(text.split())
        )

    async def _extract_playwright(self, url: str) -> ExtractedContent:
        browser = await self._get_playwright_browser()
        page = await browser.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Try to get article content
            content = await page.evaluate("""
                () => {
                    const article = document.querySelector('article, main, [role="main"], .content, .post');
                    return article ? article.innerText : document.body.innerText;
                }
            """)
            
            title = await page.title()
            
            if len(content) < 100:
                raise ValueError("Insufficient content")
            
            return ExtractedContent(
                url=url,
                title=title,
                raw_text=content,
                markdown=content,
                metadata={"extractor": "playwright"},
                content_length=len(content),
                word_count=len(content.split())
            )
        finally:
            await page.close()

    async def close(self):
        await self.client.aclose()
        if self._playwright_browser:
            await self._playwright_browser.close()


class SemanticChunker:
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        
        try:
            import tiktoken
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            self.tokenizer = None

    def count_tokens(self, text: str) -> int:
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        return len(text.split()) * 1.3  # rough estimate

    def chunk_by_headers(self, text: str) -> List[Dict[str, Any]]:
        """Split by markdown headers, preserving hierarchy."""
        lines = text.split("\n")
        chunks = []
        current_chunk = []
        current_headers = []
        
        for line in lines:
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if header_match:
                level = len(header_match.group(1))
                header_text = header_match.group(2)
                
                # Save previous chunk
                if current_chunk:
                    chunk_text = "\n".join(current_chunk).strip()
                    if len(chunk_text) >= self.min_chunk_size:
                        chunks.append({
                            "text": chunk_text,
                            "header_path": " > ".join(current_headers),
                            "level": max([h[0] for h in current_headers]) if current_headers else 0
                        })
                
                # Update header stack
                current_headers = [(level, h) for l, h in current_headers if l < level]
                current_headers.append((level, header_text))
                current_chunk = [line]
            else:
                current_chunk.append(line)
        
        # Last chunk
        if current_chunk:
            chunk_text = "\n".join(current_chunk).strip()
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append({
                    "text": chunk_text,
                    "header_path": " > ".join([h for _, h in current_headers]),
                    "level": max([h[0] for h in current_headers]) if current_headers else 0
                })
        
        return chunks

    def split_large_chunk(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Split chunks that exceed token limit."""
        text = chunk["text"]
        tokens = self.count_tokens(text)
        
        if tokens <= self.chunk_size:
            return [chunk]
        
        # Split by paragraphs
        paragraphs = text.split("\n\n")
        sub_chunks = []
        current = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = self.count_tokens(para)
            if current_tokens + para_tokens > self.chunk_size and current:
                sub_chunks.append({
                    "text": "\n\n".join(current).strip(),
                    "header_path": chunk["header_path"],
                    "level": chunk["level"]
                })
                current = [para]
                current_tokens = para_tokens
            else:
                current.append(para)
                current_tokens += para_tokens
        
        if current:
            sub_chunks.append({
                "text": "\n\n".join(current).strip(),
                "header_path": chunk["header_path"],
                "level": chunk["level"]
            })
        
        return sub_chunks

    def add_overlap(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add overlapping context between chunks."""
        if len(chunks) <= 1:
            return chunks
        
        result = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                # Add last paragraph of previous chunk
                prev_text = chunks[i-1]["text"]
                prev_paras = prev_text.split("\n\n")
                if len(prev_paras) > 1:
                    overlap = prev_paras[-1]
                    chunk["text"] = overlap + "\n\n" + chunk["text"]
            result.append(chunk)
        return result

    def chunk(self, text: str, title: str = "") -> List[DocumentChunk]:
        # First, split by headers
        header_chunks = self.chunk_by_headers(text)
        
        # Then split large chunks
        all_chunks = []
        for hc in header_chunks:
            all_chunks.extend(self.split_large_chunk(hc))
        
        # Add overlap
        all_chunks = self.add_overlap(all_chunks)
        
        # Convert to DocumentChunk
        doc_chunks = []
        for i, chunk in enumerate(all_chunks):
            # Add document title as context for first few chunks
            contextual_text = chunk["text"]
            if i < 3 and title:
                contextual_text = f"Document: {title}\n\nSection: {chunk['header_path']}\n\n{chunk['text']}"
            
            doc_chunks.append(DocumentChunk(
                text=contextual_text,
                metadata={
                    "header_path": chunk["header_path"],
                    "header_level": chunk["level"],
                },
                token_count=self.count_tokens(contextual_text),
                chunk_index=i
            ))
        
        return doc_chunks


def clean_text(text: str) -> str:
    """Clean extracted text."""
    # Remove excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Remove common boilerplate
    text = re.sub(r"(?i)cookie|privacy policy|terms of service|subscribe|newsletter", "", text)
    return text.strip()