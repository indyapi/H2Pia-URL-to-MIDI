import os
import logging
import gc
try:
    import torch
except ImportError:
    torch = None

from piano_transcription_inference import PianoTranscription, sample_rate, load_audio

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(self, device='cpu'):
        logger.info(f"Initializing TranscriptionService on {device}")
        self.device = device
        self.transcriber = PianoTranscription(device=device)

    def transcribe(self, audio_path, output_midi_path):
        """Transcribes audio file to MIDI."""
        try:
            logger.info(f"Starting transcription: {audio_path}")
            (audio, _) = load_audio(audio_path, sr=sample_rate, mono=True)
            self.transcriber.transcribe(audio, output_midi_path)
            
            # Clear local large array immediately
            del audio
            logger.info(f"Transcription complete: {output_midi_path}")
            return output_midi_path
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise Exception(f"Transcription failed: {str(e)}")

    def cleanup(self):
        """Explicitly release model and clear cache."""
        logger.info("Cleaning up TranscriptionService resources...")
        try:
            if hasattr(self, 'transcriber'):
                del self.transcriber
            
            if torch is not None:
                if self.device == 'cuda' and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                # Force torch to release memory if possible
                # (Note: CPU memory is harder to force-release, but deleting references helps)
                
            gc.collect()
        except Exception as e:
            logger.error(f"Error during service cleanup: {e}")
