# Scraping Ebay

This project contains a Scrapy spider for collecting product data from eBay.

## Installation

Install the required dependencies using pip:

```bash
pip install scrapy Pillow
```

Alternatively you can install from `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Running the spider

From this directory run:

```bash
scrapy crawl ebay -a search="tshirt" -a pages=1
```

Replace the `search` and `pages` parameters as needed.
