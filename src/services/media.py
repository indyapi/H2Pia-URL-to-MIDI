import os
import yt_dlp
import logging

logger = logging.getLogger(__name__)

class MediaService:
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
            'noplaylist': True,
            'extract_flat': False,
            'fragment_retries': 10,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                # If it's a playlist-like structure, get the first entry
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]
                
                # Ensure thumbnail is a string if it exists
                thumbnail = info.get('thumbnail')
                if isinstance(thumbnail, list) and thumbnail:
                    thumbnail = thumbnail[0].get('url')
                elif isinstance(thumbnail, dict):
                    thumbnail = thumbnail.get('url')
                
                return {
                    'title': info.get('title') or info.get('id') or 'Unknown Title',
                    'thumbnail': thumbnail,
                    'duration': info.get('duration'),
                    'id': info.get('id')
                }
            except Exception as e:
                logger.error(f"Failed to fetch metadata: {str(e)}")
                raise Exception(f"Failed to fetch metadata: {str(e)}")

    def get_unique_path(self, folder, filename, extension):
        """Generates a unique path by adding v2, v3... if file exists."""
        base_path = os.path.join(folder, f"{filename}.{extension}")
        if not os.path.exists(base_path):
            return base_path
        
        counter = 2
        while True:
            new_path = os.path.join(folder, f"{filename} v{counter}.{extension}")
            if not os.path.exists(new_path):
                return new_path
            counter += 1

    def download(self, url, output_path_no_ext, format_type):
        """
        Downloads media based on format_type.
        """
        logger.info(f"Downloading {format_type} from {url}")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'outtmpl': output_path_no_ext,
            'fragment_retries': 10,
        }

        # --- AUDIO FORMATS ---
        audio_map = {
            'OPUS': 'opus', 'AAC': 'm4a', 'MP3': 'mp3', 
            'FLAC': 'flac', 'WAV': 'wav'
        }
        
        if format_type in audio_map:
            codec = audio_map[format_type]
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': codec,
                    'preferredquality': '192',
                }],
            })
        
        # --- VIDEO FORMATS ---
        elif format_type == 'MP4_FULL':
            ydl_opts.update({'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'})
        elif format_type == 'MP4_1080P':
            ydl_opts.update({'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best'})
        elif format_type == 'MP4_720P':
            ydl_opts.update({'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'})
        elif format_type == 'MP4_VIDEO_ONLY':
            ydl_opts.update({'format': 'bestvideo[ext=mp4]'})
            
        # --- MIDI MODE ---
        elif format_type == 'MIDI':
            ydl_opts.update({
                'format': 'bestaudio/best', # Get highest quality regardless of bitrate
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                }],
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                actual_filename = ydl.prepare_filename(info)
                # handle extension changes from postprocessors
                if 'postprocessors' in ydl_opts:
                    ext = ydl_opts['postprocessors'][0]['preferredcodec']
                    actual_filename = os.path.splitext(actual_filename)[0] + f".{ext}"
                return actual_filename
            except Exception as e:
                logger.error(f"Download failed: {str(e)}")
                raise Exception(f"Download failed: {str(e)}")
