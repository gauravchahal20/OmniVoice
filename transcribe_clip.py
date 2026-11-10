import sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import soundfile as sf
import numpy as np
import torch

path = r'C:\Users\MSII\Documents\Instagram\Deewane - Navaan Sandhu.mp3'
data, sr = sf.read(path, dtype='float32')
print('loaded:', data.shape, sr, 'duration:', round(len(data)/sr,2))

# Convert to mono
if data.ndim > 1:
    data = data.mean(axis=1)

# Extract a clip: try 5s starting at 5s (skip possible intro)
start = 5.0
dur = 8.0
s = int(start * sr)
e = int((start + dur) * sr)
clip = data[s:e]
print('clip:', len(clip), 'samples,', round(len(clip)/sr,2), 's')

# Resample to 16k for Whisper
from scipy.signal import resample_poly
from math import gcd
target_sr = 16000
g = gcd(sr, target_sr)
clip16 = resample_poly(clip, target_sr // g, sr // g)
print('resampled:', len(clip16), 'samples at', target_sr)

# Transcribe on CPU
from transformers import pipeline as hf_pipeline
t0 = time.perf_counter()
pipe = hf_pipeline('automatic-speech-recognition', model='openai/whisper-small', device='cpu', dtype=torch.float32)
print('model loaded in', round(time.perf_counter()-t0,1), 's')
t0 = time.perf_counter()
result = pipe({'array': clip16.astype('float32'), 'sampling_rate': target_sr})
print('transcribed in', round(time.perf_counter()-t0,1), 's')
print('TRANSCRIPT:', repr(result['text']))