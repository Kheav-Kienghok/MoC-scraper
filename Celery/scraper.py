import aiohttp
import asyncio
import requests
import time
from bs4 import BeautifulSoup
import re
import logging
from urllib.parse import urlparse
from typing import List, Dict, Optional


# Set up logging for debugging and monitoring
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class MoFAWebScraper:
    """
    Web scraper for Ministry of Foreign Affairs and International Cooperation website
    Extracts and separates English and Khmer content into structured CSV format
    """

    def __init__(
        self, delay: float = 1.0, timeout: int = 30, language_cookie: str = "1"
    ):
        """
        Initialize the scraper with configuration and compile regex patterns

        Args:
            delay: Delay between requests
            timeout: Timeout in seconds
            language_cookie: '1' for English, '3' for Khmer
        """
        self.delay = delay
        self.timeout = timeout

        # Pre-compile regex patterns for better performance
        self.whitespace_pattern = re.compile(r"\s+")
        self.dash_pattern = re.compile(r"^\s*[-\s]*\s*$")
        self.dot_pattern = re.compile(r"^\s*[.]\s*$")
        self.non_word_pattern = re.compile(r"[^\w\s]")

        # Set headers to mimic a real browser
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Cookie": f"Language={language_cookie}",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def detect_language(self, text: str) -> str:
        """
        Detect if text is primarily English, Khmer, or mixed

        Args:
            text: Text to analyze

        Returns:
            'khmer', 'english', or 'mixed'
        """
        if not text:
            return "english"

        # Count Khmer Unicode characters (U+1780 to U+17FF)
        khmer_chars = sum(1 for char in text if "\u1780" <= char <= "\u17ff")
        # Count English letters
        english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)

        total_chars = len(text.replace(" ", ""))

        if total_chars == 0:
            return "english"

        khmer_ratio = khmer_chars / total_chars
        english_ratio = english_chars / total_chars

        # If more than 30% Khmer characters, consider it Khmer
        if khmer_ratio > 0.3:
            return "khmer"
        # If more than 50% English characters, consider it English
        elif english_ratio > 0.5:
            return "english"
        else:
            return "mixed"

    def clean_text(self, text: str) -> str:
        """
        Optimized text cleaning using pre-compiled regex patterns

        Args:
            text: Raw text to clean

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Use pre-compiled patterns for better performance
        text = self.whitespace_pattern.sub(" ", text.strip())
        text = self.dash_pattern.sub("", text)
        text = self.dot_pattern.sub("", text)

        return text.strip()

    def extract_content(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """
        Fixed content extraction with proper deduplication and separator handling
        Now extracts all heading elements as titles and content from div, main, div, and p elements
        Excludes footer content

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Dictionary with paired 'english' and 'khmer' text lists
        """
        content = {"english": [], "khmer": []}

        try:
            # Remove footer elements
            for footer in soup.find_all(
                ["footer", "div"], class_=lambda x: x and "footer" in str(x).lower()
            ):
                footer.decompose()
            for element in soup.find_all(
                ["div"], id=lambda x: x and "footer" in str(x).lower()
            ):
                element.decompose()

            # Extract all heading elements (h1, h2, h3, h4) as titles
            heading_selectors = ["h4"]
            all_texts = []

            for selector in heading_selectors:
                headings = soup.select(selector)
                print(selector)
                for heading in headings:
                    heading_text = self.clean_text(heading.get_text(strip=True))
                    if heading_text and len(heading_text) >= 3:
                        all_texts.append(heading_text)
                        logger.info(f"Found title: {heading_text[:20]}...")

            # Extract content from p elements
            content_selectors = [
                "div.post-content p",  # All <p> elements inside <div class="post-content">
                "span:not(.header-title-en):not(.header-title-km)"  # All span elements except header titles
            ]

            # Process each selector type
            for selector in content_selectors:
                elements = soup.select(
                    selector
                )  # Skip the first p element if we're processing p tags
                if selector == "div.post-content p" and elements:
                    elements = elements[1:]  # Skip the first p element
                    logger.info(
                        f"Skipped first p element, processing {len(elements)} remaining p elements"
                    )

                for element in elements:

                    # Get text content
                    text = element.get_text(strip=True)

                    if text:
                        cleaned_text = self.clean_text(text)
                        if cleaned_text and len(cleaned_text) >= 3:
                            # Avoid duplicates
                            if cleaned_text not in all_texts:
                                all_texts.append(cleaned_text)

            logger.info(f"Total extracted texts: {len(all_texts)}")

            khmer_fragments = []
            english_texts = []

            # Process other texts
            for text in all_texts:
                detected_lang = self.detect_language(text)
                if detected_lang == "khmer":
                    khmer_fragments.append(text)
                else:
                    english_texts.append(text)

            # Add English texts to content
            content["english"] = english_texts  # Join Khmer sentence fragments properly
            if khmer_fragments:
                joined_khmer = self.join_khmer_sentences(khmer_fragments)
                content["khmer"] = joined_khmer

            logger.info(
                f"Final extraction: {len(content['english'])} English, {len(content['khmer'])} Khmer texts"
            )

        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")

        return content

    def join_khmer_sentences(self, data: List[str]) -> List[str]:
        """
        Join Khmer sentence fragments that are split across multiple elements.
        Khmer sentences typically end with "។" character.
        Skips the first element as it's typically a topic/title.

        Args:
            data: List of text fragments

        Returns:
            List of properly joined Khmer sentences
        """
        # If there are no Khmer sentence endings, skip processing and return as-is
        has_khmer_endings = any("។" in item for item in data)
        if not has_khmer_endings:
            return data

        result = []
        temp = ""

        # Skip the first element (topic/title) and process the rest
        items_to_process = data[1:] if len(data) > 1 else []

        # Add the first element (topic) as is if it exists
        if len(data) > 0:
            result.append(data[0])

        for item in items_to_process:
            item = item.strip()
            if not item.endswith("។"):
                temp += item + " "
            else:
                if temp:
                    result.append(temp + item)
                    temp = ""
                else:
                    result.append(item)  # If temp has leftover sentence parts
        if temp:
            result.append(temp.strip())

        return result

    async def scrape_url(
        self, session: aiohttp.ClientSession, url: str
    ) -> Optional[Dict[str, List[str]]]:
        """
        Scrape content from a single URL with optimized processing (async)

        Args:
            session: aiohttp session for making requests
            url: URL to scrape

        Returns:
            Dictionary with extracted content or None if failed
        """
        try:
            logger.info(f"Scraping URL: {url}")

            # Add delay to be respectful to the server
            await asyncio.sleep(self.delay)

            # Make the request
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                response.raise_for_status()

                # Check if we got HTML content
                content_type = response.headers.get("content-type", "").lower()
                if "html" not in content_type:
                    logger.warning(f"URL {url} does not return HTML content")
                    return None

                # Read the response content
                content_bytes = await response.read()

                # Parse HTML with optimized parser
                soup = BeautifulSoup(content_bytes, "html.parser")

                # Extract content using optimized method
                content = self.extract_content(soup)

                logger.info(
                    f"Extracted {len(content['english'])} English and {len(content['khmer'])} Khmer texts"
                )

                return content

        except aiohttp.ClientError as e:
            logger.error(f"Request error for {url}: {str(e)}")
            return None
        except asyncio.TimeoutError as e:
            logger.error(f"Timeout error for {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {str(e)}")
            return None

    def scrape_url_sync(self, url: str) -> Optional[Dict[str, List[str]]]:
        """
        Synchronous version of scrape_url for use with Celery tasks

        Args:
            url: URL to scrape

        Returns:
            Dictionary with extracted content or None if failed
        """
        try:
            logger.info(f"Scraping URL (sync): {url}")

            # Add delay to be respectful to the server
            time.sleep(self.delay)

            # Make the request using requests library
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()

            # Check if we got HTML content
            content_type = response.headers.get("content-type", "").lower()
            if "html" not in content_type:
                logger.warning(f"Non-HTML content type for {url}: {content_type}")
                return None

            # Parse HTML with optimized parser
            soup = BeautifulSoup(response.content, "html.parser")

            # Extract content using optimized method
            content = self.extract_content(soup)

            logger.info(
                f"Extracted {len(content['english'])} English and {len(content['khmer'])} Khmer texts"
            )

            return content

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {url}: {str(e)}")
            return None
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout error for {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {str(e)}")
            return None

    def validate_url(self, url: str) -> bool:
        """
        Validate if URL is properly formatted and from the expected domain

        Args:
            url: URL to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            parsed = urlparse(url)

            # Check if URL has proper structure
            if not parsed.scheme or not parsed.netloc:
                return False

            # Check if it's from the expected domain (optional)
            if "mfaic.gov.kh" not in parsed.netloc:
                logger.warning(f"URL {url} is not from mfaic.gov.kh domain")
                # Don't return False here to allow other domains if needed

            return True

        except Exception:
            return False

    async def scrape_multiple_urls(self, urls: List[str]) -> List[Dict]:
        """
        Scrape content from multiple URLs with async processing

        Args:
            urls: List of URLs to scrape

        Returns:
            List of dictionaries with scraped content
        """
        results = []

        # Create aiohttp session with custom headers and timeout
        connector = aiohttp.TCPConnector(limit=10)  # Limit concurrent connections
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        async with aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        ) as session:

            # Create tasks for all URLs
            tasks = []
            for i, url in enumerate(urls, 1):
                logger.info(f"Preparing to process URL {i}/{len(urls)}: {url}")

                # Validate URL
                if not self.validate_url(url):
                    logger.error(f"Invalid URL: {url}")
                    # Add empty result for invalid URLs
                    results.append(
                        {"id": i, "url": url, "english_texts": [], "khmer_texts": []}
                    )
                    continue

                # Create task for this URL
                task = self.scrape_url(session, url)
                tasks.append((i, url, task))

            # Execute all tasks concurrently with some rate limiting
            for i, url, task in tasks:
                try:
                    content = await task

                    if content:
                        results.append(
                            {
                                "id": i,
                                "url": url,
                                "english_texts": content["english"],
                                "khmer_texts": content["khmer"],
                            }
                        )
                    else:
                        logger.warning(f"Failed to scrape content from {url}")
                        # Add empty result to maintain ID sequence
                        results.append(
                            {
                                "id": i,
                                "url": url,
                                "english_texts": [],
                                "khmer_texts": [],
                            }
                        )
                except Exception as e:
                    logger.error(f"Error processing {url}: {str(e)}")
                    results.append(
                        {"id": i, "url": url, "english_texts": [], "khmer_texts": []}
                    )

        return results
