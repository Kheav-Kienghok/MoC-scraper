from urllib.parse import urlparse
from typing import List, Dict, Optional
from extract_link import extract_link  
from models.db_models import ScrapedContent, Session
from bs4 import BeautifulSoup
import asyncio
import aiohttp
import csv
import re
import time
import logging
from pprintpp import pprint

# Set up logging for debugging and monitoring
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MoCWebScraper:
    """
    Web scraper for Ministry of Commerce Cambodia website
    Extracts and separates English and Khmer content into structured CSV format
    """
    
    def __init__(self, delay: float = 1.0, timeout: int = 30):
        """
        Initialize the scraper with configuration and compile regex patterns
        
        Args:
            delay: Delay between requests to be respectful to the server
            timeout: Request timeout in seconds
        """
        self.delay = delay
        self.timeout = timeout
        # self.session = requests.Session()
        
        # Pre-compile regex patterns for better performance
        self.whitespace_pattern = re.compile(r'\s+')
        self.dash_pattern = re.compile(r'^\s*[-\s]*\s*$')
        self.dot_pattern = re.compile(r'^\s*[.]\s*$')
        self.non_word_pattern = re.compile(r'[^\w\s]')
        
        # Pre-calculate Unicode ranges for language detection
        self.khmer_range_start = 0x1780
        self.khmer_range_end = 0x1800
        
        # Set headers to mimic a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        
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
        cleaned_text = self.non_word_pattern.sub('', text)
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
            
        # Use pre-compiled patterns for better performance
        text = self.whitespace_pattern.sub(' ', text.strip())
        text = self.dash_pattern.sub('', text)
        text = self.dot_pattern.sub('', text)
        
        return text.strip()
    
    def extract_content(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """
        Fixed content extraction with proper deduplication and separator handling
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            Dictionary with paired 'english' and 'khmer' text lists
        """
        content = {'english': [], 'khmer': []}
        
        try:
            # Extract title separately (it's outside page-description)
            title_text = None
            title_element = soup.select_one('h2.title-detail')
            if title_element:
                title_text = self.clean_text(title_element.get_text(strip=True))
            
            # Extract only paragraph blocks (avoid duplication)
            paragraph_blocks = soup.select('div.article-content div.page-description div[id="paragraphBlock"]')

            if not paragraph_blocks:

                # Try to extract from div.postbox__content > div.postbox__text
                postbox_text_div = soup.select_one('div.postbox__content > div.postbox__text')

                if postbox_text_div:
                    paragraphs = postbox_text_div.find_all('div', recursive=False)

                    seen = set()

                    if not paragraphs:
                        main_text = self.clean_text(postbox_text_div.get_text(separator=' ', strip=True))
                        if main_text:
                            lang = 'khmer' if self.is_khmer_text(main_text) else 'english'
                            content[lang].append(main_text)
                    else:
                        for para in paragraphs:
                            para_text = self.clean_text(para.get_text(separator=' ', strip=True))
                            if para_text and para_text not in seen:
                                seen.add(para_text)
                                lang = 'khmer' if self.is_khmer_text(para_text) else 'english'
                                content[lang].append(para_text)
                                
                else:
                    logger.warning("Could not find postbox__text div")

                return content
                    
            logger.info(f"Found {len(paragraph_blocks)} paragraph blocks")
            
            # Extract text from each paragraph block
            all_texts = []
            for block in paragraph_blocks:
                # Get text from the paragraph inside the block
                paragraph = block.find('p')
                if paragraph:
                    text = paragraph.get_text(strip=True)
                    if text:
                        cleaned_text = self.clean_text(text)
                        if cleaned_text and len(cleaned_text) >= 3:
                            all_texts.append(cleaned_text)
            
            # Find separator (should be "- - -")
            separator_index = -1
            for i, text in enumerate(all_texts):
                if text.strip() in ['- - -', '---', '***', '* * *']:
                    separator_index = i
                    logger.info(f"Found separator at index {i}: '{text.strip()}'")
                    break
            
            if separator_index != -1:
                # Split content at separator
                khmer_texts = all_texts[:separator_index]
                english_texts = all_texts[separator_index + 1:]
                
                # Remove empty and placeholder texts
                khmer_texts = [t for t in khmer_texts if t.strip() and t.strip() != '...']
                english_texts = [t for t in english_texts if t.strip() and t.strip() != '...']
                
                # Add title to appropriate language
                if title_text:
                    if self.is_khmer_text(title_text):
                        content['khmer'].insert(0, title_text)
                    else:
                        content['english'].insert(0, title_text)
                
                # Add content
                content['khmer'].extend(khmer_texts)
                content['english'].extend(english_texts)
                
            else:
                # Fallback: no separator found, use language detection
                logger.info("No separator found, using language detection")
                
                # Add title first
                if title_text:
                    if self.is_khmer_text(title_text):
                        content['khmer'].append(title_text)
                    else:
                        content['english'].append(title_text)

                # Process other texts
                for text in all_texts:
                    if text.strip() and text.strip() != '...':
                        if self.is_khmer_text(text):
                            content['khmer'].append(text)
                        else:
                            content['english'].append(text)
            
            logger.info(f"Final extraction: {len(content['english'])} English, {len(content['khmer'])} Khmer texts")
            
        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")

        english_texts = content['english']
        khmer_texts = content['khmer']

        total_texts = len(english_texts) + len(khmer_texts)

        # Check if the total number of responses is odd and khmer > english
        if total_texts % 2 == 1 and len(khmer_texts) > len(english_texts):
            # Insert empty string at index 0 in english_texts
            english_texts.insert(0, "")
            
        return content

    
    async def scrape_url(self, session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, List[str]]]:
        """
        Scrape content from a single URL with optimized processing
        
        Args:
            url: URL to scrape
            
        Returns:
            Dictionary with extracted content or None if failed
        """

        try:
            logger.info(f"Scraping URL: {url}")

            async with session.get(url, timeout=self.timeout) as response:

                if response.status != 200:
                    logger.warning(f"URL {url} returned status {response.status}")
                    return None
                
                # Check if we got HTML content
                content_type = response.headers.get('content-type', '').lower()
                if 'html' not in content_type:
                    logger.warning(f"URL {url} does not return HTML content")
                    return None
                
                html = await response.text()

                # Parse HTML with optimized parser
                soup = BeautifulSoup(html, 'html.parser')

                # Extract content using optimized method
                content = self.extract_content(soup)
                logger.info(f"Extracted {len(content['english'])} English and {len(content['khmer'])} Khmer texts")

                await asyncio.sleep(self.delay)

                return content
        
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
            if 'moc.gov.kh' not in parsed.netloc:
                logger.warning(f"URL {url} is not from moc.gov.kh domain")
                # Don't return False here to allow other domains if needed
                
            return True
            
        except Exception:
            return False
    
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
                    results.append({
                        'id': i,
                        'url': url,
                        'english_texts': [],
                        'khmer_texts': []
                    })
                    continue
                tasks.append(self.scrape_url(session, url))

            # Scrape content
            responses = await asyncio.gather(*tasks)
            
            idx = 1
            for url, content in zip(urls, responses):

                if content:

                    results.append({
                        'id': idx,
                        'url': url,
                        'english_texts': content['english'],
                        'khmer_texts': content['khmer']
                    })
                else:
                    results.append({
                        'id': idx,
                        'url': url,
                        'english_texts': [],
                        'khmer_texts': []
                    })
                idx += 1
        
        return results

    def save_to_csv(self, results: List[Dict], filename: str = 'scraped_content.csv'):
        """
        Save scraped results to CSV file with unique ID for each sentence pair
        
        Args:
            results: List of scraped content dictionaries
            filename: Output CSV filename
        """
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['ID', 'English_Text', 'Khmer_Text']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header
                writer.writeheader()
                
                # Initialize global row counter for unique IDs
                row_id = 1
                # Process each result
                for result in results:
                    english_texts = result['english_texts']
                    khmer_texts = result['khmer_texts']
                    
                    # Handle the case where we have different numbers of English and Khmer texts
                    max_texts = max(len(english_texts), len(khmer_texts))
                    
                    if max_texts == 0:
                        # No content found - still assign an ID
                        writer.writerow({
                            'ID': row_id,
                            'English_Text': '',
                            'Khmer_Text': ''
                        })
                        row_id += 1
                    else:
                        # Write each text pair with unique ID
                        for i in range(max_texts):
                            english_text = english_texts[i] if i < len(english_texts) else ''
                            khmer_text = khmer_texts[i] if i < len(khmer_texts) else ''
                            
                            writer.writerow({
                                'ID': row_id,
                                'English_Text': english_text,
                                'Khmer_Text': khmer_text
                            })
                            row_id += 1
            
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
            row_id = 1
            for result in results:
                english_texts = result['english_texts']
                khmer_texts = result['khmer_texts']
                max_texts = max(len(english_texts), len(khmer_texts))
                if max_texts == 0:
                    session.add(ScrapedContent(
                        english_text='',
                        khmer_text=''
                    ))
                else:
                    for i in range(max_texts):
                        english_text = english_texts[i] if i < len(english_texts) else ''
                        khmer_text = khmer_texts[i] if i < len(khmer_texts) else ''
                        session.add(ScrapedContent(
                            english_text=english_text,
                            khmer_text=khmer_text
                        ))
            session.commit()
            logger.info("Results saved to the database.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving to database: {str(e)}")
            raise
        finally:
            session.close()


def get_urls_from_user() -> List[str]:
    """
    Get URLs from user input
    
    Returns:
        List of URLs to scrape
    """
    urls = []
    
    print("Enter URLs to scrape (one per line, press Enter twice to finish):")
    print("Example: https://www.moc.gov.kh/news/3122")
    print("Or enter a page with multiple links (e.g., https://cambodiaip.gov.kh)")
    
    while True:
        url = input("URL: ").strip()
        
        if not url:
            if urls:  # If we have at least one URL, break
                break
            else:
                print("Please enter at least one URL.")
                continue


        # If the URL ends with .kh, use extract_link to get all links from the page
        if url.endswith('.kh'):
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
    
        # Ask user where to save results
        print("\nWhere would you like to save the results?")
        print("1. CSV file (default)")
        print("2. Database (SQLite)")
        save_choice = input("Enter your choice (1 or 2): ").strip()
        
        # Initialize optimized scraper
        print("\nInitializing optimized scraper...")
        scraper = MoCWebScraper(delay=1.0, timeout=30)
        
        print(f"Starting scraping process...")
        start_time = time.time()
        
        # Scrape all URLs
        results = await scraper.scrape_multiple_urls(urls)

        if save_choice == '2':
            # Save to database
            filename = "databases/scraped_content.db"
            scraper.save_to_db(results)
        else:
            # Save to CSV
            filename = input("\nEnter output CSV filename (default: scraped_content.csv): ").strip()
            if not filename:
                filename = 'scraped_content.csv'
            if not filename.endswith('.csv'):
                filename += '.csv'
            scraper.save_to_csv(results, filename)
        
        # Save results
        # scraper.save_to_csv(results, filename)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Print summary
        total_english = sum(len(r['english_texts']) for r in results)
        total_khmer = sum(len(r['khmer_texts']) for r in results)
        
        print(f"\n=== Scraping Complete ===")
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