# Ebay SW Pic Scraper 2

This repository contains two approaches for downloading images from eBay listings.

- **scraping-ebay-1.0.3** – a Scrapy project.
- **LSW_Ebay_SW_pic_scraper_new_fixed.py** – a standalone script using [pyppeteer](https://github.com/pyppeteer/pyppeteer).

The standalone script reads links from `Ebay/EBay_links_output.csv` and saves the
first matching image for each item under `Ebay/Ebaydata/images/<SW_Code>/`.

## Requirements

Install the Python dependencies using pip:

```bash
pip install -r requirements.txt
```

`pyppeteer` will download a compatible Chromium build on first run. Ensure that
internet access is available.

## Usage

```bash
python LSW_Ebay_SW_pic_scraper_new_fixed.py
```

To rotate proxies, set the environment variable `SCRAPER_PROXIES` to a
comma-separated list of proxy URLs before running the script. Each
request will use the next proxy in the list.

The CSV file must contain the columns `SW_Code`, `Item_Link` and `Downloaded`.
Newly downloaded images will update the `Downloaded` column.
