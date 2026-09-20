import unittest

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


if __name__ == "__main__":
    unittest.main()
