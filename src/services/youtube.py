import os
import yt_dlp
import logging

logger = logging.getLogger(__name__)

class YoutubeService:
    def __init__(self, temp_dir="temp"):
        self.temp_dir = temp_dir
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def get_metadata(self, url):
        """Fetches title, thumbnail, and duration."""
        logger.info(f"Fetching metadata for: {url}")
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                logger.info(f"Metadata fetched: {info.get('title')}")
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'thumbnail': info.get('thumbnail'),
                    'duration': info.get('duration'),
                    'id': info.get('id')
                }
            except Exception as e:
                logger.error(f"Failed to fetch metadata for {url}: {str(e)}")
                raise Exception(f"Failed to fetch metadata: {str(e)}")

    def download_audio(self, url, output_filename):
        """Downloads audio as WAV 16kHz Mono."""
        output_path = os.path.join(self.temp_dir, f"{output_filename}.wav")
        logger.info(f"Downloading audio from {url} to {output_path}")
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'postprocessor_args': [
                '-ar', '16000',
                '-ac', '1',
            ],
            'outtmpl': os.path.join(self.temp_dir, output_filename),
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([url])
                logger.info(f"Audio downloaded: {output_path}")
                return output_path
            except Exception as e:
                logger.error(f"Download failed for {url}: {str(e)}")
                raise Exception(f"Download failed: {str(e)}")
