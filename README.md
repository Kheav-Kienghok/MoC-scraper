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