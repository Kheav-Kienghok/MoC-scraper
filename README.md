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

## 🐞 Known Issue & Solution

A known issue was identified on the page [https://uat.moc.gov.kh/kh/news/2679](https://uat.moc.gov.kh/kh/news/2679), where the number of English paragraphs exceeds that of the Khmer version. To address this, I used `KhmerEnglishAligner` with the `sentence-transformers/LaBSE` model from Hugging Face to align the bilingual content accurately.

In some cases, the similarity score slightly drops after merging paragraphs (by about **0.01**). If the drop is minor and still within an acceptable range, the merged result is retained to ensure alignment consistency.
