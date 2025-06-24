import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import logging
from urllib.parse import urlparse
from typing import List, Dict, Tuple, Optional
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

    
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

class MoFAWebScraper:
    """
    Web scraper for Ministry of Foreign Affairs and International Cooperation website
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
        self.session = requests.Session()
        
        # Pre-compile regex patterns for better performance
        self.whitespace_pattern = re.compile(r'\s+')
        self.dash_pattern = re.compile(r'^\s*[-\s]*\s*$')
        self.dot_pattern = re.compile(r'^\s*[.]\s*$')
        self.non_word_pattern = re.compile(r'[^\w\s]')
        
        # Set headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Cookie': 'Language=1',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
    
    def is_khmer_text(self, text: str) -> bool:
        """
        Determine if text contains primarily Khmer characters using langdetect
        
        Args:
            text: Text to analyze
            
        Returns:
            True if text is primarily Khmer, False if English/Latin
        """
        if not text or len(text.strip()) < 3:
            return False
        
        try:
            # Use langdetect to identify language
            detected_lang = detect(text)
            return detected_lang == 'km'  # 'km' is the language code for Khmer
        except LangDetectException:
            # Fallback to Unicode range detection
            return self._fallback_khmer_detection(text)
    
    def _fallback_khmer_detection(self, text: str) -> bool:
        """
        Fallback method using Unicode ranges
        """
        khmer_count = 0
        total_chars = 0
        
        for char in text:
            if char.isalpha():
                total_chars += 1
                if 0x1780 <= ord(char) <= 0x17FF:  # Khmer Unicode range
                    khmer_count += 1
        
        if total_chars == 0:
            return False
        
        return (khmer_count / total_chars) > 0.3
    
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
        Now extracts all heading elements as titles and content from div, main, div, and p elements
        Excludes footer content
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            Dictionary with paired 'english' and 'khmer' text lists
        """
        content = {'english': [], 'khmer': []}
        
        try:
            # Remove footer elements
            for footer in soup.find_all(['footer', 'div'], class_=lambda x: x and 'footer' in str(x).lower()):
                footer.decompose()
            for element in soup.find_all(['div'], id=lambda x: x and 'footer' in str(x).lower()):
                element.decompose()
                
            # Extract all heading elements (h1, h2, h3, h4) as titles
            heading_selectors = ['h4']
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
                # 'p'              # All paragraph elements
                'div.post-content p'  # All <p> elements inside <div class="post-content">
            ]
            
            # Process each selector type
            for selector in content_selectors:
                elements = soup.select(selector)

                # Skip the first p element if we're processing p tags
                if selector == 'div.post-content p' and elements:
                    elements = elements[1:]  # Skip the first p element
                    logger.info(f"Skipped first p element, processing {len(elements)} remaining p elements")
                
                            
                for element in elements:
                    # # Skip if this element is already processed as a heading
                    # if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    #     continue
                    
                    # # Skip if element is within footer (additional safety check)
                    # if element.find_parent(['footer']) or element.find_parent(class_=lambda x: x and 'footer' in str(x).lower()):
                    #     continue
                    
                    # Get text content
                    text = element.get_text(strip=True)
                    
                    if text:
                        cleaned_text = self.clean_text(text)
                        if cleaned_text and len(cleaned_text) >= 3:
                            # Avoid duplicates
                            if cleaned_text not in all_texts:
                                all_texts.append(cleaned_text)
            
            logger.info(f"Total extracted texts: {len(all_texts)}")
            
            # Process other texts
            for text in all_texts:
                if self.is_khmer_text(text):
                    content['khmer'].append(text)
                else:
                    content['english'].append(text)
            
            logger.info(f"Final extraction: {len(content['english'])} English, {len(content['khmer'])} Khmer texts")
            
        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")
            
        return content
    
    def scrape_url(self, url: str) -> Optional[Dict[str, List[str]]]:
        """
        Scrape content from a single URL with optimized processing
        
        Args:
            url: URL to scrape
            
        Returns:
            Dictionary with extracted content or None if failed
        """
        try:
            logger.info(f"Scraping URL: {url}")
            
            # Add delay to be respectful to the server
            time.sleep(self.delay)
            
            # Make the request
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Check if we got HTML content
            content_type = response.headers.get('content-type', '').lower()
            if 'html' not in content_type:
                logger.warning(f"URL {url} does not return HTML content")
                return None
            
            # Parse HTML with optimized parser
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract content using optimized method
            content = self.extract_content(soup)
            
            logger.info(f"Extracted {len(content['english'])} English and {len(content['khmer'])} Khmer texts")
            
            return content
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {url}: {str(e)}")
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
            if 'mfaic.gov.kh' not in parsed.netloc:
                logger.warning(f"URL {url} is not from mfaic.gov.kh domain")
                # Don't return False here to allow other domains if needed
                
            return True
            
        except Exception:
            return False
    
    def scrape_multiple_urls(self, urls: List[str]) -> List[Dict]:
        """
        Scrape content from multiple URLs with optimized processing
        
        Args:
            urls: List of URLs to scrape
            
        Returns:
            List of dictionaries with scraped content
        """
        results = []
        
        for i, url in enumerate(urls, 1):
            logger.info(f"Processing URL {i}/{len(urls)}: {url}")
            
            # Validate URL
            if not self.validate_url(url):
                logger.error(f"Invalid URL: {url}")
                continue
            
            # Scrape content
            content = self.scrape_url(url)
            
            if content:
                results.append({
                    'id': i,
                    'url': url,
                    'english_texts': content['english'],
                    'khmer_texts': content['khmer']
                })
            else:
                logger.warning(f"Failed to scrape content from {url}")
                # Add empty result to maintain ID sequence
                results.append({
                    'id': i,
                    'url': url,
                    'english_texts': [],
                    'khmer_texts': []
                })
        
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


def get_urls_from_user() -> List[str]:
    """
    Get URLs from user input
    
    Returns:
        List of URLs to scrape
    """
    urls = []
    
    print("Enter URLs to scrape (one per line, press Enter twice to finish):")
    print("Example: https://www.mfaic.gov.kh/Posts/2025-06-21-News-Her-Excellency-PHEN-Savny-receives-a-courtesy-call-by-His-Excellency-Suren-Baghdasaryan-10-24-59")
    
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

def main():
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
        
        # Get output filename
        filename = input("\nEnter output CSV filename (default: scraped_content.csv): ").strip()
        if not filename:
            filename = 'scraped_content.csv'
        
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        # Initialize optimized scraper
        print("\nInitializing optimized scraper...")
        scraper = MoFAWebScraper(delay=1.0, timeout=30)
        
        print(f"Starting scraping process...")
        start_time = time.time()
        
        # Scrape all URLs
        results = scraper.scrape_multiple_urls(urls)
        
        # Save results
        scraper.save_to_csv(results, filename)
        
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
    main()