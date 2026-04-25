import os
import logging
from piano_transcription_inference import PianoTranscription, sample_rate, load_audio

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(self, device='cpu'):
        # device can be 'cuda' if GPU is available
        logger.info(f"Initializing TranscriptionService on {device}")
        self.transcriber = PianoTranscription(device=device)

    def transcribe(self, audio_path, output_midi_path):
        """Transcribes audio file to MIDI."""
        try:
            logger.info(f"Starting transcription: {audio_path} -> {output_midi_path}")
            # Load audio
            (audio, _) = load_audio(audio_path, sr=sample_rate, mono=True)

            # Transcribe
            self.transcriber.transcribe(audio, output_midi_path)
            
            logger.info(f"Transcription complete: {output_midi_path}")
            return output_midi_path
        except Exception as e:
            logger.error(f"Transcription failed for {audio_path}: {str(e)}")
            raise Exception(f"Transcription failed: {str(e)}")
