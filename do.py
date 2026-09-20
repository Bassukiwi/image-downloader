import os
import re
from urllib.parse import (
    parse_qsl,
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

    parsed = urlparse(image_url)

    # 解析原有 query 参数
    query_params = parse_qsl(parsed.query, keep_blank_values=True)

    # 删除原来的 caw
    query_params = [(key, value) for key, value in query_params if key.lower() != "caw"]

    # 添加新的 caw
    query_params.append(("caw", str(target_caw)))

    # 重新生成 query
    new_query = urlencode(query_params)

    # 重新组合 URL
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )


def download_images_from_url(page_url: str, save_folder: str):
    """
    请求网页 → 找到图片 → 修改图片 URL 的 caw → 下载。
    """

    try:
        print("\n[+] 正在请求页面:")
        print(f"    {page_url}")

        response = requests.get(page_url, headers=HEADERS, timeout=15)

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        img_tags = soup.find_all("img")

        if not img_tags:
            print("  [-] 该页面未找到 <img> 标签图片。")
            return

        img_count = 0

        for img in img_tags:
            # ==========================
            # 1. 获取图片原始地址
            # ==========================

            img_src = img.get("src") or img.get("data-src") or img.get("data-original")

            if not img_src:
                continue

            # ==========================
            # 2. 转换成绝对 URL
            # ==========================

            full_img_url = urljoin(page_url, img_src)

            # 排除 base64
            if full_img_url.startswith("data:"):
                continue

            # ==========================
            # 3. ⭐ 这里才修改图片 URL
            # ==========================

            original_img_url = full_img_url

            full_img_url = add_caw_to_image_url(full_img_url, TARGET_CAW)

            print("\n  原始图片:")
            print(f"    {original_img_url}")

            print("  修改后:")
            print(f"    {full_img_url}")

            # ==========================
            # 4. 获取文件名
            # ==========================

            parsed_path = urlparse(full_img_url).path

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
            # 5. 防止重名
            # ==========================

            file_path = os.path.join(save_folder, filename)

            counter = 1

            while os.path.exists(file_path):
                file_path = os.path.join(save_folder, f"{counter}_{filename}")

                counter += 1

            # ==========================
            # 6. 下载真正的图片
            # ==========================

            print(f"  --> 下载图片: {full_img_url}")

            img_res = requests.get(full_img_url, headers=HEADERS, timeout=15)

            if img_res.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(img_res.content)

                img_count += 1

                print(f"  [✓] 保存: {file_path}")

            else:
                print(f"  [!] 图片下载失败: HTTP {img_res.status_code}")

        print(f"\n  [✓] 页面处理完成，成功下载 {img_count} 张图片。")

    except Exception as e:
        print(f"  [!] 处理页面失败: {e}")


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

    print(f"=== 成功识别 {len(cleaned_urls)} 个网址 ===")

    for idx, url in enumerate(cleaned_urls, start=1):
        print(f" [{idx}] {url}")

    # ==========================
    # 2. 开始下载
    # ==========================

    print("\n=== 开始进行图片下载 ===")

    for idx, url in enumerate(cleaned_urls, start=1):
        print(f"\n进度: ({idx}/{len(cleaned_urls)})")

        download_images_from_url(url, SAVE_DIR)

    print("\n🎉 所有图片下载完成！")

    print(f"文件保存在目录: {os.path.abspath(SAVE_DIR)}")


if __name__ == "__main__":
    main()
