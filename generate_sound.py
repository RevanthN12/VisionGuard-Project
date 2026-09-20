"""
generate_sound.py — Generate a loud alert.wav alarm sound for Vision Guard.
Run this once: py generate_sound.py
"""
import wave
import struct
import math
import os

SAMPLE_RATE = 44100
SOUNDS_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
os.makedirs(SOUNDS_DIR, exist_ok=True)

file_path = os.path.join(SOUNDS_DIR, "alert.wav")

def sine_sample(freq, t, amplitude=0.9):
    return int(32767 * amplitude * math.sin(2.0 * math.pi * freq * t / SAMPLE_RATE))

frames = []

# Pattern: 3 urgent beeps (1000 Hz ON 0.25s → silent 0.1s) × 3, then long 1400Hz blast
for _ in range(3):
    # Beep ON — 1000 Hz, 0.25 seconds
    for i in range(int(SAMPLE_RATE * 0.25)):
        frames.append(struct.pack('<h', sine_sample(1000, i)))
    # Silence — 0.1 seconds
    for i in range(int(SAMPLE_RATE * 0.10)):
        frames.append(struct.pack('<h', 0))

# Long high-pitch blast — 1400 Hz, 0.6 seconds
for i in range(int(SAMPLE_RATE * 0.6)):
    frames.append(struct.pack('<h', sine_sample(1400, i)))

with wave.open(file_path, 'w') as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(SAMPLE_RATE)
    wav.writeframesraw(b''.join(frames))

print(f"[OK] Alert sound generated: {file_path}  ({len(frames)/SAMPLE_RATE:.2f}s)")
