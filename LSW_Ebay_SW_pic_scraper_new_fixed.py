import os
import time
import pandas as pd
import requests
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ----------------------------------------
# Configuration
# ----------------------------------------
use_existing_links = True
download_images = True

path_links_csv = r"D:\Lego_Value_Checker\Ebay\EBay_links_output.csv"
image_root = r"D:\Lego_Value_Checker\Ebay\Ebaydata\images"

# CSS selectors for images and original offer button
CANONICAL_SELECTOR = "link[rel='canonical']"
OG_IMAGE_META = "meta[property='og:image']"
PRELOAD_LINKS = "link[rel='preload'][as='image']"
IMG_SELECTOR = "img"
ORIGINAL_BTN = "button[aria-label='Originalangebot ansehen']"

# ----------------------------------------
# Setup Selenium WebDriver
# ----------------------------------------
options = Options()
options.headless = True
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')

driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
wait = WebDriverWait(driver, 15)

# ----------------------------------------
# Functions
# ----------------------------------------
def load_links(path):
    df = pd.read_csv(path)
    df['Downloaded'] = df['Downloaded'].fillna(0).astype(int)
    return df


def save_image(url, folder):
    fname = os.path.basename(url.split('?')[0])
    dst = os.path.join(folder, fname)
    if not os.path.exists(dst):
        r = requests.get(url, timeout=30)
        with open(dst, 'wb') as f:
            f.write(r.content)
    return fname


def extract_images_for_item(item_url, sw_code):
    driver.get(item_url)
    # click original offer if present
    try:
        btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ORIGINAL_BTN)))
        btn.click()
        time.sleep(2)
    except:
        pass
    # wait for gallery container
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, IMG_SELECTOR)))

    # collect URLs
    urls = set()
    # meta og:image
    try:
        meta = driver.find_element(By.CSS_SELECTOR, OG_IMAGE_META)
        content = meta.get_attribute('content')
        if content:
            urls.add(re.sub(r'/s-l\d+(\.jpe?g|\.webp)$', '/s-l1600.webp', content))
    except:
        pass
    # preload links
    for link in driver.find_elements(By.CSS_SELECTOR, PRELOAD_LINKS):
        href = link.get_attribute('href')
        if href:
            urls.add(href)
    # inline heroImg
    hero = driver.execute_script('return window.heroImg || "";')
    if hero.startswith('http'):
        urls.add(hero)
    # all <img>
    for img in driver.find_elements(By.CSS_SELECTOR, IMG_SELECTOR):
        src = img.get_attribute('src') or ''
        zoom = img.get_attribute('data-zoom-src') or ''
        for url in (zoom, src):
            if url and sw_code.lower() in url.lower() and 'thumbs' not in url:
                urls.add(url)
    return urls


def download_images_selenium(df):
    for idx, row in df[df['Downloaded'] == 0].iterrows():
        sw, link = row['SW_Code'], row['Item_Link']
        print(f"→ Processing {sw}: {link}")
        folder = os.path.join(image_root, sw)
        os.makedirs(folder, exist_ok=True)
        urls = extract_images_for_item(link, sw)
        saved = 0
        for url in urls:
            try:
                save_image(url, folder)
                print(f"    ✔ {url}")
                saved += 1
            except Exception as e:
                print(f"    ✘ {url}: {e}")
        if saved:
            df.at[idx, 'Downloaded'] = 1
            df.to_csv(path_links_csv, index=False)
            print(f"  → {sw}: {saved} images saved.")
        else:
            print(f"  → {sw}: no images found.")

# ----------------------------------------
# Main
# ----------------------------------------
def main():
    links_df = load_links(path_links_csv)
    if download_images:
        download_images_selenium(links_df)
    driver.quit()

if __name__ == '__main__':
    main()
