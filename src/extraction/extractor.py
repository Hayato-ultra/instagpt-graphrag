import asyncio
import json
import hashlib
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from readability import Document
import trafilatura
from playwright.async_api import async_playwright

from src.config import get_settings
from src.config.models import (
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
    INSTAGRAM_COOKIES = "instagram_cookies"


class ContentExtractor:
    COOKIES_FILE = "cookiesinsta.txt"

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; InstaGPT-GraphRAG/0.1)"}
        )
        self._playwright_browser = None
        self._instagram_cookies = self._load_instagram_cookies()

    def _load_instagram_cookies(self) -> List[Dict[str, Any]]:
        """Load Instagram cookies from cookiesinsta.txt (Netscape format)."""
        cookies_path = Path(self.COOKIES_FILE)
        if not cookies_path.exists():
            logger.warning(f"Cookies file not found: {self.COOKIES_FILE}")
            return []

        cookies = []
        try:
            content = cookies_path.read_text(encoding="utf-8")
            for line in content.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    domain, _, path, secure, expires, name, value = parts[:7]
                    cookies.append({
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": path,
                        "secure": secure.upper() == "TRUE",
                        "httpOnly": False,
                    })
            logger.info(f"Loaded {len(cookies)} Instagram cookies")
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
        return cookies

    @staticmethod
    def _is_instagram_url(url: str) -> bool:
        return "instagram.com" in urlparse(url).netloc

    async def _get_playwright_browser(self):
        if self._playwright_browser is None:
            # Use sync playwright in a thread to avoid subprocess issues on Windows
            import threading
            from playwright.sync_api import sync_playwright
            
            def _launch_browser():
                pw = sync_playwright().start()
                self._playwright_browser = pw.chromium.launch(
                    headless=settings.PLAYWRIGHT_HEADLESS
                )
                return pw
            
            # Run in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            self._playwright_pw = await loop.run_in_executor(None, _launch_browser)
        return self._playwright_browser

    async def extract(self, url: str) -> ExtractedContent:
        logger.info(f"Extracting content from: {url}")

        # Instagram requires cookies - try special extraction first
        if self._is_instagram_url(url):
            if self._instagram_cookies:
                try:
                    content = await self._extract_instagram(url)
                    if content and len(content.raw_text) > 100:
                        logger.success("Successfully extracted Instagram content with cookies")
                        content.extraction_strategy = "instagram_cookies"
                        # Post-process to filter unrelated feed content
                        content = self._filter_instagram_feed(content, url)
                        return content
                except Exception as e:
                    logger.warning(f"Instagram cookie extraction failed: {e}")
            else:
                logger.warning("Instagram URL detected but no cookies loaded")

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
        """Extract using Playwright sync API in a thread."""
        import asyncio
        
        def _extract_sync():
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=settings.PLAYWRIGHT_HEADLESS)
                page = browser.new_page()
                
                try:
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(2000)
                    
                    # Try to get article content
                    content = page.evaluate("""
                        () => {
                            const article = document.querySelector('article, main, [role="main"], .content, .post');
                            return article ? article.innerText : document.body.innerText;
                        }
                    """)
                    
                    title = page.title()
                    
                    if len(content) < 100:
                        raise ValueError("Insufficient content")
                    
                    return {
                        "url": url,
                        "title": title,
                        "raw_text": content,
                        "markdown": content,
                    }
                finally:
                    page.close()
                    browser.close()
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _extract_sync)

        return ExtractedContent(
            url=result["url"],
            title=result["title"],
            raw_text=result["raw_text"],
            markdown=result["markdown"],
            metadata={"extractor": "playwright"},
            content_length=len(result["raw_text"]),
            word_count=len(result["raw_text"].split())
        )

    async def _extract_instagram(self, url: str) -> ExtractedContent:
        """Extract Instagram content using saved cookies with Playwright."""

        def _extract_sync():
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=settings.PLAYWRIGHT_HEADLESS)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                )
                context.add_cookies(self._instagram_cookies)
                page = context.new_page()

                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(3000)

                    # Extract reel caption content
                    content = page.evaluate("""
                        () => {
                            // Strategy 1: Find the reel caption via data-testid
                            const postText = document.querySelector('[data-testid="post-text"]');
                            if (postText && postText.innerText.trim().length > 30) {
                                return postText.innerText.trim();
                            }

                            // Strategy 2: Find caption in the reel's article container
                            const articles = document.querySelectorAll('article');
                            for (const article of articles) {
                                // Look for caption-like content (longer text blocks)
                                const spans = article.querySelectorAll('span');
                                for (const span of spans) {
                                    const text = span.innerText.trim();
                                    if (text.length > 50 && text.length < 5000) {
                                        // Check if it looks like a caption (has hashtags or is descriptive)
                                        if (text.includes('#') || text.split('\\n').length > 2) {
                                            return text;
                                        }
                                    }
                                }
                            }

                            // Strategy 3: Find h1 or main heading
                            const h1 = document.querySelector('h1');
                            if (h1 && h1.innerText.trim().length > 20) {
                                return h1.innerText.trim();
                            }

                            // Strategy 4: Get first meaningful text block from main content area
                            const main = document.querySelector('main') || document.querySelector('[role="main"]');
                            if (main) {
                                const textBlocks = [];
                                const walker = document.createTreeWalker(
                                    main,
                                    NodeFilter.SHOW_TEXT,
                                    null,
                                    false
                                );
                                let node;
                                while (node = walker.nextNode()) {
                                    const text = node.textContent.trim();
                                    if (text.length > 20) {
                                        textBlocks.push(text);
                                        if (textBlocks.join('\\n').length > 200) {
                                            break;
                                        }
                                    }
                                }
                                if (textBlocks.length > 0) {
                                    return textBlocks.join('\\n');
                                }
                            }

                            // Last resort: return empty string instead of full page
                            return '';
                        }
                    """)

                    title = page.title()

                    # Get page URL after any redirects
                    final_url = page.url

                    if not content or len(content) < 50:
                        raise ValueError("Insufficient content from Instagram")

                    return {
                        "url": final_url,
                        "title": title,
                        "raw_text": content,
                        "markdown": content,
                    }
                finally:
                    page.close()
                    context.close()
                    browser.close()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _extract_sync)

        return ExtractedContent(
            url=result["url"],
            title=result["title"],
            raw_text=result["raw_text"],
            markdown=result["markdown"],
            metadata={"extractor": "instagram_cookies"},
            content_length=len(result["raw_text"]),
            word_count=len(result["raw_text"].split())
        )

    def _filter_instagram_feed(self, content: ExtractedContent, url: str) -> ExtractedContent:
        """Filter Instagram feed to extract only the target reel content."""
        raw_text = content.raw_text

        # Split by common Instagram feed separators
        # Patterns: "username • Follow", "Likes", "Comments"
        post_separators = [
            r"\n(?=[a-z0-9_.]+\s*•\s*\nFollow)",  # username • Follow pattern
            r"\n(?=\d+[,\d]*\s*\n\d+[,\d]*$)",  # Likes/Comments pattern
        ]

        posts = [raw_text]
        for pattern in post_separators:
            new_posts = []
            for post in posts:
                new_posts.extend(re.split(pattern, post, flags=re.MULTILINE))
            posts = new_posts

        # Find the target post (first post or one matching the URL)
        target_post = None

        # Strategy 1: First post is usually the target reel
        if posts:
            target_post = posts[0].strip()

        # Strategy 2: Look for posts with substantial content (>50 words)
        if target_post and len(target_post.split()) < 20:
            for post in posts:
                if len(post.split()) >= 20:
                    target_post = post.strip()
                    break

        # Clean up the extracted content
        if target_post:
            # Remove "Likes" and number patterns at the end
            target_post = re.sub(r"\nLikes\n[\d,]+\n[\d,]+$", "", target_post)
            # Remove "Follow" button text
            target_post = re.sub(r"\nFollow$", "", target_post)
            # Remove excessive whitespace
            target_post = re.sub(r"\n{3,}", "\n\n", target_post)

            if len(target_post) > 50:
                logger.info(
                    f"Filtered Instagram feed from {len(raw_text)} to "
                    f"{len(target_post)} chars"
                )
                return ExtractedContent(
                    url=content.url,
                    title=content.title,
                    raw_text=target_post,
                    markdown=target_post,
                    metadata=content.metadata,
                    content_length=len(target_post),
                    word_count=len(target_post.split()),
                    extraction_strategy=content.extraction_strategy,
                )

        # If filtering didn't help, return original
        logger.warning("Instagram feed filtering did not improve content, returning original")
        return content

    async def close(self):
        await self.client.aclose()
        # No async cleanup needed for sync playwright instances


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