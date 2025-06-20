"""
Main module for MoC News Scraper.

This module orchestrates the scraping and processing pipeline for bilingual
news articles from the Ministry of Commerce of Cambodia website.
"""

# Standard library imports (built-in Python modules)
import asyncio
import aiofiles
import csv
import logging
import re
import time
import io
from typing import Dict, List, Optional
from urllib.parse import urlparse
from pathlib import Path

# Third-party imports (external packages)
import aiohttp
from bs4 import BeautifulSoup
from asyncio import Semaphore

# Local application imports (your project modules)
from extract_link import extract_link
from KhmerEnglishAligner import KhmerEnglishAligner
from models.db_models import ScrapedContent, Session


# Set up logging for debugging and monitoring
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/scraper.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class MoCWebScraper:
    """
    Web scraper for Ministry of Commerce Cambodia website
    Extracts and separates English and Khmer content into structured CSV format
    """

    def __init__(
        self,
        delay: float = 1.0,
        timeout: int = 30,
        max_concurrent: int = 10,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        """
        Initialize the scraper with configuration and compile regex patterns

        Args:
            delay: Delay between requests to be respectful to the server
            timeout: Request timeout in seconds
            max_concurrent: Maximum number of concurrent requests
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Base delay between retry attempts (exponential backoff)
        """
        self.delay = delay
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.semaphore = Semaphore(max_concurrent)

        self.special_characters = ["- - -", "---", "***", "* * *"]
        self.aligner = KhmerEnglishAligner()

        # Pre-compile regex patterns for better performance
        self.whitespace_pattern = re.compile(r"\s+")
        self.dash_pattern = re.compile(r"^\s*[-\s]*\s*$")
        self.dot_pattern = re.compile(r"^\s*[.]\s*$")
        self.non_word_pattern = re.compile(r"[^\w\s]")

        # Pre-calculate Unicode ranges for language detection
        self.khmer_range_start = 0x1780
        self.khmer_range_end = 0x1800

        # Set headers to mimic a real browser
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self):
        """Create necessary directories if they don't exist"""
        Path("logs").mkdir(exist_ok=True)
        Path("databases").mkdir(exist_ok=True)
        Path("output").mkdir(exist_ok=True)

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Retry a function with exponential backoff

        Args:
            func: The async function to retry
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function

        Returns:
            Result of the function or None if all retries failed
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                if attempt > 0:
                    # Calculate exponential backoff delay
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    logger.info(
                        f"Retrying in {delay:.1f} seconds (attempt {attempt + 1}/{self.max_retries + 1})"
                    )
                    await asyncio.sleep(delay)

                return await func(*args, **kwargs)

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                aiohttp.ServerTimeoutError,
            ) as e:
                last_exception = e
                if attempt < self.max_retries:
                    logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                else:
                    logger.error(
                        f"All {self.max_retries + 1} attempts failed. Last error: {str(e)}"
                    )
            except Exception as e:
                # For non-network errors, don't retry
                logger.error(f"Non-retryable error: {str(e)}")
                return None

        return None

    def is_khmer_text(self, text: str) -> bool:
        """
        Optimized Khmer text detection using pre-compiled patterns and ranges

        Args:
            text: Input text to analyze

        Returns:
            True if text is primarily Khmer, False otherwise
        """
        if not text or not text.strip():
            return False

        # Use pre-compiled pattern for cleaning
        cleaned_text = self.non_word_pattern.sub("", text)
        if not cleaned_text:
            return False

        # More efficient character counting using optimized range checking
        khmer_chars = 0
        latin_chars = 0

        for char in cleaned_text:
            char_code = ord(char)
            if self.khmer_range_start <= char_code < self.khmer_range_end:
                khmer_chars += 1
            elif char.isalpha() and char_code < 256:
                latin_chars += 1

        total_chars = khmer_chars + latin_chars

        # If no alphabetic characters, return False
        if total_chars == 0:
            return False

        # Consider text Khmer if more than 60% of characters are Khmer
        khmer_ratio = khmer_chars / total_chars
        return khmer_ratio > 0.6

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

        # Preserve special characters that act as separators
        if text.strip() in self.special_characters:
            return text.strip()

        # Use pre-compiled patterns for better performance
        text = self.whitespace_pattern.sub(" ", text.strip())
        text = self.dash_pattern.sub("", text)
        text = self.dot_pattern.sub("", text)

        return text.strip()

    def extract_content(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """
        Fixed content extraction with proper deduplication and separator handling

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Dictionary with paired 'english' and 'khmer' text lists
        """
        content = {"english": [], "khmer": []}

        try:
            # Extract title separately (it's outside page-description)
            title_text = None
            title_element = soup.select_one("h2.title-detail")
            if title_element:
                title_text = self.clean_text(title_element.get_text(strip=True))

            # Extract only paragraph blocks (avoid duplication)
            paragraph_blocks = soup.select(
                'div.article-content div.page-description div[id="paragraphBlock"]'
            )

            if not paragraph_blocks:

                # Try to extract from div.postbox__content > div.postbox__text
                postbox_text_div = soup.select_one(
                    "div.postbox__content > div.postbox__text"
                )

                if postbox_text_div:
                    paragraphs = postbox_text_div.find_all("div", recursive=False)

                    seen = set()

                    if not paragraphs:
                        main_text = self.clean_text(
                            postbox_text_div.get_text(separator=" ", strip=True)
                        )
                        if main_text:
                            lang = (
                                "khmer" if self.is_khmer_text(main_text) else "english"
                            )
                            content[lang].append(main_text)
                    else:
                        for para in paragraphs:
                            para_text = self.clean_text(
                                para.get_text(separator=" ", strip=True)
                            )
                            if para_text and para_text not in seen:
                                seen.add(para_text)
                                lang = (
                                    "khmer"
                                    if self.is_khmer_text(para_text)
                                    else "english"
                                )
                                content[lang].append(para_text)

                else:
                    logger.warning("Could not find postbox__text div")

                return content

            logger.info(f"Found {len(paragraph_blocks)} paragraph blocks")

            # Extract text from each paragraph block
            all_texts = []
            for block in paragraph_blocks:
                # Get text from the paragraph inside the block
                paragraph = block.find("p")
                if paragraph:
                    text = paragraph.get_text(strip=True)
                    if text:
                        cleaned_text = self.clean_text(text)
                        if cleaned_text and len(cleaned_text) >= 3:
                            all_texts.append(cleaned_text)

            # Find separator (should be "- - -")
            separator_index = -1
            for i, text in enumerate(all_texts):
                if text.strip() in self.special_characters:
                    separator_index = i
                    logger.info(f"Found separator at index {i}: '{text.strip()}'")
                    break

            if separator_index != -1:
                # Split content at separator
                khmer_texts = all_texts[:separator_index]
                english_texts = all_texts[separator_index + 1 :]

                # Remove empty and placeholder texts
                khmer_texts = [
                    t for t in khmer_texts if t.strip() and t.strip() != "..."
                ]
                english_texts = [
                    t for t in english_texts if t.strip() and t.strip() != "..."
                ]

                # Add title to appropriate language
                if title_text:
                    if self.is_khmer_text(title_text):
                        content["khmer"].insert(0, title_text)
                    else:
                        content["english"].insert(0, title_text)

                # Add content
                content["khmer"].extend(khmer_texts)
                content["english"].extend(english_texts)

                # Count the number of texts in each language
                total_khmer = len(content["khmer"])
                total_english = len(content["english"])

                # If there's one more Khmer entry, it might be a heading
                # Insert an empty placeholder in English to keep alignment
                if total_khmer == total_english + 1:
                    content["english"].insert(0, "")

                    logger.info(
                        f"Final extraction: {len(content['english'])} English, {len(content['khmer'])} Khmer texts"
                    )

                    return content

            else:
                # Fallback: no separator found, use language detection
                logger.info("No separator found, using language detection")

                # Add title first
                if title_text:
                    if self.is_khmer_text(title_text):
                        content["khmer"].append(title_text)
                    else:
                        content["english"].append(title_text)

                # Process other texts
                for text in all_texts:
                    if text.strip() and text.strip() != "...":
                        if self.is_khmer_text(text):
                            content["khmer"].append(text)
                        else:
                            content["english"].append(text)

            logger.info(
                f"Final extraction: {len(content['english'])} English, {len(content['khmer'])} Khmer texts"
            )

            # Handle case where we have different numbers of English and Khmer texts
            if content["english"] and content["khmer"]:
                if len(content["english"]) != len(content["khmer"]) and len(
                    content["english"]
                ) > len(content["khmer"]):
                    logger.warning(
                        "Different number of English and Khmer texts, aligning them"
                    )
                    # Align texts using KhmerEnglishAligner
                    content = self.align_texts(content["english"], content["khmer"])

        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")

        return content

    def align_texts(self, english_texts: List[str], khmer_texts: List[str]):
        """
        Align English and Khmer sentence lists using KhmerEnglishAligner.

        Args:
            english_texts: List of English sentences.
            khmer_texts: List of Khmer sentences.

        Returns:
            Dictionary with aligned 'english' and 'khmer' sentence lists.
        """
        data = {"english": english_texts, "khmer": khmer_texts}

        return self.aligner.align(data)

    async def _scrape_url_internal(
        self, session: aiohttp.ClientSession, url: str
    ) -> Optional[Dict[str, List[str]]]:
        """
        Internal method to scrape URL without retry logic
        """
        logger.info(f"Scraping URL: {url}")

        # Create timeout for this specific request
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        async with session.get(url, timeout=timeout) as response:
            if response.status != 200:
                logger.warning(f"URL {url} returned status {response.status}")
                return None

            # Check if we got HTML content
            content_type = response.headers.get("content-type", "").lower()
            if "html" not in content_type:
                logger.warning(f"URL {url} does not return HTML content")
                return None

            html = await response.text()

            # Parse HTML with optimized parser
            soup = BeautifulSoup(html, "html.parser")

            # Extract content using optimized method
            content = self.extract_content(soup)
            logger.info(
                f"Extracted {len(content['english'])} English and {len(content['khmer'])} Khmer texts"
            )

            await asyncio.sleep(self.delay)

            return content

    async def scrape_url_with_semaphore(
        self, session: aiohttp.ClientSession, url: str
    ) -> Optional[Dict[str, List[str]]]:
        """
        Scrape URL with semaphore to limit concurrent requests
        """
        async with self.semaphore:
            return await self.scrape_url(session, url)

    async def scrape_url(
        self, session: aiohttp.ClientSession, url: str
    ) -> Optional[Dict[str, List[str]]]:
        """
        Scrape content from a single URL with retry mechanism

        Args:
            session: aiohttp ClientSession
            url: URL to scrape

        Returns:
            Dictionary with extracted content or None if failed
        """

        result = await self._retry_with_backoff(self._scrape_url_internal, session, url)

        # If all retries failed, make sure it's logged
        if result is None:
            logger.error(f"URL {url} failed after {self.max_retries} retries")
        else:
            logger.info(f"URL {url} scraped successfully")
        

        return result

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
            if "moc.gov.kh" not in parsed.netloc:
                logger.warning(f"URL {url} is not from moc.gov.kh domain")
                # Don't return False here to allow other domains if needed

            return True

        except Exception:
            return False

    async def scrape_multiple_urls_batched(
        self, urls: List[str], batch_size: int = 50
    ) -> List[Dict]:
        """
        Scrape URLs in batches to prevent memory issues and rate limiting
        """
        results = []
        total_batches = (len(urls) + batch_size - 1) // batch_size

        # Configure connection limits
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=10,  # Connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
        )

        timeout = aiohttp.ClientTimeout(
            total=60,  # Total timeout
            connect=10,  # Connection timeout
            sock_read=30,  # Socket read timeout
        )

        async with aiohttp.ClientSession(
            headers=self.headers, connector=connector, timeout=timeout
        ) as session:

            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, len(urls))
                batch_urls = urls[start_idx:end_idx]

                logger.info(
                    f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_urls)} URLs)"
                )

                # Process batch with semaphore
                tasks = []
                for url in batch_urls:
                    if not self.validate_url(url):
                        logger.error(f"Invalid URL: {url}")
                        results.append(
                            {
                                "id": start_idx + len(tasks) + 1,
                                "url": url,
                                "english_texts": [],
                                "khmer_texts": [],
                            }
                        )
                        continue

                    tasks.append(self.scrape_url_with_semaphore(session, url))

                try:
                    # Process batch with timeout
                    batch_results = await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=300,  # 5 minutes per batch
                    )

                    # Process results
                    task_idx = 0
                    for i, url in enumerate(batch_urls):
                        if not self.validate_url(url):
                            continue

                        result = batch_results[task_idx]
                        task_idx += 1

                        if isinstance(result, Exception):
                            logger.error(f"Error processing {url}: {result}")
                            content = {"english": [], "khmer": []}
                        elif result is None:
                            content = {"english": [], "khmer": []}
                        else:
                            content = result

                        results.append(
                            {
                                "id": start_idx + i + 1,
                                "url": url,
                                "english_texts": content["english"],
                                "khmer_texts": content["khmer"],
                            }
                        )

                except asyncio.TimeoutError:
                    logger.error(f"Batch {batch_num + 1} timed out")
                    # Add empty results for failed batch
                    for i, url in enumerate(batch_urls):
                        results.append(
                            {
                                "id": start_idx + i + 1,
                                "url": url,
                                "english_texts": [],
                                "khmer_texts": [],
                            }
                        )

                # Add delay between batches
                if batch_num < total_batches - 1:
                    await asyncio.sleep(self.delay * 2)

        return results

    async def scrape_multiple_urls(self, urls: List[str]) -> List[Dict]:
        """
        Scrape content from multiple URLs with optimized processing

        Args:
            urls: List of URLs to scrape

        Returns:
            List of dictionaries with scraped content
        """
        results = []

        async with aiohttp.ClientSession(headers=self.headers) as session:

            tasks = []

            for i, url in enumerate(urls, 1):

                # Validate URL
                if not self.validate_url(url):
                    logger.error(f"Invalid URL: {url}")
                    results.append(
                        {"id": i, "url": url, "english_texts": [], "khmer_texts": []}
                    )
                    continue
                tasks.append(self.scrape_url(session, url))

            # Scrape content
            responses = await asyncio.gather(*tasks)

            idx = 1
            for url, content in zip(urls, responses):

                if content:

                    results.append(
                        {
                            "id": idx,
                            "url": url,
                            "english_texts": content["english"],
                            "khmer_texts": content["khmer"],
                        }
                    )
                else:
                    results.append(
                        {"id": idx, "url": url, "english_texts": [], "khmer_texts": []}
                    )
                idx += 1

        return results

    async def save_to_csv(
        self, results: List[Dict], filename: str = "output/scraped_content.csv"
    ):
        """
        Save scraped results to CSV file with unique ID for each sentence pair

        Args:
            results: List of scraped content dictionaries
            filename: Output CSV filename
        """
        try:
            # Ensure output directory exists
            output_path = Path(filename)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Create CSV content in memory first
            buffer = io.StringIO()
            fieldnames = ["ID", "English_Text", "Khmer_Text"]
            writer = csv.DictWriter(buffer, fieldnames=fieldnames)

            # Write header
            writer.writeheader()

            # Initialize global row counter for unique IDs
            row_id = 1
            # Process each result
            for result in results:
                english_texts = result["english_texts"]
                khmer_texts = result["khmer_texts"]

                # Handle the case where we have different numbers of English and Khmer texts
                max_texts = max(len(english_texts), len(khmer_texts))

                if max_texts == 0:
                    # No content found - still assign an ID
                    writer.writerow(
                        {"ID": row_id, "English_Text": "", "Khmer_Text": ""}
                    )
                    row_id += 1
                else:
                    # Write each text pair with unique ID
                    for i in range(max_texts):
                        english_text = (
                            english_texts[i] if i < len(english_texts) else ""
                        )
                        khmer_text = khmer_texts[i] if i < len(khmer_texts) else ""

                        writer.writerow(
                            {
                                "ID": row_id,
                                "English_Text": english_text,
                                "Khmer_Text": khmer_text,
                            }
                        )
                        row_id += 1

            # Write all content to file at once
            csv_content = buffer.getvalue()
            buffer.close()

            async with aiofiles.open(
                filename, "w", newline="", encoding="utf-8"
            ) as csvfile:
                await csvfile.write(csv_content)

            logger.info(f"Results saved to {filename}")

        except Exception as e:
            logger.error(f"Error saving to CSV: {str(e)}")
            raise

    def save_to_db(self, results: List[Dict]):
        """
        Save scraped results to the database using SQLAlchemy ORM.
        Args:
            results: List of scraped content dictionaries
        """
        session = Session()
        try:
            for result in results:
                english_texts = result["english_texts"]
                khmer_texts = result["khmer_texts"]
                max_texts = max(len(english_texts), len(khmer_texts))
                if max_texts == 0:
                    session.add(ScrapedContent(english_text="", khmer_text=""))
                else:
                    for i in range(max_texts):
                        english_text = (
                            english_texts[i] if i < len(english_texts) else ""
                        )
                        khmer_text = khmer_texts[i] if i < len(khmer_texts) else ""
                        session.add(
                            ScrapedContent(
                                english_text=english_text, khmer_text=khmer_text
                            )
                        )
            session.commit()
            logger.info("Results saved to the database.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving to database: {str(e)}")
            raise "Error saving to database"
        finally:
            session.close()


def get_urls_from_user() -> List[str]:
    """
    Get URLs from user input

    Returns:
        List of URLs to scrape
    """
    urls = []

    print("Enter URLs to scrape:")
    print("• One URL per line")
    print("• Press Enter twice when finished")
    print(
        "• For pages with multiple links (ending in .kh), all links will be extracted"
    )
    print("\nExamples:")
    print("  https://www.moc.gov.kh/news/3122")
    print("  https://cambodiaip.gov.kh")
    print("=" * 50)

    while True:
        url = input("URL: ").strip()

        if not url:
            if urls:  # If we have at least one URL, break
                break
            else:
                print("Please enter at least one URL.")
                continue

        # If the URL ends with .kh, use extract_link to get all links from the page
        if url.endswith(".kh"):
            extracted = extract_link(url)
            if extracted:
                logging.info(f"Extracted {len(extracted)} links from {url}")
                urls.extend(extracted)
            else:
                logging.warning(f"No links found on {url}")
        else:
            urls.append(url)

    return urls


async def main():
    """
    Main function to run the optimized scraper
    """
    print("=== Ministry of Commerce Cambodia Web Scraper (Optimized) ===")
    print("This tool scrapes content and separates English and Khmer text.")
    print()

    try:
        # Get URLs from user
        urls = get_urls_from_user()

        if not urls:
            print("No URLs provided. Exiting.")
            return

        print(f"\nWill scrape {len(urls)} URL(s):")
        for i, url in enumerate(urls, 1):
            print(f"  {i}. {url}")
        if len(urls) > 100:
            print(f"  ... and {len(urls) - 100} more URLs")

        # Ask for batch size if many URLs
        batch_size = 50
        if len(urls) > 100:
            print(f"\nLarge number of URLs detected ({len(urls)})")
            batch_input = input(f"Enter batch size (default: {batch_size}): ").strip()
            if batch_input.isdigit():
                batch_size = int(batch_input)

        # Ask user where to save results
        print("=" * 50)
        print("\nWhere would you like to save the results?")
        print("1. CSV file (default)")
        print("2. Database (SQLite)")
        save_choice = input("Enter your choice (1 or 2): ").strip()
        print("")
        print("=" * 50)

        # Initialize optimized scraper
        print("\nInitializing optimized scraper...")
        scraper = MoCWebScraper(delay=1.0, timeout=30, max_concurrent=10)

        print(f"Starting scraping process with batch size {batch_size}...")
        start_time = time.time()

        # Use batched scraping for large URL lists
        if len(urls) > 50:
            results = await scraper.scrape_multiple_urls_batched(urls, batch_size)
        else:
            results = await scraper.scrape_multiple_urls(urls)

        if save_choice == "2":
            # Save to database
            filename = "databases/scraped_content.db"
            scraper.save_to_db(results)
        else:
            # Save to CSV
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            csv_filename = f"output/scraped_content_{timestamp}.csv"
            filename = csv_filename
            await scraper.save_to_csv(results, csv_filename)

        end_time = time.time()
        processing_time = end_time - start_time

        # Print summary
        total_english = sum(len(r["english_texts"]) for r in results)
        total_khmer = sum(len(r["khmer_texts"]) for r in results)

        print(f"\n" + "=" * 50)
        print(f"\t SCRAPING SUMMARY")
        print(f"=" * 50)
        print(f"URLs processed: {len(results)}")
        print(f"Total English texts: {total_english}")
        print(f"Total Khmer texts: {total_khmer}")
        print(f"Processing time: {processing_time:.2f} seconds")
        print(f"Results saved to: {filename}")

    except KeyboardInterrupt:
        print("\nScraping interrupted by user.")
    except Exception as e:
        logger.error(f"Unexpected error in main: {str(e)}")
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
