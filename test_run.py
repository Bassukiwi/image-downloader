import unittest

from do import (
    add_query_parameters,
    build_pixiv_original_urls,
    extract_image_sources,
    upgrade_image_url,
    parse_rewrite_parameters,
    prompt_url_rewrite,
)
from run import collect_urls


class CollectUrlsTests(unittest.TestCase):
    def test_collects_multiple_urls_until_blank_line(self):
        inputs = iter(
            [
                "https://example.com/one",
                "some text https://example.com/two,",
                "https://example.com/one",
                "",
            ]
        )

        urls = collect_urls(input_fn=lambda _prompt: next(inputs))

        self.assertEqual(
            urls,
            [
                "https://example.com/one",
                "https://example.com/two",
            ],
        )


class ImageUrlRewriteTests(unittest.TestCase):
    def test_keeps_original_url_when_rewrite_is_disabled(self):
        image_url = "https://example.com/image.jpg?caw=500"

        result = add_query_parameters(image_url, None)

        self.assertEqual(result, image_url)

    def test_replaces_existing_and_appends_new_parameters(self):
        image_url = "https://example.com/image.jpg?caw=500&token=abc"
        parameters = [("caw", "1920"), ("format", "webp")]

        result = add_query_parameters(image_url, parameters)

        self.assertEqual(
            result,
            "https://example.com/image.jpg?caw=1920&token=abc&format=webp",
        )

    def test_parses_multiple_custom_parameters(self):
        result = parse_rewrite_parameters("caw=1920&format=webp")

        self.assertEqual(result, [("caw", "1920"), ("format", "webp")])

    def test_prompt_retries_after_malformed_parameters(self):
        inputs = iter(["yes", "caw", "caw=1920&format=webp"])

        result = prompt_url_rewrite(input_fn=lambda _prompt: next(inputs))

        self.assertEqual(result, [("caw", "1920"), ("format", "webp")])


class PixivImageTests(unittest.TestCase):
    def test_builds_all_original_urls_from_pixiv_metadata(self):
        metadata = {
            "illustId": "149940075",
            "pageCount": 2,
            "createDate": "2026-09-21T12:17:00+00:00",
            "urls": {"original": None},
            "userIllusts": {
                "149940075": {
                    "url": "https://i.pximg.net/c/250x250_80_a2/custom-thumb/img/2026/09/21/21/17/48/149940075_p0_custom1200.jpg"
                }
            },
        }

        result = build_pixiv_original_urls(
            "https://www.pixiv.net/artworks/149940075",
            metadata,
        )

        self.assertEqual(
            result,
            [
                "https://i.pximg.net/img-original/img/2026/09/21/21/17/48/149940075_p0.jpg",
                "https://i.pximg.net/img-original/img/2026/09/21/21/17/48/149940075_p1.jpg",
            ],
        )


class GenericImageSourceTests(unittest.TestCase):
    def test_prefers_high_quality_attributes_and_largest_srcset_candidate(self):
        html = """
        <a href="/images/photo-original.jpg">
            <img src="/images/photo-thumb.jpg"
                 data-original="/images/photo-medium.jpg"
                 data-full="/images/photo-full.jpg"
                 srcset="/images/photo-small.jpg 400w, /images/photo-large.jpg 1600w">
        </a>
        """

        result = extract_image_sources(html, "https://example.com/gallery")

        self.assertEqual(result, ["https://example.com/images/photo-full.jpg"])

    def test_falls_back_to_src_when_no_high_quality_candidate_exists(self):
        html = '<img src="/images/photo-thumb.jpg">'

        result = extract_image_sources(html, "https://example.com/gallery")

        self.assertEqual(result, ["https://example.com/images/photo-thumb.jpg"])

    def test_uses_largest_srcset_candidate_when_no_explicit_original_exists(self):
        html = """
        <img src="/images/photo-thumb.jpg"
             srcset="/images/photo-small.jpg 400w, /images/photo-large.jpg 1600w">
        """

        result = extract_image_sources(html, "https://example.com/gallery")

        self.assertEqual(result, ["https://example.com/images/photo-large.jpg"])

    def test_uses_image_link_when_thumbnail_is_wrapped_by_original_url(self):
        html = """
        <a href="/images/photo-original.jpg">
            <img src="/images/photo-thumb.jpg">
        </a>
        """

        result = extract_image_sources(html, "https://example.com/gallery")

        self.assertEqual(result, ["https://example.com/images/photo-original.jpg"])

    def test_upgrades_note_image_to_the_click_quality_variant(self):
        image_url = (
            "https://assets.st-note.com/img/1763820256-abc.jpg?width=1200"
        )

        result = upgrade_image_url(image_url)

        self.assertEqual(
            result,
            "https://assets.st-note.com/img/1763820256-abc.jpg?"
            "width=4000&height=4000&fit=bounds&format=jpg&quality=90",
        )

    def test_deduplicates_note_size_variants_after_upgrading(self):
        html = """
        <img src="https://assets.st-note.com/img/photo.jpg?width=400">
        <img src="https://assets.st-note.com/img/photo.jpg?width=1200">
        """

        result = extract_image_sources(html, "https://note.com/example")

        self.assertEqual(
            result,
            [
                "https://assets.st-note.com/img/photo.jpg?"
                "width=4000&height=4000&fit=bounds&format=jpg&quality=90"
            ],
        )

    def test_keeps_only_highest_note_variant_for_same_image_path(self):
        html = """
        <img src="https://assets.st-note.com/production/uploads/images/avatar.jpg?width=60">
        <img src="https://assets.st-note.com/production/uploads/images/avatar.jpg?width=600">
        <img src="https://assets.st-note.com/production/uploads/images/avatar.jpg?width=80&height=80">
        """

        result = extract_image_sources(html, "https://note.com/example")

        self.assertEqual(
            result,
            [
                "https://assets.st-note.com/production/uploads/images/avatar.jpg?width=600"
            ],
        )


if __name__ == "__main__":
    unittest.main()
