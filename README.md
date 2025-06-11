# Conclusion!


## How to Run the Application

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the application:

```bash
python main.py
```

## Project Summary

This project is designed to scrape all possible news links from [https://uat.moc.gov.kh](https://uat.moc.gov.kh).  
To accomplish this, I developed a script called `DynamicLinkScrapping.py`, which scrolls through the site's infinite scroll feature and extracts all news article links.

- **Scraping time:** ~6 minutes  
- **Processing time (after pasting links into `main.py`):** ~28.57 seconds  
- **Total time:** ~428.57 seconds  

In comparison, using a brute-force method results in a processing time of approximately **35.46 seconds**.

## Features

- **Flexible Storage Options**  
  This project uses an Object-Relational Mapping (ORM) system to support multiple storage backends.

  You can choose between:
  - **Default:** CSV file
  - **SQLite or other database engines:**  
    Create a `.env` file and set the following environment variable:

    ```env
    DATABASE_ENGINE=your_database_url_here
    ```

  This allows easy switching between local file storage and database storage.

## Known Issue & Solution

There is a specific issue with the page [https://moc.gov.kh/news/3126](https://moc.gov.kh/news/3126):  
The article does not include an English translation for the topic, which results in a mismatch between the Khmer and English content.

### Solution

To ensure the content remains aligned, a check was added to insert an empty string into the English list when the number of Khmer elements exceeds the number of English ones. This ensures both lists stay balanced and aligned properly during processing.

**Relevant code (lines 238-246):**

```python
def extract_content(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
    # existing code ...

    english_texts = content['english']
    khmer_texts = content['khmer']

    total_texts = len(english_texts) + len(khmer_texts)

    # Check if the total number of responses is odd and khmer > english
    if total_texts % 2 == 1 and len(khmer_texts) > len(english_texts):
        # Insert empty string at index 0 in english_texts
        english_texts.insert(0, "")
```

## Additional Handling for Title Extraction

Some pages do not wrap the title inside an `<h2>` element; instead, the title is placed directly inside a `<div>`.  
To address this inconsistency, the following logic was added to ensure the title is consistently captured:

**Relevant code (lines 140–145):**

```python
def extract_content(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
    # existing code ...

    if title_element is None:
        # Check for <div> with class 'mobile-title-detail'
        mobile_title_element = soup.select_one('div.mobile-title-detail')
        if mobile_title_element:
            title_text = self.clean_text(mobile_title_element.get_text(strip=True))
            title_element = mobile_title_element
