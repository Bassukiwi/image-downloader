import base64
import json
import os
import re
from datetime import datetime
from html import unescape
from urllib.parse import (
    parse_qsl,
    unquote,
    urlencode,
    urljoin,
    urlparse,
    urlunparse,
)

import requests
from bs4 import BeautifulSoup

# ==================== 1. 在这里直接粘贴网址 ====================
RAW_TEXT = """
# https://example.com/gallery?item=1&caw=1080
# https://example.com/photo/view?caw=1920
# https://example.com/test
# https://example.com/item3?caw=500;
# https://example.com/item4?a=1&caw=200
"""

# 保存图片的本地文件夹
SAVE_DIR = "downloaded_images"

TARGET_CAW = 3840

RewriteParameters = list[tuple[str, str]]
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif")
NOTE_IMAGE_HOST = "assets.st-note.com"
PATREON_IMAGE_SUFFIX = ".patreonusercontent.com"

# 请求头
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    # "Referer": "https://example.com/test",  # 如果需要，可以设置 Referer
}


def extract_urls(raw_input: str) -> list:
    """
    只负责从杂乱文本中提取网页 URL。

    注意：
    这里绝对不修改 caw。
    """

    url_pattern = r"https?://[^\s,\"\'>]+"

    raw_urls = re.findall(url_pattern, raw_input)

    urls = []
    seen = set()

    for url in raw_urls:
        # 去掉 URL 末尾可能误匹配的标点
        url = url.rstrip(".,;!)]}")

        # 去重
        if url not in seen:
            seen.add(url)
            urls.append(url)

    return urls


def build_pixiv_original_urls(page_url: str, metadata: dict) -> list[str]:
    """Build all original Pixiv image URLs from artwork metadata."""

    artwork_id = str(metadata.get("illustId", ""))
    page_count = metadata.get("pageCount", 0)
    create_date = metadata.get("createDate")

    if not artwork_id or not page_count:
        return []

    source_urls = []
    original_url = (metadata.get("urls") or {}).get("original")
    if original_url:
        source_urls.append(original_url)

    related_illustration = (metadata.get("userIllusts") or {}).get(artwork_id, {})
    related_url = related_illustration.get("url")
    if related_url:
        source_urls.append(related_url)

    for source_url in source_urls:
        source_match = re.match(
            r"^(https://i\.pximg\.net)/(?:.+/)?img/"
            r"(?P<timestamp>\d{4}/\d{2}/\d{2}/\d{2}/\d{2}/\d{2})/"
            r"(?P<id>\d+)_p\d+(?:_custom\d+)?(?P<extension>\.[^/?#]+)$",
            source_url,
        )
        if source_match and source_match.group("id") == artwork_id:
            return [
                f"{source_match.group(1)}/img-original/img/"
                f"{source_match.group('timestamp')}/{artwork_id}_p{page}"
                f"{source_match.group('extension')}"
                for page in range(int(page_count))
            ]

    if not create_date or not page_url:
        return []

    timestamp = datetime.fromisoformat(create_date).strftime("%Y/%m/%d/%H/%M/%S")
    return [
        f"https://i.pximg.net/img-original/img/{timestamp}/{artwork_id}_p{page}.jpg"
        for page in range(int(page_count))
    ]


def get_pixiv_original_urls(page_url: str) -> list[str]:
    """Fetch original image URLs for a Pixiv artwork page."""

    parsed_url = urlparse(page_url)
    if parsed_url.netloc not in {"pixiv.net", "www.pixiv.net"}:
        return []

    artwork_match = re.search(r"/artworks/(\d+)", parsed_url.path)
    if not artwork_match:
        return []

    artwork_id = artwork_match.group(1)
    api_url = f"https://www.pixiv.net/ajax/illust/{artwork_id}?lang=en"
    api_headers = {**HEADERS, "Referer": page_url}

    try:
        response = requests.get(api_url, headers=api_headers, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    if payload.get("error"):
        return []

    return build_pixiv_original_urls(page_url, payload.get("body") or {})


def _best_srcset_url(srcset: str) -> str | None:
    """Return the largest candidate from a srcset value."""

    candidates = []
    for candidate in srcset.split(","):
        parts = candidate.strip().split()
        if not parts:
            continue

        descriptor = parts[1] if len(parts) > 1 else "0w"
        match = re.fullmatch(r"(\d+(?:\.\d+)?)(w|x)", descriptor)
        score = float(match.group(1)) if match else 0
        candidates.append((score, parts[0]))

    if not candidates:
        return None

    return max(candidates, key=lambda candidate: candidate[0])[1]


def upgrade_image_url(image_url: str) -> str:
    """Use a site's original-image transformation when it is known."""

    parsed = urlparse(image_url)
    host = parsed.netloc.lower()
    is_note_image = host == NOTE_IMAGE_HOST and parsed.path.startswith("/img/")
    is_patreon_image = _is_patreon_image_url(image_url)

    if not is_note_image and not is_patreon_image:
        return image_url

    if is_patreon_image:
        # Patreon signs the encoded path and token together. Without the
        # page's real click URL, changing the thumbnail URL cannot produce a
        # valid original URL.
        return image_url
    else:
        query_params = [
            ("width", "4000"),
            ("height", "4000"),
            ("fit", "bounds"),
            ("format", "jpg"),
            ("quality", "90"),
        ]

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query_params),
            parsed.fragment,
        )
    )


def _is_patreon_image_url(image_url: str) -> bool:
    """Return whether a URL is a signed Patreon media URL."""

    parsed = urlparse(image_url)
    return parsed.netloc.lower().endswith(PATREON_IMAGE_SUFFIX) and "/patreon-media/" in parsed.path


def _patreon_transform(path: str) -> tuple[int, dict] | None:
    """Decode the signed image-transform segment in a Patreon path."""

    for index, segment in enumerate(path.split("/")):
        encoded = unquote(segment)
        if len(encoded) < 8:
            continue

        try:
            padding = "=" * (-len(encoded) % 4)
            payload = base64.urlsafe_b64decode(encoded + padding)
            transform = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            continue

        if isinstance(transform, dict) and {"w", "q", "webp", "a", "p"} & transform.keys():
            return index, transform

    return None


def _image_identity(image_url: str) -> str:
    """Identify same-file CDN variants without collapsing different images."""

    parsed = urlparse(image_url)
    if parsed.netloc.lower() == NOTE_IMAGE_HOST:
        identity_path = parsed.path
    elif parsed.netloc.lower().endswith(PATREON_IMAGE_SUFFIX):
        path_parts = parsed.path.split("/")
        transform = _patreon_transform(parsed.path)
        if transform:
            path_parts.pop(transform[0])
        identity_path = "/".join(path_parts)
    else:
        return image_url

    return urlunparse((parsed.scheme, parsed.netloc, identity_path, "", "", ""))


def _image_quality_score(image_url: str) -> tuple[float, float, float]:
    """Score known CDN variants by dimensions first, then quality."""

    parsed = urlparse(image_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))

    def number(name: str) -> float:
        try:
            return float(query.get(name, 0))
        except ValueError:
            return 0

    width = number("width")
    height = number("height")
    quality = number("quality")
    area = width * height if width and height else width or height

    transform = _patreon_transform(parsed.path)
    if transform:
        values = transform[1]
        if "q" in values:
            return 2, float(values.get("q", 0)), float(values.get("webp") == 0)
        if "w" in values:
            return 1, float(values.get("w", 0)), 0

    return 0, max(width, height), max(area, quality)


def _has_incomplete_patreon_token(image_url: str) -> bool:
    """Identify Patreon URLs that contain a hash but no expiry timestamp."""

    if not _is_patreon_image_url(image_url):
        return False

    query = dict(parse_qsl(urlparse(image_url).query, keep_blank_values=True))
    return bool(query.get("token-hash")) and not query.get("token-time")


_EMBEDDED_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})|\\/")


def _decode_embedded_page_data(html: str) -> str:
    """Decode HTML entities and JSON string escapes used in page payloads."""

    def replace(match: re.Match[str]) -> str:
        hex_value = match.group(1)
        if hex_value:
            return chr(int(hex_value, 16))
        return "/"

    return _EMBEDDED_ESCAPE_RE.sub(replace, unescape(html))


def extract_image_sources(html: str, page_url: str) -> list[str]:
    """Extract one best-quality image URL per HTML image element."""

    soup = BeautifulSoup(html, "html.parser")
    image_sources = []
    source_indexes = {}

    quality_attributes = (
        "data-full",
        "data-full-size",
        "data-hires",
        "data-highres",
        "data-large",
        "data-original",
    )
    fallback_attributes = ("data-src", "data-lazy-src", "src")

    for image in soup.find_all("img"):
        candidates = []

        for attribute in quality_attributes:
            value = image.get(attribute)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

        for attribute in ("data-srcset", "srcset"):
            value = image.get(attribute)
            if isinstance(value, str):
                candidate = _best_srcset_url(value)
                if candidate:
                    candidates.append(candidate)

        link = image.find_parent("a", href=True)
        href = link.get("href") if link else None
        if isinstance(href, str) and urlparse(href).path.lower().endswith(
            IMAGE_EXTENSIONS
        ):
            candidates.append(href)

        for attribute in fallback_attributes:
            value = image.get(attribute)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

        if not candidates:
            continue

        candidate_urls = [
            upgrade_image_url(urljoin(page_url, candidate)) for candidate in candidates
        ]
        candidate_urls = [
            candidate
            for candidate in candidate_urls
            if not candidate.startswith("data:")
            and not _has_incomplete_patreon_token(candidate)
        ]
        if not candidate_urls:
            continue

        full_url = max(candidate_urls, key=_image_quality_score)

        identity = _image_identity(full_url)
        existing_index = source_indexes.get(identity)
        if existing_index is None:
            source_indexes[identity] = len(image_sources)
            image_sources.append(full_url)
        elif _image_quality_score(full_url) > _image_quality_score(
            image_sources[existing_index]
        ):
            image_sources[existing_index] = full_url

    # Some Patreon pages keep the click-through URL in serialized page data
    # instead of the image's parent link. Include those signed candidates too.
    # The original query string often uses JSON escapes such as \u0026 for '&'.
    page_data = _decode_embedded_page_data(html)
    patreon_urls = re.findall(
        r"https?://[\w.-]*patreonusercontent\.com/[^\s\"'<>\\]+",
        page_data,
        flags=re.IGNORECASE,
    )
    for candidate in patreon_urls:
        full_url = upgrade_image_url(urljoin(page_url, candidate.rstrip(".,;")))
        if _has_incomplete_patreon_token(full_url):
            continue
        identity = _image_identity(full_url)
        existing_index = source_indexes.get(identity)
        if existing_index is None:
            source_indexes[identity] = len(image_sources)
            image_sources.append(full_url)
        elif _image_quality_score(full_url) > _image_quality_score(
            image_sources[existing_index]
        ):
            image_sources[existing_index] = full_url

    return image_sources


def parse_rewrite_parameters(raw_parameters: str) -> RewriteParameters:
    """Parse a query string such as ``caw=1920&format=webp``."""

    if not raw_parameters.strip():
        raise ValueError("参数不能为空")

    for parameter in raw_parameters.split("&"):
        if "=" not in parameter or not parameter.split("=", 1)[0].strip():
            raise ValueError("每个参数都必须使用 name=value 格式")

    parameters = parse_qsl(raw_parameters, keep_blank_values=True)

    if not parameters:
        raise ValueError("没有找到有效参数")

    return parameters


def prompt_url_rewrite(input_fn=input) -> RewriteParameters | None:
    """Ask whether image URL query parameters should be changed."""

    while True:
        choice = input_fn("是否修改图片链接参数？(y/n，默认 n): ").strip().lower()

        if choice in {"", "n", "no", "否"}:
            return None

        if choice in {"y", "yes", "是"}:
            while True:
                raw_parameters = input_fn(
                    "请输入要添加或修改的参数（例如 caw=1920&format=webp）: "
                ).strip()

                try:
                    return parse_rewrite_parameters(raw_parameters)
                except ValueError as error:
                    print(f"参数格式无效：{error}")
                    print("请重新输入。")

        print("请输入 y 或 n。")


def add_query_parameters(
    image_url: str,
    rewrite_parameters: RewriteParameters | None,
) -> str:
    """Replace or append query parameters when rewriting is enabled."""

    if rewrite_parameters is None or _is_patreon_image_url(image_url):
        return image_url

    parsed = urlparse(image_url)
    query_params = parse_qsl(parsed.query, keep_blank_values=True)

    for key, value in rewrite_parameters:
        replaced = False
        updated_params = []

        for existing_key, existing_value in query_params:
            if existing_key != key:
                updated_params.append((existing_key, existing_value))
            elif not replaced:
                updated_params.append((key, value))
                replaced = True

        if not replaced:
            updated_params.append((key, value))

        query_params = updated_params

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query_params),
            parsed.fragment,
        )
    )


def add_caw_to_image_url(image_url: str, target_caw: int = 3840) -> str:
    """
    只对真正的图片 URL 添加/修改 caw 参数。

    例如：

    https://example.com/a.jpg
        ↓
    https://example.com/a.jpg?caw=3840


    https://example.com/a.jpg?foo=1
        ↓
    https://example.com/a.jpg?foo=1&caw=3840


    https://example.com/a.jpg?foo=1&caw=500
        ↓
    https://example.com/a.jpg?foo=1&caw=3840
    """

    return add_query_parameters(image_url, [("caw", str(target_caw))])


def download_images_from_url(
    page_url: str,
    save_folder: str,
    rewrite_parameters: RewriteParameters | None = None,
):
    """
    请求网页 → 找到图片 → 按需修改图片 URL → 下载。
    """

    try:
        print("\n[+] 正在请求页面:")
        print(f"    {page_url}")

        response = requests.get(page_url, headers=HEADERS, timeout=15)

        response.raise_for_status()

        pixiv_image_urls = get_pixiv_original_urls(page_url)
        image_sources = pixiv_image_urls or extract_image_sources(
            response.text, page_url
        )

        if not image_sources:
            print("  [-] 该页面未找到 <img> 标签图片。")
            return

        img_count = 0

        for img_src in image_sources:
            # ==========================
            # 1. 获取图片原始地址
            # ==========================

            if not img_src:
                continue

            # ==========================
            # 2. 图片地址已经在提取阶段转成绝对 URL
            # ==========================

            original_img_url = img_src

            download_url = add_query_parameters(original_img_url, rewrite_parameters)

            print("\n  原始图片:")
            print(f"    {original_img_url}")

            if rewrite_parameters is not None:
                print("  修改后:")
                print(f"    {download_url}")
            else:
                print("  使用原始链接")

            # ==========================
            # 3. 获取文件名
            # ==========================

            parsed_path = urlparse(download_url).path

            filename = os.path.basename(parsed_path)

            if not filename:
                filename = f"image_{img_count + 1}.jpg"

            # 如果没有常见图片后缀
            if not any(
                filename.lower().endswith(ext)
                for ext in [
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                    ".gif",
                    ".svg",
                ]
            ):
                filename = f"image_{img_count + 1}.jpg"

            # ==========================
            # 4. 防止重名
            # ==========================

            file_path = os.path.join(save_folder, filename)

            counter = 1

            while os.path.exists(file_path):
                file_path = os.path.join(save_folder, f"{counter}_{filename}")

                counter += 1

            # ==========================
            # 5. 下载真正的图片
            # ==========================

            print(f"  --> 下载图片: {download_url}")

            try:
                image_headers = {**HEADERS, "Referer": page_url}
                img_res = requests.get(download_url, headers=image_headers, timeout=15)
                img_res.raise_for_status()
            except requests.RequestException as error:
                print(f"  [!] 图片下载失败: {type(error).__name__}: {error}")
                continue

            try:
                with open(file_path, "wb") as f:
                    f.write(img_res.content)
            except OSError as error:
                print(f"  [!] 图片保存失败: {type(error).__name__}: {error}")
                continue

            img_count += 1
            print(f"  [✓] 保存: {file_path}")

        print(f"\n  [✓] 页面处理完成，成功下载 {img_count} 张图片。")

    except (OSError, requests.RequestException) as error:
        print(f"  [!] 处理页面失败: {type(error).__name__}: {error}")


def main():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    # ==========================
    # 1. 只提取网页 URL
    # ==========================

    cleaned_urls = extract_urls(RAW_TEXT)

    if not cleaned_urls:
        print("[-] 未在提供的文本中识别到 任何有效的 HTTP/HTTPS 网址！")

        return

    rewrite_parameters = prompt_url_rewrite()

    print(f"=== 成功识别 {len(cleaned_urls)} 个网址 ===")

    for idx, url in enumerate(cleaned_urls, start=1):
        print(f" [{idx}] {url}")

    # ==========================
    # 2. 开始下载
    # ==========================

    print("\n=== 开始进行图片下载 ===")

    for idx, url in enumerate(cleaned_urls, start=1):
        print(f"\n进度: ({idx}/{len(cleaned_urls)})")

        download_images_from_url(url, SAVE_DIR, rewrite_parameters)

    print("\n🎉 所有图片下载完成！")

    print(f"文件保存在目录: {os.path.abspath(SAVE_DIR)}")


if __name__ == "__main__":
    main()
