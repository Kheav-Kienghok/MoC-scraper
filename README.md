<div align="center">

![Python](https://img.shields.io/badge/Python-3.13-blue?style=for-the-badge&logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-43B02A?style=for-the-badge&logo=selenium&logoColor=white)
![Chrome](https://img.shields.io/badge/Chrome-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white)

![Issues](https://img.shields.io/github/issues/Kheav-Kienghok/MoC-scraper?style=for-the-badge&color=red)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge)

</div>

---
<div align="center">

   <h1>🇰🇭 MoC News Scraper</h1>
</div>

A robust web scraping tool designed to extract and process bilingual (Khmer-English) news articles from the Ministry of Commerce of Cambodia website.

## 🚀 Quick Start

### Prerequisites
- Python 3.13
- pip package manager

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Kheav-Kienghok/MoC-scraper.git
   cd MoC-scraper
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

## 🔗 **Link Extraction**

If you have no links and want to scrape everything from `https://uat.moc.gov.kh/news?category=2` with infinite scroll functionality, use the following command:

```bash
# For comprehensive link extraction with infinite scroll
python DynamicLinkScrapping.py --headless --timeout 30
```

> **Expected Output:** ~400 URL links from the website. If you get significantly fewer links, there may be an internet connection issue.

## 🎛️ **Command Line Options**

The scraper supports various command-line arguments for flexible configuration:

### **Basic Usage**
```bash
# Run with default settings (GUI mode)
python DynamicLinkScrapping.py

# Run the complete pipeline
python main.py
```

### **Available Arguments**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--headless` | Flag | `False` | Run browser in headless mode (no GUI) |
| `--timeout` | Integer | `15` | Timeout in seconds for page loading |
| `--category` | Integer | `2` | News category to scrape |
| `--help` | Flag | - | Show help message and exit |

### **Usage Examples**

```bash
# Run in headless mode (no browser window)
python DynamicLinkScrapping.py --headless

# Run with custom timeout and category
python DynamicLinkScrapping.py --headless --timeout 20 --category 3

# Run with GUI and extended timeout
python DynamicLinkScrapping.py --timeout 30

# Show all available options
python DynamicLinkScrapping.py --help
```

## 📋 Project Overview

This project scrapes bilingual news articles from [https://uat.moc.gov.kh](https://uat.moc.gov.kh) and processes them for structured data extraction. The scraper handles dynamic content loading and aligns Khmer-English text pairs using advanced NLP techniques.

### Key Components

- **`DynamicLinkScrapping.py`**: Handles infinite scroll navigation and link extraction
- **`KhmerEnglishAligner.py`**: Aligns bilingual content using semantic similarity
- **`main.py`**: Orchestrates the scraping and processing pipeline
- **ORM Integration**: Flexible data storage with multiple backend support

## ⚡ Performance Metrics

| Metric | Time |
|--------|------|
| **Link Scraping** | ~6 minutes |
| **Content Processing** | ~28.57 seconds |
| **Total Runtime** | ~6.5 minutes |

> **Note:** Brute-force processing takes approximately 35.46 seconds, making our optimized approach **~20% faster**.

## 🗄️ Storage Options

The project uses an Object-Relational Mapping (ORM) system for flexible data storage:

### Default: CSV File
No configuration needed. Data is automatically saved to CSV format.

### Database Storage
Create a `.env` file in the project root:

```env
DATABASE_ENGINE=sqlite:///news_data.db
# Or use other database URLs:
# DATABASE_ENGINE=postgresql://user:password@localhost/dbname
# DATABASE_ENGINE=mysql://user:password@localhost/dbname
```

**Supported databases:**
- SQLite (recommended for local development)
- PostgreSQL
- MySQL
- Any SQLAlchemy-compatible database

## 🔧 Advanced Features

### Bilingual Content Alignment

The scraper uses the `sentence-transformers/LaBSE` model to align Khmer and English content accurately:

- **Model**: LaBSE (Language-agnostic BERT Sentence Embedding)
- **Similarity Threshold**: Configurable (default: -0.01 acceptable drop)
- **Alignment Strategy**: Semantic similarity-based matching with merge optimization

### Configuration Options

You can customize the alignment behavior:

```python
aligner = KhmerEnglishAligner(
    model_name='sentence-transformers/LaBSE',
    acceptable_negative_diff=-0.01  # Adjust similarity tolerance
)
```

## 🐞 Known Issues & Solutions

### Issue: Paragraph Count Mismatch
**Problem**: Some pages (e.g., [news/2679](https://uat.moc.gov.kh/kh/news/2679)) have unequal numbers of English and Khmer paragraphs.

**Solution**: Implemented semantic alignment using the LaBSE model:
- Matches content based on meaning rather than position
- Merges related paragraphs when beneficial
- Maintains content integrity with configurable similarity thresholds

**Impact**: Slight similarity score drops (~0.01) are acceptable to ensure proper alignment.

## 📁 Project Structure

```
MoC-scraper/
├── main.py                     # Main application entry point
├── DynamicLinkScrapping.py     # Dynamic content scraper
├── KhmerEnglishAligner.py      # Bilingual content aligner
├── requirements.txt            # Python dependencies
├── .env.example                # Environment configuration template
└── README.md                   # This file
```


## 🔍 Usage Examples


### Custom Alignment
```python
from KhmerEnglishAligner import KhmerEnglishAligner

data = {
    'english': ['Hello', 
                'world'],
    'khmer': ['សួស្តី ពិភពលោក']
}

aligner = KhmerEnglishAligner()
result = aligner.align(data)
print(result)
```


## 🆘 Support

If you encounter any issues or have questions:

1. Check the [Issues](../../issues) section
2. Review the test cases for usage examples
3. Ensure all dependencies are properly installed
4. Verify your environment configuration


## 📊 **Data Output Format Structure**

---

### 🗂️ **CSV Schema Definition**

```csv
ID, English_Text, Khmer_Text
```

---


### 📋 **Field Specifications**

| 🔢 **Field** | 📝 **Type** | 📖 **Description** | ⚙️ **Format** | 🎯 **Example** |
|--------------|-------------|-------------------|----------------|----------------|
| **ID** | `Integer` | Unique record identifier | Sequential number | `1`, `2`, `3` |
| **English_Text** | `String` | English paragraph content | UTF-8 encoded, quoted | `"Hello world"` |
| **Khmer_Text** | `String` | Khmer paragraph content | UTF-8 encoded, quoted | `"សួស្តី ពិភពលោក"` |

---

### 📄 **Sample Data Visualization**


```
ID | English_Text                               | Khmer_Text                                       
---|--------------------------------------------|-----------------------------------------
1  | (Phnom Penh): On the morning of Tuesday... | (ភ្នំពេញ)៖ នាព្រឹកថ្ងៃអង្គារ...               
2  | To begin, Her Excellency expressed...      | ជាកិច្ចចាប់ផ្តើម លោកជំទាវរដ្ឋមន្ត្រី...          
3  | In addition to the memorandum...           | ឆ្លៀតក្នុងឱកាសនោះ លោកជំទាវរដ្ឋមន្ត្រី...       
4  | In conclusion, Her Excellency...           | មុននឹងបញ្ចប់ លោកជំទាវរដ្ឋមន្ត្រី...            
```


