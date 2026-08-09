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
                    headless=settings.PLAYWRIGHT_HEADLESS,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ]
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
                    # For Instagram, accept shorter content (captions can be brief)
                    # The extractor returns specific metadata when it got valid content
                    is_valid_instagram = (
                        content
                        and content.metadata
                        and content.metadata.get("extractor") in (
                            "instagram_cookies", "instagram_metadata",
                            "instagram_metadata_fallback", "instagram_video_frames",
                        )
                    )
                    if is_valid_instagram:
                        logger.success("Successfully extracted Instagram content with cookies")
                        content.extraction_strategy = "instagram_cookies"
                        # _extract_instagram already calls _filter_instagram_feed internally
                        return content
                except Exception as e:
                    logger.warning(f"Instagram cookie extraction failed: {e}")
            else:
                logger.warning("Instagram URL detected but no cookies loaded")

        # Try strategies in order
        # Skip Playwright for Instagram URLs - generic Playwright always gets login page
        strategies = [
            (ExtractionStrategy.TRAFILATURA, self._extract_trafilatura),
            (ExtractionStrategy.READABILITY, self._extract_readability),
            (ExtractionStrategy.WEBCRAWL, self._extract_webcrawl),
        ]
        if not self._is_instagram_url(url):
            strategies.append((ExtractionStrategy.PLAYWRIGHT, self._extract_playwright))
        
        last_error = None
        for strategy_name, strategy_func in strategies:
            try:
                content = await strategy_func(url)
                if content and len(content.raw_text) > 100:
                    # Skip feed filtering for video-extracted content
                    if content.metadata and content.metadata.get("has_caption") is False:
                        logger.success(f"Successfully extracted with {strategy_name} (video frames)")
                        content.extraction_strategy = strategy_name
                        return content
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
        """Extract Instagram content using saved cookies with Playwright.
        
        For Reels without captions, falls back to video frame extraction + OCR.
        """
        # First, try to get metadata via yt-dlp to check if caption exists
        metadata = await self._get_instagram_metadata(url)
        
        def _extract_sync():
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=settings.PLAYWRIGHT_HEADLESS,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    timezone_id="America/New_York",
                )
                context.add_cookies(self._instagram_cookies)
                page = context.new_page()

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(5000)

                    # Extract reel caption content
                    content = page.evaluate("""
                        () => {
                            // Strategy 1: Get from og:description meta tag (most reliable for reels)
                            const ogDesc = document.querySelector('meta[property="og:description"]');
                            if (ogDesc && ogDesc.content) {
                                const match = ogDesc.content.match(/"(.+)"/);
                                if (match && match[1].length > 10) {
                                    return match[1];
                                }
                                if (ogDesc.content.length > 20) {
                                    return ogDesc.content;
                                }
                            }

                            // Strategy 2: Find the reel caption via data-testid
                            const postText = document.querySelector('[data-testid="post-text"]');
                            if (postText && postText.innerText.trim().length > 30) {
                                return postText.innerText.trim();
                            }

                            // Strategy 3: Find caption in the reel's article container
                            const articles = document.querySelectorAll('article');
                            for (const article of articles) {
                                const spans = article.querySelectorAll('span');
                                for (const span of spans) {
                                    const text = span.innerText.trim();
                                    if (text.length > 50 && text.length < 5000) {
                                        if (text.includes('#') || text.split('\\n').length > 2) {
                                            return text;
                                        }
                                    }
                                }
                            }

                            // Strategy 4: Find h1 or main heading
                            const h1 = document.querySelector('h1');
                            if (h1 && h1.innerText.trim().length > 20) {
                                return h1.innerText.trim();
                            }

                            // Strategy 5: Get main content using innerText (preserves spacing)
                            const main = document.querySelector('main') || document.querySelector('[role="main"]');
                            if (main) {
                                const fullText = main.innerText.trim();
                                if (fullText.length > 30) {
                                    return fullText;
                                }
                            }

                            // Last resort: return empty string instead of full page
                            return '';
                        }
                    """)

                    title = page.title()

                    # Extract username from og:description for a better title
                    og_username = page.evaluate("""() => {
                        const meta = document.querySelector('meta[property="og:description"]');
                        if (meta && meta.content) {
                            const match = meta.content.match(/^(.+?) on /);
                            if (match) return match[1].trim();
                        }
                        return '';
                    }""")

                    # Get page URL after any redirects
                    final_url = page.url

                    return {
                        "url": final_url,
                        "title": og_username or title,
                        "raw_text": content or '',
                        "markdown": content or '',
                    }
                finally:
                    page.close()
                    context.close()
                    browser.close()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _extract_sync)
        
        # Check if we got meaningful content from Playwright
        raw_text = result.get("raw_text", "")
        is_login_page = "Log in" in raw_text[:200] or "Password" in raw_text[:200]
        
        # Check if content looks like feed content (unrelated posts)
        # Only check if NOT a login page
        feed_patterns = [
            r"•\s*\nFollow",
            r"(?:Blood Soul|CLASH|Effects pack)",
            r"(?:Watch Story|𝐖𝐚𝐭𝐜𝐡 𝐒𝐭𝐨𝐫𝐲)",
            r"(?:Japanese|ジャンプ|サーブ|バレーボール)",
            r"(?:Free Certifications|Google & Microsoft)",
            r"(?:Automatic bridge in Minecraft)",
            r"(?:弥渡山歌|YANGYINYUE)",
            r"(?:Follow button kon)",
            r"(?:Surjit Bindrakhia|Lakk Tunoo)",  # Punjabi music
            r"(?:Lo aa gay|new trend)",  # Trend content
            r"·\s*[A-Z]",  # Music artist pattern (Artist · Song)
            r"(?:trend|viral|fyp|explore)",  # Generic viral content
        ]
        is_feed_content = not is_login_page and any(re.search(p, raw_text, re.IGNORECASE) for p in feed_patterns)
        
        has_caption = (
            raw_text
            and len(raw_text) > 50
            and not is_login_page
            and not is_feed_content
        )
        logger.info(f"Instagram Playwright result: len={len(raw_text)}, has_caption={has_caption}, is_feed={is_feed_content}")
        
        # If no caption found or feed content detected, try metadata description first
        # (yt-dlp reliably extracts the reel description)
        if not has_caption and metadata:
            description = metadata.get("description", "")
            if description and len(description) > 20:
                title = metadata.get("uploader", "Instagram Reel")
                full_text = f"Title: Video by {title}\n\n{description}"
                logger.info(f"Using yt-dlp metadata description ({len(description)} chars)")
                
                # Also try video frame extraction for richer content
                video_content = await self._extract_instagram_from_video(url, metadata)
                if video_content and len(video_content) > 100:
                    full_text = f"Title: Video by {title}\n\n{description}\n\n[Video Frame Content]:\n{video_content}"
                
                return ExtractedContent(
                    url=url,
                    title=f"Video by {title}",
                    raw_text=full_text,
                    markdown=full_text,
                    metadata={"extractor": "instagram_metadata", "uploader": title, "has_caption": bool(description)},
                    content_length=len(full_text),
                    word_count=len(full_text.split())
                )
            
            # Fallback: try video frame extraction even without description
            logger.info("No caption found in Instagram Reel, attempting video frame extraction...")
            video_content = await self._extract_instagram_from_video(url, metadata)
            if video_content and len(video_content) > 100:
                title = metadata.get("uploader", "Instagram Reel")
                full_text = f"Title: Video by {title}\n\n[Video Frame Content]:\n{video_content}"
                return ExtractedContent(
                    url=url,
                    title=f"Video by {title}",
                    raw_text=full_text,
                    markdown=full_text,
                    metadata={"extractor": "instagram_video_frames", "uploader": title, "has_caption": False},
                    content_length=len(full_text),
                    word_count=len(full_text.split())
                )
        
        # If we have caption content, also try video extraction for richer content
        # Reels often have spoken content not in the caption
        if has_caption:
            caption_text = result["raw_text"]
            title = result["title"]
            
            # Always attempt video extraction (audio transcript + OCR) for Reels
            logger.info("Caption found, also attempting video audio transcription + OCR...")
            video_content = await self._extract_instagram_from_video(url, metadata)
            
            if video_content and len(video_content) > 50:
                # Combine caption with video content
                full_text = f"Title: {title}\n\n[Caption]:\n{caption_text}\n\n[Video Content]:\n{video_content}"
                logger.info(f"Combined caption + video content: {len(full_text)} chars")
            else:
                # Use caption alone
                full_text = caption_text
                logger.info(f"Using caption alone: {len(full_text)} chars")
            
            content = ExtractedContent(
                url=result["url"],
                title=title,
                raw_text=full_text,
                markdown=full_text,
                metadata={"extractor": "instagram_cookies", "has_caption": True},
                content_length=len(full_text),
                word_count=len(full_text.split())
            )
            content = self._filter_instagram_feed(content, url)
            return content
        
        # Last resort: use metadata description if available, otherwise return what we have
        if metadata and metadata.get("description"):
            title = metadata.get("uploader", "Instagram Reel")
            description = metadata["description"]
            full_text = f"Title: Video by {title}\n\n{description}"
            return ExtractedContent(
                url=url,
                title=f"Video by {title}",
                raw_text=full_text,
                markdown=full_text,
                metadata={"extractor": "instagram_metadata_fallback", "uploader": title, "has_caption": True},
                content_length=len(full_text),
                word_count=len(full_text.split())
            )
        
        return ExtractedContent(
            url=url,
            title=result.get("title", "Instagram Reel"),
            raw_text=result.get("raw_text", ""),
            markdown=result.get("markdown", ""),
            metadata={"extractor": "instagram_cookies"},
            content_length=len(result.get("raw_text", "")),
            word_count=len(result.get("raw_text", "").split())
        )

    def _filter_instagram_feed(self, content: ExtractedContent, url: str) -> ExtractedContent:
        """Filter Instagram feed to extract only the target reel content."""
        raw_text = content.raw_text
        
        # Common feed content indicators that suggest we're getting unrelated posts
        feed_indicators = [
            r"•\s*\nFollow",  # "username • Follow" pattern
            r"\nLikes\n\d",   # Likes count
            r"\n\d+\s*\n\d+\s*$",  # Comment counts at end
            r"#(?:viral|instagood|fyp|explore)",  # Generic viral hashtags
            r"(?:concert|match|live|stream)",  # Live event content
            r"(?:game|gaming|player)",  # Gaming content unrelated to tech
            r"(?:marvel|avengers|thanos)",  # Marvel content
            r"(?:Blood Soul|CLASH|Effects pack)",  # Music/effects content
            r"(?:Watch Story|𝐖𝐚𝐭𝐜𝐡 𝐒𝐭𝐨𝐫𝐲)",  # Story promotion
            r"(?:ジャンプ|サーブ|バレーボール)",  # Japanese sports content
            r"(?:Free Certifications|Google & Microsoft)",  # Certification spam
            r"(?:follow for|follow me)",  # Follow requests
        ]
        
        # Check if content looks like feed content
        # Skip feed filter if content has video transcription/OCR markers (real reel content)
        has_video_content = (
            "[Audio Transcript]" in raw_text
            or "[Video Frame OCR]" in raw_text
            or "[Video Content]" in raw_text
            or "[English Transcript]" in raw_text
            or "[Hindi Translation]" in raw_text
        )
        is_feed_content = False
        if not has_video_content:
            for pattern in feed_indicators:
                if re.search(pattern, raw_text, re.IGNORECASE):
                    is_feed_content = True
                    logger.info(f"Detected feed content indicator: {pattern}")
                    break
        
        # If content looks like feed content, try to extract the first meaningful post
        # rather than returning empty - the first post is often the target reel
        if is_feed_content:
            logger.warning("Extracted content appears to be from Instagram feed, attempting to isolate target post")
        
        # Split by common Instagram feed separators
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
        
        # Find the target post - prefer the most substantial post (likely the target reel)
        target_post = None
        
        # Strategy 1: Find the post with the most content (reels usually have the longest caption)
        if posts:
            # Score each post by word count and caption-like features
            scored_posts = []
            for post in posts:
                word_count = len(post.split())
                has_hashtags = '#' in post
                has_newlines = post.count('\n') >= 2
                # Reels typically have descriptive captions with hashtags
                score = word_count + (50 if has_hashtags else 0) + (20 if has_newlines else 0)
                scored_posts.append((score, post))
            
            # Pick the highest-scoring post
            scored_posts.sort(key=lambda x: x[0], reverse=True)
            target_post = scored_posts[0][1].strip()
        
        # Strategy 2: Look for posts with substantial content (>20 words)
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

    async def _get_instagram_metadata(self, url: str) -> dict:
        """Get Instagram Reel metadata using yt-dlp."""
        import subprocess
        import json as json_module
        
        cookies_path = Path(self.COOKIES_FILE)
        
        # Try with cookies file first, then fallback to browser cookies
        attempts = []
        if cookies_path.exists():
            attempts.append(["--cookies", str(cookies_path)])
        attempts.append(["--cookies-from-browser", "chrome"])
        
        for cookie_args in attempts:
            try:
                cmd = [
                    "yt-dlp",
                    *cookie_args,
                    "--dump-json",
                    "--no-playlist",
                    url
                ]
                
                logger.info(f"Trying yt-dlp with {cookie_args[0]}...")
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=60,
                    cwd=str(Path(__file__).parent.parent.parent)
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    metadata = json_module.loads(result.stdout)
                    logger.info(f"Instagram metadata: uploader={metadata.get('uploader')}, has_description={bool(metadata.get('description'))}")
                    return metadata
                else:
                    logger.warning(f"yt-dlp failed with {cookie_args[0]}: {result.stderr[:200]}")
            except subprocess.TimeoutExpired:
                logger.warning(f"yt-dlp metadata extraction timed out with {cookie_args[0]}")
            except Exception as e:
                logger.warning(f"Failed with {cookie_args[0]}: {e}")
        
        return {}

    async def _extract_instagram_from_video(self, url: str, metadata: dict) -> str:
        """Extract content from Instagram Reel by downloading video, running OCR, and transcribing audio."""
        import subprocess
        import tempfile
        import shutil
        
        cookies_path = Path(self.COOKIES_FILE)
        temp_dir = Path(tempfile.mkdtemp(prefix="insta_reel_"))
        
        try:
            # Try with cookies file first, then fallback to browser cookies
            attempts = []
            if cookies_path.exists():
                attempts.append(["--cookies", str(cookies_path)])
            attempts.append(["--cookies-from-browser", "chrome"])
            
            video_id = url.rstrip("/").split("/")[-1]
            output_path = temp_dir / f"{video_id}.mp4"
            
            for cookie_args in attempts:
                try:
                    cmd = [
                        "yt-dlp",
                        *cookie_args,
                        "--no-playlist",
                        "-o", str(output_path),
                        url
                    ]
                    
                    logger.info(f"Downloading Instagram Reel video with {cookie_args[0]}...")
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        timeout=120,
                        cwd=str(Path(__file__).parent.parent.parent)
                    )
                    
                    if result.returncode == 0:
                        if output_path.exists():
                            logger.info(f"Video downloaded: {output_path.name}")
                            break
                        else:
                            # yt-dlp might add extension
                            possible_paths = list(temp_dir.glob(f"{video_id}.*"))
                            if possible_paths:
                                output_path = possible_paths[0]
                                logger.info(f"Video downloaded: {output_path.name}")
                                break
                    
                    logger.warning(f"Video download failed with {cookie_args[0]}: {result.stderr[:200]}")
                except subprocess.TimeoutExpired:
                    logger.warning(f"Video download timed out with {cookie_args[0]}")
                except Exception as e:
                    logger.warning(f"Failed with {cookie_args[0]}: {e}")
            
            if not output_path.exists():
                logger.warning("Video file not found after all download attempts")
                return ""
            
            logger.info(f"Video downloaded: {output_path.name}")
            
            # Extract audio from video
            audio_path = temp_dir / "audio.wav"
            cmd = [
                "ffmpeg",
                "-i", str(output_path),
                "-vn",  # No video
                "-acodec", "pcm_s16le",  # WAV format
                "-ar", "16000",  # 16kHz sample rate
                "-ac", "1",  # Mono
                str(audio_path),
                "-y"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            # Transcribe audio
            transcript = ""
            if audio_path.exists():
                logger.info("Transcribing audio...")
                transcript = await self._transcribe_audio(audio_path)
                if transcript:
                    logger.info(f"Audio transcription: {len(transcript)} chars")
            
            # Extract frames using FFmpeg
            frames_dir = temp_dir / "frames"
            frames_dir.mkdir(exist_ok=True)
            
            cmd = [
                "ffmpeg",
                "-i", str(output_path),
                "-vf", "fps=1/2",  # Extract one frame every 2 seconds
                "-q:v", "2",
                str(frames_dir / "frame_%04d.jpg"),
                "-y"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                logger.warning(f"Frame extraction failed: {result.stderr[:200]}")
                return transcript  # Return transcript if frame extraction fails
            
            frames = sorted(frames_dir.glob("*.jpg"))
            logger.info(f"Extracted {len(frames)} frames")
            
            # Try OCR on frames
            ocr_text = ""
            if frames:
                ocr_text = await self._ocr_frames(frames)
                if ocr_text:
                    logger.info(f"OCR extracted {len(ocr_text)} chars from video frames")
            
            # Combine transcript and OCR text
            combined_text = ""
            if transcript:
                combined_text += f"[Audio Transcript]:\n{transcript}\n\n"
            if ocr_text:
                combined_text += f"[Video Frame OCR]:\n{ocr_text}"
            
            if combined_text:
                return combined_text
            
            # If no text extracted, return frame count info
            return f"[Video contains {len(frames)} key frames - no text detected]"
            
        except Exception as e:
            logger.error(f"Video extraction failed: {e}")
            return ""
        finally:
            # Cleanup temp directory
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    async def _transcribe_audio(self, audio_path: Path) -> str:
        """Transcribe audio using SpeechRecognition with Google's free API."""
        try:
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            
            # Load audio file
            with sr.AudioFile(str(audio_path)) as source:
                audio_data = recognizer.record(source)
            
            # Try English first (most Reels are in English)
            transcript_en = ""
            try:
                transcript_en = recognizer.recognize_google(audio_data, language="en-US")
                logger.info(f"Transcribed with English (US): {len(transcript_en)} chars")
            except Exception as e:
                logger.warning(f"English (US) transcription failed: {e}")
            
            # If English US failed or is too short, try English India
            if len(transcript_en) < 20:
                try:
                    transcript_en = recognizer.recognize_google(audio_data, language="en-IN")
                    logger.info(f"Transcribed with English (IN): {len(transcript_en)} chars")
                except Exception as e:
                    logger.warning(f"English (IN) transcription failed: {e}")
            
            # If English failed completely, try Hindi as fallback
            transcript_hi = ""
            if len(transcript_en) < 20:
                try:
                    transcript_hi = recognizer.recognize_google(audio_data, language="hi-IN")
                    logger.info(f"Transcribed with Hindi: {len(transcript_hi)} chars")
                except Exception as e:
                    logger.warning(f"Hindi transcription failed: {e}")
            
            # Translate Hindi to English only if English failed
            translated = ""
            if transcript_hi and len(transcript_en) < 20:
                translated = await self._translate_hindi_to_english(transcript_hi)
                logger.info(f"Translated to English: {len(translated)} chars")
            
            # Use English as primary, translation as fallback
            combined = ""
            if transcript_en:
                # LLM cleanup to fix proper nouns and improve accuracy
                cleaned = await self._cleanup_transcript(transcript_en)
                if cleaned and len(cleaned) > len(transcript_en) * 0.8:
                    combined += f"[English Transcript]:\n{cleaned}"
                else:
                    combined += f"[English Transcript]:\n{transcript_en}"
            if translated:
                combined += f"\n\n[Hindi Translation]:\n{translated}"
            
            return combined if combined else ""
                
        except ImportError:
            logger.warning("SpeechRecognition not available")
            return ""
        except Exception as e:
            logger.warning(f"Audio transcription failed: {e}")
            return ""

    async def _cleanup_transcript(self, raw_transcript: str) -> str:
        """Use LLM to fix proper nouns, brand names, and improve transcript accuracy.
        
        Google's free STT often mangles proper nouns (e.g., "SPG icons" → "SVG icons",
        "Shaders" → missed entirely). This uses the LLM with context to clean up.
        """
        try:
            from src.enrichment.llm_client import LLMClient
            llm = LLMClient()
            
            result = await llm.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a transcript cleanup assistant. Clean up this Instagram Reel transcript.\n\n"
                            "TASKS:\n"
                            "1. Fix STT errors (mangled words, proper nouns)\n"
                            "2. REMOVE author/creator names (e.g., 'RammCodes', 'Developer Advocate')\n"
                            "3. REMOVE filler words: 'hey guys', 'welcome back', 'let's go', 'check this out',\n"
                            "   'make sure', 'subscribe', 'link in bio', 'follow for more'\n"
                            "4. REMOVE Instagram-specific: 'follow', 'like', 'comment', 'share', 'save'\n"
                            "5. Keep ONLY the technical content about tools/websites\n\n"
                            "EXAMPLE:\n"
                            "Input: 'Hey guys welcome back to my channel I'm RammCodes Developer Advocate and today we're looking at 404 animations'\n"
                            "Output: '404 animations - free to copy'\n\n"
                            "RULES:\n"
                            "- Remove author names and social media phrases\n"
                            "- Keep tool/website names and technical descriptions\n"
                            "- Return ONLY cleaned content, no explanations"
                        ),
                    },
                    {"role": "user", "content": f"Clean up this transcript:\n\n{raw_transcript}"},
                ],
                temperature=0.1,
                max_tokens=500,
            )
            
            cleaned = result["content"].strip()
            if cleaned and len(cleaned) > 20:
                logger.info(f"Cleaned transcript: {len(raw_transcript)} → {len(cleaned)} chars")
                return cleaned
            
        except Exception as e:
            logger.warning(f"Transcript cleanup failed: {e}")
        
        return raw_transcript

    async def _translate_hindi_to_english(self, hindi_text: str) -> str:
        """Translate Hindi text to English with brand name correction.
        
        Uses LLM to translate Hindi transcript to proper English,
        fixing brand names that get mangled in Hindi transcription.
        """
        # Common brand name corrections for Hindi transcriptions
        brand_corrections = {
            "अब वर्क": "Upwork",
            "अबवर्क": "Upwork",
            "फ्रीलांसिंग": "freelancing",
            "फ्रीलांसर": "freelancer",
            "टॉपटल": "Toptal",
            "हैंडशेक": "Handshake",
            "फ्रीलांसर डॉट कॉम": "Freelancer.com",
            "रिमोट जॉब": "remote job",
            "प्रोजेक्ट": "project",
            "क्लाइंट": "client",
            "वेब डेवलपमेंट": "web development",
            "डिजाइनिंग": "designing",
            "मार्केटिंग": "marketing",
            "राइटिंग": "writing",
            "प्रीमियम": "premium",
            "फ्रीलांसिंग प्लेटफार्म": "freelancing platform",
        }
        
        # Apply dictionary corrections first
        corrected = hindi_text
        for hindi, english in brand_corrections.items():
            corrected = corrected.replace(hindi, english)
        
        # Try LLM translation for better accuracy (use Ollama first)
        try:
            from src.enrichment.llm_client import LLMClient, LLMProvider
            llm = LLMClient()
            
            # Try Ollama first (local, free)
            try:
                result = await llm.chat_completion(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a Hindi to English translator specializing in tech content. "
                                "Translate the Hindi text to natural English. Fix brand names: "
                                "Upwork (not Ab Work), Freelancer, Toptal, Handshake. "
                                "Return ONLY the English translation, no explanations."
                            ),
                        },
                        {"role": "user", "content": f"Translate this Hindi tech content to English:\n\n{hindi_text}"},
                    ],
                    temperature=0.1,
                    max_tokens=500,
                )
                
                translated = result["content"].strip()
                if translated and len(translated) > 20:
                    logger.info("Translation completed using LLM")
                    return translated
            except Exception as e:
                logger.warning(f"LLM translation failed: {e}")
                
        except Exception as e:
            logger.warning(f"LLM translation failed: {e}, using dictionary corrections")
        
        # Fallback to dictionary-corrected text
        return corrected

    async def _ocr_frames(self, frames: list) -> str:
        """OCR text from video frames using available OCR library."""
        texts = []
        
        # Try pytesseract first
        try:
            import pytesseract
            from PIL import Image, ImageFilter, ImageEnhance
            
            # Set tesseract path for Windows
            import os
            tess_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(tess_path):
                pytesseract.pytesseract.tesseract_cmd = tess_path
            
            for frame_path in frames:
                try:
                    img = Image.open(frame_path)
                    # Preprocess: grayscale + contrast boost + sharpen
                    img_gray = img.convert('L')
                    img_enhanced = ImageEnhance.Contrast(img_gray).enhance(2.0)
                    img_sharp = img_enhanced.filter(ImageFilter.SHARPEN)
                    
                    text = pytesseract.image_to_string(img_sharp, lang="eng", config="--psm 6")
                    if text and len(text.strip()) > 10:
                        cleaned = text.strip()
                        # Keep alphanumeric, spaces, and common punctuation
                        cleaned = re.sub(r'[^\w\s#@.,!?\'-]', ' ', cleaned)
                        cleaned = re.sub(r'\s+', ' ', cleaned)
                        if len(cleaned) > 10:
                            texts.append(cleaned)
                except Exception:
                    continue
            
            if texts:
                # Remove duplicate texts
                seen = set()
                unique_texts = []
                for t in texts:
                    # Use first 50 chars as dedup key
                    key = t[:50].lower()
                    if key not in seen:
                        seen.add(key)
                        unique_texts.append(t)
                return "\n\n".join(unique_texts)
        except ImportError:
            pass
        
        # Try easyocr if available
        try:
            import easyocr
            reader = easyocr.Reader(['en', 'hi'])
            
            for frame_path in frames:
                try:
                    result = reader.readtext(str(frame_path))
                    frame_text = " ".join([r[1] for r in result if r[2] > 0.3])
                    if frame_text and len(frame_text.strip()) > 10:
                        cleaned = frame_text.strip()
                        cleaned = re.sub(r'[^\w\s#@.,!?\'-]', ' ', cleaned)
                        cleaned = re.sub(r'\s+', ' ', cleaned)
                        if len(cleaned) > 10:
                            texts.append(cleaned)
                except Exception:
                    continue
            
            if texts:
                seen = set()
                unique_texts = []
                for t in texts:
                    key = t[:50].lower()
                    if key not in seen:
                        seen.add(key)
                        unique_texts.append(t)
                return "\n\n".join(unique_texts)
        except ImportError:
            pass
        
        # No OCR library available
        return ""

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