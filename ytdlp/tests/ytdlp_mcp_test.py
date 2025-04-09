import unittest
import json
import os
from ytdlp_mcp import YtDlpService


class TestYtDlpService(unittest.TestCase):
    def setUp(self):
        self.service = YtDlpService()
        self.test_url = "https://www.youtube.com/watch?v=QlUt06XLbJE"
        self.test_chapters = [
            {"start_time": "13:50", "title": "SECRET SAUCE of AI Coding"}
        ]

    def test_extract_chapters(self):
        """Test extracting chapters from a YouTube video."""
        result = self.service.extract_chapters(self.test_url)

        # Verify the result structure
        self.assertTrue(result["success"])
        self.assertIn("content", result)
        self.assertIn("message", result)
        self.assertIn("raw_chapters", result)

        # Verify we got some chapters
        self.assertIsInstance(result["raw_chapters"], list)

        # Print chapters for manual verification
        print("\nExtracted chapters:")
        print(result["content"])

    def test_extract_subtitles(self):
        """Test extracting subtitles from a YouTube video with chapter filtering."""
        # No need to convert timestamps - the service will handle string timestamps
        result = self.service.extract_subtitles(
            self.test_url, language="en", chapters=self.test_chapters
        )

        # Verify the result structure
        self.assertTrue(result["success"])
        self.assertIn("content", result)
        self.assertIn("message", result)

        print(result["content"])
        # Verify we got some subtitle content
        self.assertIsInstance(result["content"], str)
        self.assertTrue(len(result["content"]) > 0)

        # Check if the chapter title is in the content
        self.assertIn(self.test_chapters[0]["title"], result["content"])

        # Print a sample of the subtitles for manual verification
        print("\nExtracted subtitles sample (first 500 chars):")
        print(result["content"][:500] + "...")

    def test_extract_subtitles_without_chapters(self):
        """Test extracting all subtitles from a YouTube video without chapter filtering."""
        result = self.service.extract_subtitles(self.test_url, language="en")

        # Verify the result structure
        self.assertTrue(result["success"])
        self.assertIn("content", result)
        self.assertIn("message", result)

        # Verify we got some subtitle content
        self.assertIsInstance(result["content"], str)
        self.assertTrue(len(result["content"]) > 0)

        # Print a sample of the subtitles for manual verification
        print("\nExtracted full subtitles sample (first 500 chars):")
        print(result["content"][:500] + "...")


if __name__ == "__main__":
    unittest.main()
