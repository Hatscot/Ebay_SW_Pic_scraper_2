import os
import time
import pandas as pd
import requests
import re
import asyncio
from pyppeteer import launch

# ----------------------------------------
# Configuration
# ----------------------------------------
use_existing_links = True
download_images = True

path_links_csv = os.path.join("Ebay", "EBay_links_output.csv")
image_root = os.path.join("Ebay", "Ebaydata", "images")

# CSS selectors for images and original offer button
CANONICAL_SELECTOR = "link[rel='canonical']"
OG_IMAGE_META = "meta[property='og:image']"
PRELOAD_LINKS = "link[rel='preload'][as='image']"
IMG_SELECTOR = "img"
ORIGINAL_BTN = "button[aria-label='Originalangebot ansehen']"

# ----------------------------------------
# Async browser (pyppeteer) will be launched when downloading
# ----------------------------------------
browser = None

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


async def extract_images_for_item(page, item_url, sw_code):
    await page.goto(item_url)
    # click original offer if present
    try:
        btn = await page.querySelector(ORIGINAL_BTN)
        if btn:
            await btn.click()
            await page.waitForTimeout(2000)
    except Exception:
        pass

    await page.waitForSelector(IMG_SELECTOR)

    urls = set()

    # meta og:image
    try:
        meta = await page.querySelector(OG_IMAGE_META)
        if meta:
            content = await page.evaluate('(el) => el.content', meta)
            if content:
                urls.add(re.sub(r'/s-l\d+(\.jpe?g|\.webp)$', '/s-l1600.webp', content))
    except Exception:
        pass

    # preload links
    for link in await page.querySelectorAll(PRELOAD_LINKS):
        href = await page.evaluate('(el) => el.href', link)
        if href:
            urls.add(href)

    # inline heroImg variable
    hero = await page.evaluate('window.heroImg || ""')
    if hero.startswith('http'):
        urls.add(hero)

    # all <img> tags
    for img in await page.querySelectorAll(IMG_SELECTOR):
        src = await page.evaluate('(el) => el.getAttribute("src") || ""', img)
        zoom = await page.evaluate('(el) => el.getAttribute("data-zoom-src") || ""', img)
        for url in (zoom, src):
            if url and sw_code.lower() in url.lower() and 'thumbs' not in url:
                urls.add(url)

    return urls


async def download_images_pyppeteer(df):
    global browser
    browser = await launch(headless=True, args=['--no-sandbox'])
    page = await browser.newPage()
    downloaded_any = False

    for idx, row in df[df['Downloaded'] == 0].iterrows():
        sw, link = row['SW_Code'], row['Item_Link']
        print(f"→ Processing {sw}: {link}")
        folder = os.path.join(image_root, sw)
        os.makedirs(folder, exist_ok=True)

        urls = await extract_images_for_item(page, link, sw)
        saved = 0
        for url in urls:
            try:
                save_image(url, folder)
                print(f"    ✔ {url}")
                saved += 1
                downloaded_any = True
                break  # stop after first image
            except Exception as e:
                print(f"    ✘ {url}: {e}")

        if saved:
            df.at[idx, 'Downloaded'] = 1
            df.to_csv(path_links_csv, index=False)
            print(f"  → {sw}: {saved} image saved.")
        else:
            print(f"  → {sw}: no images found.")

        if downloaded_any:
            break

    await browser.close()

# ----------------------------------------
# Main
# ----------------------------------------
async def main():
    links_df = load_links(path_links_csv)
    if download_images:
        await download_images_pyppeteer(links_df)

if __name__ == '__main__':
    asyncio.run(main())
