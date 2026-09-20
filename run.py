import os

from do import (
    SAVE_DIR,
    download_images_from_url,
    extract_urls,
)


def collect_urls(input_fn=input):
    """Read URL text line by line until the user submits a blank line."""
    print("Enter one or more webpage URLs.")
    print("You can paste several URLs at once; submit a blank line to start.")

    lines = []
    while True:
        line = input_fn("URL> ")
        if not line.strip():
            break
        lines.append(line)

    return extract_urls("\n".join(lines))


def main():
    urls = collect_urls()

    if not urls:
        print("No valid HTTP/HTTPS URLs were found.")
        return

    os.makedirs(SAVE_DIR, exist_ok=True)

    print(f"\nFound {len(urls)} URL(s):")
    for index, url in enumerate(urls, start=1):
        print(f"  [{index}] {url}")

    print("\nStarting image downloads...")
    for index, url in enumerate(urls, start=1):
        print(f"\nProgress: ({index}/{len(urls)})")
        download_images_from_url(url, SAVE_DIR)

    print(f"\nAll downloads finished. Files are in: {SAVE_DIR}")


if __name__ == "__main__":
    main()
