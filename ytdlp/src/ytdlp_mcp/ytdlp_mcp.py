import os
import tempfile
import json
from typing import Dict, Any, List, Optional
import yt_dlp
from pydantic import BaseModel
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


# Pydantic models for input validation
class YouTubeChapterInput(BaseModel):
    url: str


class YouTubeChapter(BaseModel):
    start_time: str
    title: str


class YouTubeSubtitles(BaseModel):
    url: str
    language: str = "en"
    chapters: List[YouTubeChapter]


class YtDlpTools(str):
    YOUTUBE_CHAPTERS = "youtube_chapters"
    YOUTUBE_SUBTITLES = "youtube_subtitles"


class YtDlpService:
    """Service for extracting subtitles and chapters from YouTube videos using yt-dlp."""

    def __init__(self):
        """Initialize the YouTube extraction service."""
        # No need to check if yt-dlp is installed since we're importing it directly

    def _time_to_seconds(self, time_str: str) -> float:
        """
        Convert a time string (HH:MM:SS or MM:SS) to seconds.

        Args:
            time_str: Time string in format "HH:MM:SS", "MM:SS", or already a number

        Returns:
            Time in seconds as a float
        """
        # If already a number, return it
        if isinstance(time_str, (int, float)):
            return float(time_str)

        # Handle string time formats
        try:
            parts = time_str.split(":")
            if len(parts) == 3:  # HH:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:  # MM:SS
                return int(parts[0]) * 60 + float(parts[1])
            else:
                # Try to convert directly to float
                return float(time_str)
        except (ValueError, AttributeError):
            # If conversion fails, return 0
            return 0.0

    def extract_subtitles(
        self,
        url: str,
        language: str = "en",
        chapters: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Extract subtitles from a YouTube video, filtered by chapters if provided.

        Args:
            url: YouTube video URL
            language: Language code for subtitles (default: "en" for English)
            chapters: List of chapters with start_time and title to filter subtitles

        Returns:
            Dict containing success status, subtitle content, and any error information
        """
        try:
            # Convert any string timestamps in chapters to seconds
            if chapters:
                for chapter in chapters:
                    if "start_time" in chapter and not isinstance(
                        chapter["start_time"], (int, float)
                    ):
                        chapter["start_time"] = self._time_to_seconds(
                            chapter["start_time"]
                        )
                    if "end_time" in chapter and not isinstance(
                        chapter["end_time"], (int, float)
                    ):
                        chapter["end_time"] = self._time_to_seconds(chapter["end_time"])

            # Create a temporary directory to store the subtitle file
            with tempfile.TemporaryDirectory() as temp_dir:
                output_file = os.path.join(temp_dir, "subtitles")

                # Configure yt-dlp options
                ydl_opts = {
                    "skip_download": True,
                    "writesubtitles": True,
                    "writeautomaticsub": True,  # Also try auto-generated subs if regular ones aren't available
                    "subtitleslangs": [language],
                    "subtitlesformat": "vtt",
                    "outtmpl": output_file,
                    "quiet": True,
                }

                # Use yt-dlp library directly
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)

                # Get all chapters for context if we're filtering by chapters
                all_chapters = None
                if chapters and not any(
                    chapter.get("end_time") for chapter in chapters
                ):
                    # Get all chapters from video metadata
                    all_chapters = info.get("chapters", [])

                    # If no chapters in video metadata, create a single chapter for the whole video
                    if not all_chapters and info.get("duration"):
                        all_chapters = [
                            {
                                "start_time": 0,
                                "end_time": info.get("duration", 0),
                                "title": info.get("title", "Full Video"),
                            }
                        ]

                    # Sort all chapters by start time
                    all_chapters = sorted(
                        all_chapters, key=lambda x: x.get("start_time", 0)
                    )

                # Check if the subtitle file was created
                subtitle_file = f"{output_file}.{language}.vtt"
                if os.path.exists(subtitle_file):
                    with open(subtitle_file, "r", encoding="utf-8") as f:
                        subtitle_content = f.read()

                    # Get video duration if available
                    duration = info.get("duration", 0)

                    # Process the VTT content to make it more readable, filtered by chapters
                    processed_content = self._process_vtt_content(
                        subtitle_content, chapters, all_chapters, duration
                    )

                    return {
                        "success": True,
                        "content": processed_content,
                        "message": "Subtitles successfully extracted"
                        + (" for specified chapters" if chapters else ""),
                    }
                else:
                    return {
                        "success": False,
                        "error": f"No subtitles found for language '{language}'",
                    }

        except Exception as e:
            raise

    def _process_vtt_content(
        self,
        vtt_content: str,
        selected_chapters: Optional[List[Dict[str, Any]]] = None,
        all_chapters: Optional[List[Dict[str, Any]]] = None,
        video_duration: int = 0,
    ) -> str:
        """
        Process VTT subtitle content to make it more readable, filtered by chapters if provided.

        Args:
            vtt_content: Raw VTT subtitle content
            selected_chapters: List of specific chapters to extract subtitles for
            all_chapters: Complete list of all chapters in the video (for context)
            video_duration: Total duration of the video in seconds

        Returns:
            Processed subtitle text
        """
        lines = vtt_content.split("\n")

        # If no chapters provided, process all subtitles
        if not selected_chapters:
            return self._process_all_subtitles(lines)

        # Create chapter ranges with start and end times
        chapter_ranges = []

        # Sort selected chapters by start time
        selected_chapters = sorted(
            selected_chapters, key=lambda x: x.get("start_time", 0)
        )

        for chapter in selected_chapters:
            start_time = chapter.get("start_time", 0)
            title = chapter.get("title", "Unnamed chapter")

            # If chapter has explicit end_time, use it
            if "end_time" in chapter:
                end_time = chapter["end_time"]
            else:
                # Find this chapter in all_chapters to determine its end time
                end_time = None

                if all_chapters:
                    # Find the current chapter in all_chapters
                    for i, full_chapter in enumerate(all_chapters):
                        if (
                            full_chapter.get("start_time") == start_time
                            and full_chapter.get("title") == title
                        ):
                            # If this is the last chapter, end time is video duration
                            if i == len(all_chapters) - 1:
                                end_time = video_duration
                            else:
                                # Otherwise, end time is the start time of the next chapter
                                end_time = all_chapters[i + 1].get("start_time")
                            break

                # If we couldn't find the end time, use the next chapter's start time or video duration
                if end_time is None:
                    # Find the next chapter in selected_chapters that has a later start time
                    next_chapters = [
                        c
                        for c in selected_chapters
                        if c.get("start_time", 0) > start_time
                    ]
                    if next_chapters:
                        end_time = min(
                            c.get("start_time", video_duration) for c in next_chapters
                        )
                    else:
                        end_time = video_duration

            # Add 2 seconds buffer to end time if it's not the last chapter
            is_last_chapter = i == len(selected_chapters) - 1
            if not is_last_chapter and end_time < video_duration:
                end_time += 2

            chapter_ranges.append(
                {"start": start_time, "end": end_time, "title": title}
            )

        # Process subtitles by chapter
        result = []
        for chapter_range in chapter_ranges:
            chapter_subs = self._extract_subtitles_for_timerange(
                lines, chapter_range["start"], chapter_range["end"]
            )
            if chapter_subs:
                result.append(f"## {chapter_range['title']}")
                result.append(chapter_subs)

        return "\n\n".join(result)

    def _process_all_subtitles(self, lines: list) -> str:
        """Process all subtitles without chapter filtering."""
        processed_lines = []
        seen_sentences = set()  # Track unique sentences
        current_sentence = ""

        # Skip header lines
        start_processing = False

        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue

            # Skip VTT header
            if not start_processing:
                if line.strip() and not line.startswith("WEBVTT"):
                    start_processing = True
                else:
                    continue

            # Skip timing lines (they contain --> )
            if "-->" in line:
                continue

            # Skip lines with just numbers (timestamp indices)
            if line.strip().isdigit():
                continue

            # Clean the line and add non-empty content
            cleaned_line = self._clean_subtitle_text(line.strip())
            if not cleaned_line:
                continue

            # Check if this line is a duplicate of the previous content
            # This handles the case where VTT repeats the same text in consecutive segments
            if processed_lines and cleaned_line in processed_lines[-1]:
                continue

            # If we have a complete sentence, add it
            if cleaned_line.endswith((".", "!", "?")):
                if current_sentence:
                    full_sentence = f"{current_sentence} {cleaned_line}".strip()
                else:
                    full_sentence = cleaned_line

                # Only add if not a duplicate
                if full_sentence not in seen_sentences:
                    seen_sentences.add(full_sentence)
                    processed_lines.append(full_sentence)
                current_sentence = ""
            else:
                # Add to current sentence
                if current_sentence:
                    current_sentence += f" {cleaned_line}"
                else:
                    current_sentence = cleaned_line

        # Add any remaining text
        if current_sentence and current_sentence not in seen_sentences:
            seen_sentences.add(current_sentence)
            processed_lines.append(current_sentence)

        # Final deduplication pass - remove lines that are substrings of other lines
        final_lines = []
        for i, line in enumerate(processed_lines):
            is_substring = False
            for j, other_line in enumerate(processed_lines):
                if i != j and line in other_line:
                    is_substring = True
                    break
            if not is_substring:
                final_lines.append(line)

        return "\n".join(final_lines)

    def _extract_subtitles_for_timerange(
        self, lines: list, start_seconds: float, end_seconds: float
    ) -> str:
        """
        Extract subtitles that fall within a specific time range.

        Args:
            lines: VTT subtitle lines
            start_seconds: Start time in seconds
            end_seconds: End time in seconds

        Returns:
            Processed subtitle text for the time range
        """
        # Ensure start_seconds and end_seconds are float values
        start_seconds = float(start_seconds)
        end_seconds = float(end_seconds)

        # First, collect all subtitle segments in the time range
        subtitle_segments = []
        current_time = 0
        current_segment = {"time": 0, "text": ""}

        i = 0
        while i < len(lines):
            line = lines[i]

            # Parse timestamp lines
            if "-->" in line:
                time_parts = line.split("-->")
                if len(time_parts) >= 1:
                    # Parse the start time
                    time_str = time_parts[0].strip()
                    try:
                        # Handle different time formats (00:00:00.000 or 00:00.000)
                        if time_str.count(":") == 2:
                            h, m, s = time_str.split(":")
                            current_time = int(h) * 3600 + int(m) * 60 + float(s)
                        else:
                            m, s = time_str.split(":")
                            current_time = int(m) * 60 + float(s)

                        # Check if this subtitle falls within our chapter range
                        if start_seconds <= current_time < end_seconds:
                            # Start a new segment
                            current_segment = {"time": current_time, "text": ""}

                            # Collect all text lines until next timestamp or empty line
                            j = i + 1
                            while (
                                j < len(lines)
                                and not ("-->" in lines[j])
                                and lines[j].strip()
                            ):
                                if not lines[j].strip().isdigit():  # Skip index numbers
                                    cleaned_line = self._clean_subtitle_text(
                                        lines[j].strip()
                                    )
                                    if cleaned_line:
                                        current_segment["text"] += (
                                            " " + cleaned_line
                                            if current_segment["text"]
                                            else cleaned_line
                                        )
                                j += 1

                            # Only add non-empty segments
                            if current_segment["text"]:
                                subtitle_segments.append(current_segment)
                    except (ValueError, IndexError):
                        pass
            i += 1

        # Now process the segments to remove duplicates
        processed_lines = []
        seen_texts = set()

        # Sort segments by time
        subtitle_segments.sort(key=lambda x: x["time"])

        # Process segments
        for segment in subtitle_segments:
            text = segment["text"].strip()

            # Skip if we've seen this exact text before
            if text in seen_texts:
                continue

            # Skip if this text is a substring of the last added line
            if processed_lines and text in processed_lines[-1]:
                continue

            # Skip if the last added line is a substring of this text
            if processed_lines and processed_lines[-1] in text:
                # Replace the last line with this more complete one
                processed_lines[-1] = text
                seen_texts.add(text)
                continue

            # Add new unique text
            processed_lines.append(text)
            seen_texts.add(text)

        return "\n".join(processed_lines)

    def _clean_subtitle_text(self, text: str) -> str:
        """
        Remove HTML-like tags and timestamps from subtitle text.

        Args:
            text: Raw subtitle text with tags

        Returns:
            Clean text without tags
        """
        import re

        # Remove timestamp tags like <00:13:50.279>
        text = re.sub(r"<\d+:\d+:\d+\.\d+>", "", text)

        # Remove <c> and </c> tags
        text = re.sub(r"</?c>", "", text)

        # Remove any duplicate spaces created by tag removal
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _format_time(self, seconds: float) -> str:
        """
        Format time in seconds to HH:MM:SS format.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted time string
        """
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def extract_chapters(self, url: str) -> Dict[str, Any]:
        """
        Extract chapters from a YouTube video.

        Args:
            url: YouTube video URL

        Returns:
            Dict containing success status, chapters information, and any error information
        """
        try:
            # Configure yt-dlp options
            ydl_opts = {
                "skip_download": True,
                "quiet": True,
            }

            # Use yt-dlp library directly
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            # Get video title
            video_title = info.get("title", "Untitled Video")

            # Check if chapters information is available
            if info and "chapters" in info and info["chapters"]:
                chapters = info["chapters"]

                # Format chapters information
                formatted_chapters = []
                for chapter in chapters:
                    start_time = self._format_time(chapter.get("start_time", 0))
                    title = chapter.get("title", "Unnamed chapter")
                    formatted_chapters.append(f"{start_time} - {title}")

                chapters_text = "\n".join(formatted_chapters)

                return {
                    "success": True,
                    "content": chapters_text,
                    "message": f"Successfully extracted {len(chapters)} chapters",
                    "raw_chapters": chapters,  # Include raw data for potential further processing
                }
            else:
                # No chapters found, return video title as a single chapter
                formatted_chapter = f"00:00 - {video_title}"

                return {
                    "success": True,
                    "content": formatted_chapter,
                    "message": "No chapters found. Returning video title as a single chapter.",
                    "raw_chapters": [{"start_time": 0, "title": video_title}],
                }

        except Exception as e:
            return {"success": False, "error": f"Failed to extract chapters: {str(e)}"}


async def serve() -> None:
    server = Server("mcp-ytdlp")
    service = YtDlpService()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=YtDlpTools.YOUTUBE_CHAPTERS,
                description="Extract chapters from a YouTube video",
                inputSchema=YouTubeChapterInput.model_json_schema(),
            ),
            Tool(
                name=YtDlpTools.YOUTUBE_SUBTITLES,
                description="Extract subtitles from a YouTube video for specific chapters",
                inputSchema=YouTubeSubtitles.model_json_schema(),
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            if name == YtDlpTools.YOUTUBE_CHAPTERS:
                result = service.extract_chapters(arguments["url"])
                return [TextContent(type="text", text=result["content"])]

            elif name == YtDlpTools.YOUTUBE_SUBTITLES:
                if "chapters" not in arguments or len(arguments["chapters"]) == 0:
                    raise Exception("Chapter is required")
                result = service.extract_subtitles(
                    arguments["url"],
                    arguments.get("language", "en"),
                    arguments["chapters"],
                )
                return [TextContent(type="text", text=result["content"])]
            else:
                raise ValueError(f"Unknown tool: {name}")

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


def main():
    import asyncio

    asyncio.run(serve())
