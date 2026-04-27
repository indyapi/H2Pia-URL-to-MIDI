import os
import logging
import gc
import multiprocessing
import warnings

# ปิดคำเตือน FutureWarnings ของ librosa ที่รบกวน Log
warnings.filterwarnings("ignore", category=FutureWarning, module="librosa")

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
        
        # Use torch.no_grad for better inference stability if on GPU
        with torch.no_grad():
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
    def __init__(self, device='cpu'):
        self.device = device

    def transcribe(self, audio_path, output_midi_path):
        p = multiprocessing.Process(
            target=_subprocess_transcribe_worker,
            args=(audio_path, output_midi_path, self.device)
        )
        p.start()
        return p

    def cleanup(self):
        gc.collect()
