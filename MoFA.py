from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import List, Dict, Optional
import aiohttp
import asyncio
import csv
import re
import time
import logging
import sys

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log", encoding="utf-8"),
    ],
)

# Set the console handler to use UTF-8 encoding
for handler in logging.getLogger().handlers:
    if isinstance(handler, logging.StreamHandler):
        handler.stream = open(
            sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1
        )
        break

logger = logging.getLogger(__name__)


class MoFAWebScraper:
    """
    Web scraper for Ministry of Foreign Affairs and International Cooperation website
    Extracts and separates English and Khmer content into structured CSV format
    """

    def __init__(self, delay: float = 1.0, timeout: int = 30, language: str = "1"):
        """
        Initialize the scraper with configuration and compile regex patterns

        Args:
            delay: Delay between requests to be respectful to the server
            timeout: Request timeout in seconds
            language: Language setting for the website
        """
        self.delay = delay
        self.timeout = timeout
        self.language = language

        # Pre-compile regex patterns for better performance
        self.whitespace_pattern = re.compile(r"\s+")
        self.dash_pattern = re.compile(r"^\s*[-\s]*\s*$")
        self.dot_pattern = re.compile(r"^\s*[.]\s*$")
        self.non_word_pattern = re.compile(r"[^\w\s]")

        # Headers to mimic a real browser
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Cookie": f"Language={self.language}",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

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

                for heading in headings:
                    heading_text = self.clean_text(heading.get_text(strip=True))
                    if heading_text and len(heading_text) >= 3:
                        all_texts.append(heading_text)            # Extract content from p elements
            content_selectors = [
                "div.post-content p",  # All <p> elements inside <div class="post-content">
                "span:not(.header-title-en):not(.header-title-km)"  # All span elements except header titles
            ]

            # Process each selector type
            for selector in content_selectors:
                elements = soup.select(selector)

                # Skip the first p element if we're processing p tags
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
                        if cleaned_text and len(cleaned_text) >= 3:                            # Avoid duplicates
                            if cleaned_text not in all_texts:
                                all_texts.append(cleaned_text)

            logger.info(f"Total extracted texts: {len(all_texts)}")
            
            # Separate content by language detection instead of just language setting
            english_texts = []
            khmer_texts = []
            
            for text in all_texts:
                lang = self.detect_language(text)
                if lang == 'khmer':
                    khmer_texts.append(text)
                elif lang == 'english':
                    english_texts.append(text)
                else:  # mixed content
                    # For mixed content, add to both if scraping mode allows
                    if self.language == "3":  # Khmer mode - prefer Khmer
                        khmer_texts.append(text)
                    else:  # English mode - prefer English
                        english_texts.append(text)
            
            # Join Khmer sentences properly if we have Khmer content
            if khmer_texts:
                joined_khmer = self.join_khmer_sentences(khmer_texts)
                content["khmer"] = joined_khmer
            else:
                content["khmer"] = []
                
            content["english"] = english_texts

            logger.info(
                f"Final extraction: {len(content['english'])} English, {len(content['khmer'])} Khmer texts"
            )

        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")

        return content

    async def scrape_url(self, session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, List[str]]]:
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
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
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
            headers=self.headers,
            connector=connector,
            timeout=timeout
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
                            {"id": i, "url": url, "english_texts": [], "khmer_texts": []}
                        )
                except Exception as e:
                    logger.error(f"Error processing {url}: {str(e)}")
                    results.append(
                        {"id": i, "url": url, "english_texts": [], "khmer_texts": []}
                    )

        return results

    @staticmethod
    def save_combined_to_csv(english_results: List[Dict], khmer_results: List[Dict], filename: str = "scraped_content.csv"):
        """
        Save combined English and Khmer results to CSV file with unique ID for each sentence pair

        Args:
            english_results: List of English scraped content dictionaries
            khmer_results: List of Khmer scraped content dictionaries
            filename: Output CSV filename
        """
        try:
            with open(filename, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = ["ID", "English_Text", "Khmer_Text"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # Write header
                writer.writeheader()

                # Initialize global row counter for unique IDs
                row_id = 1

                # Process each URL's results (assuming both lists have same length and order)
                max_results = max(len(english_results), len(khmer_results))
                
                for i in range(max_results):
                    # Get English and Khmer results for the same URL
                    english_result = english_results[i] if i < len(english_results) else {"english_texts": []}
                    khmer_result = khmer_results[i] if i < len(khmer_results) else {"khmer_texts": []}
                    
                    english_texts = english_result.get("english_texts", [])
                    khmer_texts = khmer_result.get("khmer_texts", [])

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
                        for j in range(max_texts):
                            english_text = english_texts[j] if j < len(english_texts) else ""
                            khmer_text = khmer_texts[j] if j < len(khmer_texts) else ""

                            writer.writerow(
                                {
                                    "ID": row_id,
                                    "English_Text": english_text,
                                    "Khmer_Text": khmer_text,
                                }
                            )
                            row_id += 1

            logger.info(f"Combined results saved to {filename}")

        except Exception as e:
            logger.error(f"Error saving combined CSV: {str(e)}")
            raise

    def join_khmer_sentences(self, data: List[str]) -> List[str]:
        """
        Join Khmer sentence fragments that are split across multiple elements.
        Khmer sentences typically end with "។" character.
        Only processes text that contains Khmer characters.

        Args:
            data: List of text fragments

        Returns:
            List of properly joined Khmer sentences
        """
        # Filter to only include text with Khmer characters
        khmer_texts = [text for text in data if self.detect_language(text) == 'khmer']
        
        if not khmer_texts:
            return []
        
        # Check if there are any Khmer sentence endings in the data
        has_khmer_endings = any("។" in item for item in khmer_texts)
        
        # If no Khmer sentence endings found, return data as-is
        if not has_khmer_endings:
            return khmer_texts
        
        result = []
        temp = ""

        # Skip the first element (topic/title) and process the rest
        items_to_process = khmer_texts[1:] if len(khmer_texts) > 1 else []
        
        # Add the first element (topic) as is if it exists
        if len(khmer_texts) > 0:
            result.append(khmer_texts[0])

        for item in items_to_process:
            item = item.strip()
            if not item.endswith("។"):
                temp += item + " "
            else:
                if temp:
                    result.append(temp + item)
                    temp = ""
                else:
                    result.append(item)
                    
        # If temp has leftover sentence parts
        if temp:
            result.append(temp.strip())

        return result

    def detect_language(self, text: str) -> str:
        """
        Detect if text is primarily English, Khmer, or mixed
        
        Args:
            text: Text to analyze
            
        Returns:
            'khmer', 'english', or 'mixed'
        """
        if not text:
            return 'english'
        
        # Count Khmer Unicode characters (U+1780 to U+17FF)
        khmer_chars = sum(1 for char in text if '\u1780' <= char <= '\u17FF')
        # Count English letters
        english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        
        total_chars = len(text.replace(' ', ''))
        
        if total_chars == 0:
            return 'english'
        
        khmer_ratio = khmer_chars / total_chars
        english_ratio = english_chars / total_chars
        
        # If more than 30% Khmer characters, consider it Khmer
        if khmer_ratio > 0.3:
            return 'khmer'
        # If more than 50% English characters, consider it English
        elif english_ratio > 0.5:
            return 'english'
        else:
            return 'mixed'

def get_urls_from_user() -> List[str]:
    """
    Get URLs from user input

    Returns:
        List of URLs to scrape
    """
    urls = []

    print("Enter URLs to scrape (one per line, press Enter twice to finish):")
    print(
        "Example: https://www.mfaic.gov.kh/Posts/2025-06-21-News-Her-Excellency-PHEN-Savny-receives-a-courtesy-call-by-His-Excellency-Suren-Baghdasaryan-10-24-59"
    )

    while True:
        url = input("URL: ").strip()

        if not url:
            if urls:  # If we have at least one URL, break
                break
            else:
                print("Please enter at least one URL.")
                continue

        urls.append(url)

    return urls


async def main():
    """
    Main function to run the optimized scraper with both English and Khmer (async)
    """
    print("=== Ministry of Foreign Affairs & International Cooperation Web Scraper (Async) ===")
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

        # Get output filename
        filename = input(
            "\nEnter output CSV filename (default: scraped_content.csv): "
        ).strip()
        if not filename:
            filename = "scraped_content.csv"

        if not filename.endswith(".csv"):
            filename += ".csv"

        # Initialize scrapers for both languages
        print("\nInitializing scrapers for both English and Khmer...")

        languages = {
            "English": "1",
            "Khmer": "3"
        }

        print(f"Starting async scraping process...")
        start_time = time.time()

        # Create tasks for both languages
        print("Creating concurrent scraping tasks...")
        english_scraper = MoFAWebScraper(delay=1.0, timeout=30, language=languages["English"])
        khmer_scraper = MoFAWebScraper(delay=1.0, timeout=30, language=languages["Khmer"])
        
        # Run both scrapers concurrently
        print("Running English and Khmer scrapers concurrently...")
        english_task = english_scraper.scrape_multiple_urls(urls)
        khmer_task = khmer_scraper.scrape_multiple_urls(urls)
        
        # Wait for both tasks to complete
        english_results, khmer_results = await asyncio.gather(english_task, khmer_task)

        # Save combined results
        print("Combining and saving results...")
        MoFAWebScraper.save_combined_to_csv(english_results, khmer_results, filename)

        end_time = time.time()
        processing_time = end_time - start_time

        # Print summary
        total_english = sum(len(r["english_texts"]) for r in english_results)
        total_khmer = sum(len(r["khmer_texts"]) for r in khmer_results)

        print(f"\n=== Scraping Complete ===")
        print(f"URLs processed: {len(english_results)}")
        print(f"Total English texts: {total_english}")
        print(f"Total Khmer texts: {total_khmer}")
        print(f"Processing time: {processing_time:.2f} seconds")
        print(f"Combined results saved to: {filename}")

    except KeyboardInterrupt:
        print("\nScraping interrupted by user.")
    except Exception as e:
        logger.error(f"Unexpected error in main: {str(e)}")
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
