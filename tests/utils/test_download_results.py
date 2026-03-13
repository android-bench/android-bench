import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
import os
import argparse
from utils import download_results


class TestDownloadResults(unittest.TestCase):

    @patch("utils.download_results.urllib.request.urlopen")
    @patch("utils.download_results.json.loads")
    def test_fetch_release_assets_success(self, mock_json_loads, mock_urlopen):
        # Mocking the GitHub API response
        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Mocking the JSON payload to match GitHub Releases API response structure (a dict with an 'assets' key)
        mock_json_loads.return_value = {
            "assets": [
                {
                    "name": "gemini-3.1-pro-preview.tar.gz",
                    "browser_download_url": "http://example.com/gemini",
                },
                {
                    "name": "claude-sonnet-4-5.tar.gz",
                    "browser_download_url": "http://example.com/claude",
                },
            ]
        }

        assets = download_results.fetch_release_assets(
            "test-org", "test-repo", "v1.0.0"
        )

        self.assertEqual(len(assets), 2)
        # fetch_release_assets returns a list of dictionaries now, not a keyed dict
        self.assertEqual(assets[0]["name"], "gemini-3.1-pro-preview.tar.gz")
        self.assertEqual(assets[0]["browser_download_url"], "http://example.com/gemini")
        self.assertEqual(assets[1]["name"], "claude-sonnet-4-5.tar.gz")
        self.assertEqual(assets[1]["browser_download_url"], "http://example.com/claude")
        mock_urlopen.assert_called_once()

    @patch("utils.download_results.urllib.request.urlopen")
    def test_fetch_release_assets_failure(self, mock_urlopen):
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError("url", 404, "Not Found", {}, None)

        with patch("sys.stdout", new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit):
                download_results.fetch_release_assets("test-org", "test-repo", "v1.0.0")

            output = fake_out.getvalue()
            self.assertIn("Error fetching release: HTTP 404 - Not Found", output)

    @patch("utils.download_results.argparse.ArgumentParser.parse_args")
    def test_argument_parsing_in_main(self, mock_parse_args):
        # We just want to ensure main sets up arguments correctly.
        # Since logic is intertwined in main(), we can mock parse_args to return specific values
        # and mock fetch_release_assets to prevent actual execution.
        mock_args = argparse.Namespace(
            models=["all"],
            dir=".",
            org="android-bench",
            repo="android-bench",
            tag="v1.0.0",
        )
        mock_parse_args.return_value = mock_args

        with patch("utils.download_results.fetch_release_assets") as mock_fetch:
            # We also need to mock sys.exit to catch the empty assets exit
            with patch("sys.exit"):
                with patch("sys.stdout", new=StringIO()):
                    download_results.main()
                    mock_fetch.assert_called_once_with(
                        "android-bench", "android-bench", "v1.0.0"
                    )

    @patch("utils.download_results.urllib.request.urlretrieve")
    def test_download_file(self, mock_urlretrieve):
        # We mock urlretrieve which is now used in download_results

        with patch("sys.stdout", new=StringIO()):
            download_results.download_file(
                "http://example.com/test.gz", "test_out.gz", "test.gz"
            )

        mock_urlretrieve.assert_called_once_with(
            "http://example.com/test.gz", "test_out.gz"
        )


if __name__ == "__main__":
    unittest.main()
