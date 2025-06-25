from celery import Celery
from Celery.scraper import MoFAWebScraper
import csv
import os
import logging
import time

# Set up logging for debugging and monitoring
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)

# Set up logging
logger = logging.getLogger(__name__)

app = Celery(
    'mofa_tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1'
)


@app.task(name="scrape.paired_content")
def scrape_and_save_paired_content(urls: list[str], output_file: str = "mofa_paired_output.csv"):
    """
    Scrapes each URL in both English and Khmer versions, pairs content,
    and saves to a CSV file with ID, English text, and Khmer text.
    """
    start_time = time.time()
    logger.info(f"Starting paired content scraping for {len(urls)} URLs at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    scraper_en = MoFAWebScraper(delay=1.0, timeout=30, language_cookie='1')
    scraper_kh = MoFAWebScraper(delay=1.0, timeout=30, language_cookie='3')

    paired_results = []

    for idx, url in enumerate(urls, 1):
        url_start_time = time.time()
        logger.info(f"Processing URL {idx}/{len(urls)}: {url}")
        
        if not scraper_en.validate_url(url):
            logger.warning(f"Skipping invalid URL {idx}: {url}")
            continue
        
        # Scrape English content
        en_scrape_start = time.time()
        en_content = scraper_en.scrape_url_sync(url)
        en_scrape_time = time.time() - en_scrape_start
        logger.info(f"URL {idx} - English scraping completed in {en_scrape_time:.2f} seconds")
        
        # Scrape Khmer content
        kh_scrape_start = time.time()
        kh_content = scraper_kh.scrape_url_sync(url)
        kh_scrape_time = time.time() - kh_scrape_start
        logger.info(f"URL {idx} - Khmer scraping completed in {kh_scrape_time:.2f} seconds")

        en_texts = en_content['english'] if en_content else []
        kh_texts = kh_content['khmer'] if kh_content else []

        url_total_time = time.time() - url_start_time
        logger.info(f"URL {idx} - English texts: {len(en_texts)}, Khmer texts: {len(kh_texts)} - Total URL processing: {url_total_time:.2f} seconds")

        max_len = max(len(en_texts), len(kh_texts))

        for i in range(max_len):
            en_text = en_texts[i] if i < len(en_texts) else ""
            kh_text = kh_texts[i] if i < len(kh_texts) else ""
            paired_results.append({
                'ID': idx,
                'English_Text': en_text,
                'Khmer_Text': kh_text
            })

    end_time = time.time()
    processing_time = end_time - start_time
    logger.info(f"Scraping completed at {time.strftime('%Y-%m-%d %H:%M:%S')} - Total time: {processing_time:.2f} seconds")
    logger.info(f"Total paired results collected: {len(paired_results)}")
    
    # Log performance metrics
    avg_time_per_url = processing_time / len(urls) if urls else 0
    logger.info(f"Performance metrics - Average time per URL: {avg_time_per_url:.2f} seconds")

    try:
        csv_start_time = time.time()
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=['ID', 'English_Text', 'Khmer_Text'])
            writer.writeheader()
            writer.writerows(paired_results)
        
        csv_write_time = time.time() - csv_start_time
        logger.info(f"✅ CSV saved to {output_file} in {csv_write_time:.2f} seconds")
        logger.info(f"📊 Task Summary: {len(paired_results)} entries processed in {processing_time:.2f} seconds total")
        
        return f"Saved {len(paired_results)} entries to {output_file} - Processing time: {processing_time:.2f} seconds"
    except Exception as e:
        logger.error(f"❌ Failed to save CSV: {e}")
        return f"Failed to write CSV: {e} - Processing time: {processing_time:.2f} seconds"