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
        
        # ปรับแก้การเรียกใช้งานให้ทันสมัย (ถ้าเราเรียกเอง) หรือปิด warning ถ้า library เรียก
        # library 'piano_transcription_inference' มักจะเรียก resample แบบ positional
        
        transcriber = PianoTranscription(device=device)
        (audio, _) = load_audio(audio_path, sr=sample_rate, mono=True)
        
        # เริ่มการถอดรหัส
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
