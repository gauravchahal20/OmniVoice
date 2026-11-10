import sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import soundfile as sf
import numpy as np
from scipy.signal import resample_poly
from math import gcd

path = r'C:\Users\MSII\Documents\Instagram\Deewane - Navaan Sandhu.mp3'
data, sr = sf.read(path, dtype='float32')
if data.ndim > 1:
    data = data.mean(axis=1)

from transformers import pipeline as hf_pipeline
import torch

t0 = time.perf_counter()
pipe = hf_pipeline('automatic-speech-recognition', model='openai/whisper-small', device='cpu', dtype=torch.float32)
print('model loaded in', round(time.perf_counter()-t0,1), 's')

for start in [0, 15, 30, 60, 90, 120]:
    clip = data[int(start*sr):int((start+8)*sr)]
    g = gcd(sr, 16000)
    clip16 = resample_poly(clip, 16000 // g, sr // g)
    t0 = time.perf_counter()
    result = pipe({'array': clip16.astype('float32'), 'sampling_rate': 16000})
    print(f'[{start:3d}s-{start+8:3d}s] ({round(time.perf_counter()-t0,1)}s) -> {result["text"]!r}')