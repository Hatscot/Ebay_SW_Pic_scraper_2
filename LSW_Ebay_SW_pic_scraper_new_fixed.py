import os
import time
import pandas as pd
import requests
import re
import asyncio
from pyppeteer import launch, chromium_downloader
import stat
import subprocess
import zipfile

# ----------------------------------------
# Configuration
# ----------------------------------------
use_existing_links = True
download_images = True

path_links_csv = os.path.join("Ebay", "EBay_links_output.csv")
image_root = os.path.join("Ebay", "Ebaydata", "images")

# List of proxies to rotate through. Set the environment variable
# `SCRAPER_PROXIES` to a comma separated list of proxy URLs to override.
proxy_env = os.environ.get("SCRAPER_PROXIES", "")
PROXIES = [p.strip() for p in proxy_env.split(',') if p.strip()]
proxy_index = 0

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


def ensure_chromium():
    exe_path = chromium_downloader.chromium_executable()
    if os.path.exists(exe_path):
        os.chmod(exe_path, os.stat(exe_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return exe_path

    download_url = chromium_downloader.get_url()
    dest_dir = chromium_downloader.DOWNLOADS_FOLDER / chromium_downloader.REVISION
    os.makedirs(dest_dir, exist_ok=True)
    zip_path = dest_dir / 'chrome.zip'

    # download via requests which respects proxy settings
    with requests.get(download_url, stream=True) as r:
        r.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    # extract
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    os.remove(zip_path)

    # ensure executable permission
    os.chmod(exe_path, os.stat(exe_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return exe_path

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
    await page.goto(item_url, {'waitUntil': 'networkidle2', 'timeout': 60000})
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
    global browser, proxy_index
    exec_path = ensure_chromium()
    proxies = PROXIES or [os.environ.get('http_proxy', '')]
    downloaded_any = False

    for idx, row in df[df['Downloaded'] == 0].iterrows():
        sw, link = row['SW_Code'], row['Item_Link']
        print(f"→ Processing {sw}: {link}")
        folder = os.path.join(image_root, sw)
        os.makedirs(folder, exist_ok=True)

        proxy = proxies[proxy_index % len(proxies)] if proxies else ''
        proxy_index += 1
        launch_args = [
            '--no-sandbox',
            '--disable-gpu',
            '--ignore-certificate-errors',
        ]
        if proxy:
            launch_args.append(f'--proxy-server={proxy}')

        browser = await launch(
            executablePath=exec_path,
            headless=True,
            args=launch_args,
        )
        page = await browser.newPage()
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36')

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
            await browser.close()
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
