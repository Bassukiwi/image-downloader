# Image Downloader

[简体中文](README.zh-CN.md)

A small Python utility that extracts image URLs from webpage HTML and downloads the files locally. It prefers the highest-quality candidate the page already exposes, with extra handling for Pixiv, note.com, and Patreon. Changing image URL query parameters is optional and off by default.

## How images are chosen

- **Most sites:** Prefer original or high-resolution candidates such as `data-full`, `data-hires`, `srcset`, or a parent link that points at an image file. Fall back to `src` / `data-src` thumbnails only when nothing better is available. Skip `data:` images. When the same resource appears at several sizes, keep the highest-quality variant.
- **Pixiv:** For `/artworks/{id}` pages, fetch illustration metadata and download every original `img-original` file in the work. Image requests use the artwork page as `Referer`.
- **note.com:** Rewrite `assets.st-note.com/img/` URLs to the click-to-enlarge CDN parameters (up to 4000 pixels, quality 90) and keep one variant per resource path.
- **Patreon:** Prefer the signed click-through original URL from the surrounding link or embedded page data, and keep its access token. The tool does not invent a new signed URL, does not rewrite Patreon query parameters, and skips URLs that have a hash but no expiry time.

Image downloads send the source page as `Referer`. A failed image is reported and skipped; remaining images on the page still download.

## Requirements

- Python 3.13 or newer
- Internet access to the target webpages and image hosts

## Installation

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project and its dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
```

The project depends on:

- `requests` for HTTP requests
- `beautifulsoup4` for parsing webpage HTML

## Run the interactive downloader

Start the console prompt with:

```powershell
python run.py
```

Enter one URL per line, or paste a block of text containing multiple URLs. Submit an empty line to continue:

```text
Enter one or more webpage URLs.
URL> https://example.com/page-one
URL> https://example.com/page-two
URL>
```

URLs are extracted, cleaned, and de-duplicated automatically. Invalid text is ignored. Downloaded images are saved in the `downloaded_images` directory.

Before downloading, the program asks whether to modify image URL query parameters. Press Enter or choose `n` to keep the original image URLs. Choose `y` to enter parameters such as `caw=1920&format=webp`; existing parameters with the same names are replaced and new parameters are appended. Signed Patreon media URLs are never rewritten.

## Run with URLs in the source file

The original script remains available for fixed input in `RAW_TEXT`:

```powershell
python do.py
```

Edit `RAW_TEXT` in `do.py` before running this mode. It also supports multiple URLs and uses the same rewrite prompt.

## Configuration

Adjust these values near the top of `do.py` when needed:

- `SAVE_DIR`: local output directory
- `HEADERS`: request headers used for webpage and image requests

## Troubleshooting

If PowerShell blocks script activation, use this command for the current terminal session and then activate the environment again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Some websites may block automated requests or require authentication. This tool does not bypass those restrictions. Login-only Pixiv or Patreon posts will fail unless the page is already publicly reachable.
