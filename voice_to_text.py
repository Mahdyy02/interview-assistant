import numpy as np
import time

# Try to use faster-whisper (much faster), fallback to standard whisper
try:
    from faster_whisper import WhisperModel
    USE_FASTER_WHISPER = True
    print("Using faster-whisper (GPU accelerated)")
except ImportError:
    import whisper
    USE_FASTER_WHISPER = False
    print("Using standard whisper (slower)")
    print("For better performance, install: pip install faster-whisper")


# Load Whisper model
print("Loading Whisper model...")
if USE_FASTER_WHISPER:
    # faster-whisper uses GPU by default if available
    model = WhisperModel("distil-medium.en", device="cuda", compute_type="float16", num_workers=4)
    print("Model loaded on GPU!\n")
else:
    # Standard whisper
    model = whisper.load_model("base")
    print("Model loaded on CPU (slow)\n")


# Transcription worker thread
def transcription_worker(sample_rate, channels, transcription_queue, results_queue, min_audio_duration=0.5):
    """Background thread that processes transcription queue"""
    import sys
    
    while True:
        task = transcription_queue.get()
        
        if task is None:  # Poison pill to stop thread
            break
        
        audio_bytes, task_id = task
        
        try:
            # Convert to audio array for Whisper
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # Convert stereo to mono if needed
            if channels == 2:
                audio_float = audio_float.reshape(-1, 2).mean(axis=1)
            
            # Resample to 16kHz for Whisper
            if sample_rate != 16000:
                ratio = sample_rate / 16000
                indices = np.arange(0, len(audio_float), ratio).astype(int)
                audio_float = audio_float[indices]
            
            # Check if audio is long enough
            audio_duration = len(audio_float) / 16000
            if audio_duration < min_audio_duration:
                results_queue.put((task_id, ""))
                transcription_queue.task_done()
                continue
            
            # Transcribe
            start_time = time.time()
            if USE_FASTER_WHISPER:
                segments, info = model.transcribe(
                    audio_float,
                    language="en",
                    beam_size=5,
                    vad_filter=True
                )
                text = " ".join([segment.text for segment in segments]).strip()
            else:
                result = model.transcribe(
                    audio_float, 
                    fp16=False, 
                    language="en",
                    condition_on_previous_text=False
                )
                text = result["text"].strip()
            
            elapsed = time.time() - start_time
            
            # Debug: print to stderr so it doesn't interfere with main output
            # print(f"[Worker] Task #{task_id} done in {elapsed:.1f}s: '{text[:50]}...'", file=sys.stderr)
            
            results_queue.put((task_id, text))
            
        except Exception as e:
            import traceback
            print(f"\n[Transcription error for task #{task_id}: {e}]")
            traceback.print_exc()
            results_queue.put((task_id, ""))
        
        transcription_queue.task_done()