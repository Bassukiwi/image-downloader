# Image Downloader

[简体中文](README.zh-CN.md)

A small Python utility that extracts image URLs from webpage HTML and downloads the images locally. It also updates the image URL's `caw` query parameter to the configured target width.

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

Enter one URL per line, or paste a block of text containing multiple URLs. Submit an empty line to begin downloading:

```text
Enter one or more webpage URLs.
URL> https://example.com/page-one
URL> https://example.com/page-two
URL>
```

URLs are extracted, cleaned, and de-duplicated automatically. Invalid text is ignored. Downloaded images are saved in the `downloaded_images` directory.

## Run with URLs in the source file

The original script remains available for fixed input in `RAW_TEXT`:

```powershell
python do.py
```

Edit `RAW_TEXT` in `do.py` before running this mode. It also supports multiple URLs.

## Configuration

Adjust these values near the top of `do.py` when needed:

- `SAVE_DIR`: local output directory
- `TARGET_CAW`: target image width passed as the `caw` query parameter
- `HEADERS`: request headers used for webpage and image requests

## Troubleshooting

If PowerShell blocks script activation, use this command for the current terminal session and then activate the environment again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Some websites may block automated requests or require authentication. This tool does not bypass those restrictions.
