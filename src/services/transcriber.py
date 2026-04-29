import os
import logging
import gc
import multiprocessing
import warnings

# ปิดคำเตือน FutureWarnings ของ librosa ที่รบกวน Log
warnings.filterwarnings("ignore", category=FutureWarning, module="librosa")

logger = logging.getLogger(__name__)

def _subprocess_transcribe_worker(audio_path, output_midi_path, device):
    """
    กระบวนการนี้ทำงานใน Process แยก เพื่อคืน RAM 100% หลังจบงาน
    """
    try:
        # ย้ายการ Import เข้ามาข้างในเพื่อไม่ให้โปรแกรมหลักโหลดไลบรารีหนักๆ
        import warnings
        warnings.filterwarnings("ignore", category=FutureWarning)
        
        from piano_transcription_inference import PianoTranscription, sample_rate, load_audio
        import torch
        import numpy as np
        
        transcriber = PianoTranscription(device=device)
        
        # Load audio and automatically resample to 16kHz
        (audio, _) = load_audio(audio_path, sr=sample_rate, mono=True)
        
        # Normalize audio levels to improve AI accuracy and register detection
        # This helps the AI better differentiate between loud harmonics and actual notes
        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio))
        
        # Perform transcription
        transcriber.transcribe(audio, output_midi_path)
        
        # Cleanup
        del audio
        del transcriber
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
    except Exception as e:
        print(f"Subprocess Error: {e}")
        os._exit(1)

class TranscriptionService:
    def __init__(self, device=None):
        # Auto-detect device if not provided
        if device is None:
            import torch
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        logger.info(f"TranscriptionService initialized using device: {self.device}")

    def transcribe(self, audio_path, output_midi_path):
        p = multiprocessing.Process(
            target=_subprocess_transcribe_worker,
            args=(audio_path, output_midi_path, self.device)
        )
        p.start()
        return p

    def cleanup(self):
        gc.collect()
