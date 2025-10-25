import pyaudiowpatch as pyaudio
import keyboard
import wave
import numpy as np
import time
import threading
from queue import Queue
from voice_to_text import transcription_worker
from transcript_window import TranscriptWindow
from ai import generate_chatbot_response
from prompt import system_prompt
import asyncio
from rag import initialize_rag, retrieve_context

# Queues for threading
transcription_queue = Queue()  # Audio chunks to transcribe
results_queue = Queue()  # Transcription results

# Configuration
filename = "meeting_audio.wav"
silence_threshold = 500  # Adjust as needed (int16 PCM amplitude)
silence_duration = 0.5   # seconds to wait before printing accumulated text
process_interval = 3.0   # Process audio every 3 seconds
min_audio_duration = 0.5  # Minimum audio duration to transcribe (seconds)

# Initialize PyAudio
p = pyaudio.PyAudio()

# Get default WASAPI info
try:
    # Get default WASAPI output device (what's playing through speakers)
    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
    
    # Check if loopback is available
    if not default_speakers["isLoopbackDevice"]:
        # Find the loopback device for the default output
        for loopback in p.get_loopback_device_info_generator():
            if default_speakers["name"] in loopback["name"]:
                default_speakers = loopback
                break
    
    print(f"Recording from: {default_speakers['name']}")
    print(f"Channels: {default_speakers['maxInputChannels']}")
    print(f"Sample Rate: {int(default_speakers['defaultSampleRate'])} Hz\n")
    
    # Set up recording parameters
    channels = default_speakers["maxInputChannels"]
    sample_rate = int(default_speakers["defaultSampleRate"])
    
    # Open stream
    stream = p.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=sample_rate,
        input=True,
        input_device_index=default_speakers["index"],
        frames_per_buffer=1024
    )
    
    print("=== Real-time Transcription Started ===")
    print(f"Processing audio every {process_interval}s")
    print(f"Printing accumulated text after {silence_duration}s of silence")
    print("Opening GUI window...")
    print("Press Ctrl+C to stop\n")
    
    # Initialize RAG system (one-time setup)
    print("\n" + "="*60)
    print("="*60)
    if initialize_rag():
        print("✅ RAG system ready! Answers will be personalized with your background.\n")
    else:
        print("⚠️ RAG system failed to initialize. Will continue without context enhancement.")
        print("   To enable RAG, fill in documents/cv.txt, projects.txt, and experiences.txt\n")
    
    # Define AI callback function
    def handle_ai_request(transcript_text):
        """Handle AI processing request from GUI button (with RAG context)"""
        try:
            print(f"\n[AI] Processing transcript ({len(transcript_text)} chars)...")
            transcript_window.update_status("Retrieving relevant context...")
            
            # Retrieve relevant context from RAG system (fast: <200ms)
            context = retrieve_context(transcript_text, top_k=3)
            
            if context:
                print(f"[RAG] Retrieved context ({len(context)} chars)")
            
            transcript_window.update_status("Waiting for AI response...")
            
            # Run async function in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            response = loop.run_until_complete(
                generate_chatbot_response(
                    system_prompt=system_prompt,
                    user_message=transcript_text,
                    temperature=0.7,
                    max_tokens=500,
                    context=context  # Add RAG context
                )
            )
            
            loop.close()
            
            if response:
                print(f"[AI] Got response ({len(response)} chars)")
                transcript_window.add_conversation_message("AI", response)
                transcript_window.update_status("AI response received!")
            else:
                transcript_window.add_conversation_message("AI", "⚠️ No response from AI")
                transcript_window.update_status("AI request failed")
                
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            print(f"[AI Error] {e}")
            transcript_window.add_conversation_message("AI", error_msg)
            transcript_window.update_status("AI error occurred")
    
    # Create GUI window with AI callback (will run in main thread)
    transcript_window = TranscriptWindow(ai_callback=handle_ai_request)
    transcript_window.update_status("Initialized - Waiting for audio...")
    
    # Define audio recording function to run in background thread
    def audio_recording_loop():
        # Start transcription worker thread
        worker = threading.Thread(
            target=transcription_worker, 
            args=(sample_rate, channels, transcription_queue, results_queue, min_audio_duration),
            daemon=True
        )
        worker.start()
        
        # Audio buffers
        current_chunk = []      # Current 3-second chunk being collected
        all_frames = []         # All audio for saving
        accumulated_text = []   # Text segments collected in current speech period
        
        # Timing and state
        last_sound_time = time.time()
        last_process_time = time.time()
        recording_start = time.time()
        last_status_time = time.time()
        has_sound = False
        task_counter = 0
        pending_tasks = set()  # Track which tasks are pending
        
        try:
            while True:
                # Read audio chunk
                data = stream.read(1024, exception_on_overflow=False)
                current_chunk.append(data)
                all_frames.append(data)
                
                # Convert byte data to numpy array for amplitude analysis
                audio_data = np.frombuffer(data, dtype=np.int16)
                max_amplitude = np.abs(audio_data).max()
                
                # Update last sound time if audio detected
                if max_amplitude > silence_threshold:
                    last_sound_time = time.time()
                    has_sound = True
                
                # Check for completed transcription results (non-blocking)
                # Process ALL available results
                results_collected = 0
                while not results_queue.empty():
                    task_id, text = results_queue.get()
                    pending_tasks.discard(task_id)
                    results_collected += 1
                    
                    if text:
                        accumulated_text.append(text)
                        # Don't print individual results, just accumulate silently
                
                # Show status every 2 seconds
                if time.time() - last_status_time > 2:
                    elapsed = int(time.time() - recording_start)
                    chunk_duration = len(current_chunk) * 1024 / sample_rate
                    silence_elapsed = time.time() - last_sound_time
                    queue_size = transcription_queue.qsize()
                    pending_count = len(pending_tasks)
                    
                    if has_sound and silence_elapsed < silence_duration:
                        status = f"Recording... {elapsed}s | Chunk: {chunk_duration:.1f}s | Level: {max_amplitude}"
                        if len(accumulated_text) > 0:
                            status += f" | Got: {len(accumulated_text)} segments"
                        # Update GUI
                        transcript_window.update_status(f"Recording... | Audio level: {max_amplitude} | Segments: {len(accumulated_text)}")
                    elif has_sound:
                        status = f"Silence: {silence_elapsed:.1f}s / {silence_duration:.1f}s | Got: {len(accumulated_text)} segments"
                        # Update GUI
                        transcript_window.update_status(f"Silence detected: {silence_elapsed:.1f}s / {silence_duration:.1f}s")
                    else:
                        status = f"Waiting... {elapsed}s | Level: {max_amplitude}"
                        # Update GUI
                        transcript_window.update_status(f"Waiting for audio... | Level: {max_amplitude}")
                    
                    if queue_size > 0 or pending_count > 0:
                        status += f" | Processing: {pending_count}"
                    
                    print(status)
                    last_status_time = time.time()
                
                # Process audio every 3 seconds (or when chunk gets too large)
                time_since_last_process = time.time() - last_process_time
                if time_since_last_process >= process_interval and len(current_chunk) > 0:
                    chunk_duration = len(current_chunk) * 1024 / sample_rate
                    
                    if chunk_duration >= min_audio_duration:
                        # Queue this chunk for transcription in background
                        audio_bytes = b''.join(current_chunk)
                        task_counter += 1
                        pending_tasks.add(task_counter)
                        transcription_queue.put((audio_bytes, task_counter))
                        # Silently queue - don't print, just process in background
                    
                    # Reset chunk
                    current_chunk = []
                    last_process_time = time.time()
                
                # Check for silence to print accumulated text
                silence_time = time.time() - last_sound_time
                if silence_time > silence_duration and has_sound:
                    # Start timing latency from silence detection to text display
                    latency_start = time.time()
                    
                    # Wait for any pending transcriptions to complete
                    if len(pending_tasks) > 0:
                        print(f"\n[Silence detected - Waiting for {len(pending_tasks)} pending transcriptions...]", end=" ", flush=True)
                        transcript_window.update_status(f"Processing {len(pending_tasks)} transcriptions...")
                        
                        # Wait for all transcriptions to finish
                        max_wait = 30  # Max 30 seconds total
                        wait_start = time.time()
                        
                        while len(pending_tasks) > 0 and (time.time() - wait_start) < max_wait:
                            # Collect all available results
                            collected_this_loop = 0
                            while not results_queue.empty():
                                task_id, text = results_queue.get()
                                pending_tasks.discard(task_id)
                                collected_this_loop += 1
                                if text:
                                    accumulated_text.append(text)
                            
                            if len(pending_tasks) > 0:
                                time.sleep(0.2)  # Small delay before checking again
                        
                        if len(pending_tasks) > 0:
                            print(f"Timeout! Still waiting for {len(pending_tasks)} tasks")
                        else:
                            print("Done")
                    
                    # Collect any remaining results one more time
                    while not results_queue.empty():
                        task_id, text = results_queue.get()
                        if text:
                            accumulated_text.append(text)
                    
                    # Display the complete accumulated transcription
                    if len(accumulated_text) > 0:
                        full_text = " ".join(accumulated_text)
                        
                        # Calculate latency from silence detection to now
                        latency = time.time() - latency_start
                        
                        # Print to console
                        print(f"\n{'='*60}")
                        print(f">> {full_text}")
                        print(f"{'='*60}")
                        print(f"[Latency: {latency:.2f}s from silence detection to text display]\n")
                        
                        # Display in GUI window
                        transcript_window.append_text(full_text)
                        transcript_window.update_status(f"Transcription complete!")
                        transcript_window.update_latency(f"{latency:.2f}s")
                    else:
                        latency = time.time() - latency_start
                        print(f"\n[No transcription results received - Latency: {latency:.2f}s]\n")
                        transcript_window.update_status("No speech detected")
                    transcript_window.update_latency(f"{latency:.2f}s")
                
                    # Reset for next speech period
                    accumulated_text = []
                    has_sound = False
                    pending_tasks.clear()  # Clear any stuck tasks
                    last_sound_time = time.time()
                    
        except KeyboardInterrupt:
            print("\n\nCtrl+C pressed - Stopping recording...")
        
        # Stop and close stream
        print("\nStopping stream...")
        stream.stop_stream()
        stream.close()
        p.terminate()
        print("Stream closed.")
    
        # Process any remaining audio in current chunk
        if len(current_chunk) > 0:
            chunk_duration = len(current_chunk) * 1024 / sample_rate
            if chunk_duration >= min_audio_duration:
                print(f"\n[Processing final chunk: {chunk_duration:.1f}s]")
                audio_bytes = b''.join(current_chunk)
                task_counter += 1
                pending_tasks.add(task_counter)
                transcription_queue.put((audio_bytes, task_counter))
        
        # Wait for all pending transcriptions
        if len(pending_tasks) > 0:
            print(f"Waiting for {len(pending_tasks)} pending transcriptions...")
            transcription_queue.join()
            
            # Collect remaining results silently
            while not results_queue.empty():
                task_id, text = results_queue.get()
                if text:
                    accumulated_text.append(text)
        
        # Print any remaining accumulated text
        if len(accumulated_text) > 0:
            full_text = " ".join(accumulated_text)
            print(f"\n{'='*60}")
            print(f">> FINAL: {full_text}")
            print(f"{'='*60}\n")
            transcript_window.append_text(f"FINAL: {full_text}")
        
        # Stop transcription worker
        transcription_queue.put(None)
        
        # Save to file (all recorded audio)
        if all_frames:
            print(f"Saving all recorded audio to {filename}...")
            wf = wave.open(filename, 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(sample_rate)
            wf.writeframes(b''.join(all_frames))
            wf.close()
            print(f"Saved to: {filename}")
        
        print("\n=== Recording complete! ===")
        transcript_window.update_status("Recording stopped")
    
    # End of audio_recording_loop function
    
    # Start audio recording in background thread
    recording_thread = threading.Thread(target=audio_recording_loop, daemon=True)
    recording_thread.start()
    
    # Run GUI in main thread (required for Windows)
    transcript_window.run()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    p.terminate()
