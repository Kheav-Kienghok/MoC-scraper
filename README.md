# Ministry of Foreign Affairs Web Scraper

A Python web scraper designed to extract and process content from the Ministry of Foreign Affairs and International Cooperation (MoFAIC) website of Cambodia. The scraper automatically separates English and Khmer text content and exports structured data to CSV format.

## Features

- **Bilingual Content Extraction**: Automatically detects and separates English and Khmer text


## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the scraper interactively:

```bash
python MoFA.py
```

The script will prompt you to:
1. Enter URLs to scrape (one per line, empty line to finish)
2. Specify output CSV filename (default: scraped_content.csv)

### Example URLs
```
https://www.mfaic.gov.kh/Posts/2025-06-21-News-Her-Excellency-PHEN-Savny-receives-a-courtesy-call-by-His-Excellency-Suren-Baghdasaryan-10-24-59
```


## Logging

The scraper creates detailed logs in `scraper.log` for debugging and monitoring purposes.