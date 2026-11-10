import sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import soundfile as sf
import numpy as np
from scipy.signal import resample_poly
from math import gcd

# Extract a clean vocal clip (60s-68s) from the song
path = r'C:\Users\MSII\Documents\Instagram\Deewane - Navaan Sandhu.mp3'
data, sr = sf.read(path, dtype='float32')
if data.ndim > 1:
    data = data.mean(axis=1)

start, dur = 60.0, 8.0
clip = data[int(start*sr):int((start+dur)*sr)]
print('clip duration:', round(len(clip)/sr,2), 's')

# Save as 24kHz mono wav (model's native rate)
target_sr = 24000
g = gcd(sr, target_sr)
clip24 = resample_poly(clip, target_sr // g, sr // g)
clip_path = r'C:\Users\MSII\OMNIVOICE\ref_clip.wav'
sf.write(clip_path, clip24.astype('float32'), target_sr)
print('saved:', clip_path, len(clip24), 'samples')

# Now generate cloned audio
import app
app.load_model()
ref_text = 'नी ते गाऊन नी चाड देस वेरे तेरी रीष लाऊन नी नी पानी जीवे मुल कोई करी'

target_text = """Dass Putt Tera Head Down Kaston
Changa Bhala Hassda Si Maun Kaston
Aa Jehde Darwaje Vich Board Chakki Khade Aa
Main Changi Tarah Jaanda Aa Kaun Kaston

Tell me, son, whose head is held down in sorrow,
Once he laughed and stayed silent in sorrow.
Those who stand in the doorway with a signboard,
I know well who is who, no need to inquire.

Kuch Aithe Chandi Chamkauna Chaunde Ne
Kuch Tainu Fadd Thalle Launa Chaunde Ne
Kuch Ek Aaye Aithe Bukhe Fame De
Naam Laike Tera Agge Aune Chaunde Ne"""

t0 = time.perf_counter()
audio, status, out_path, _ = app.generate(
    target_text, 'Auto', 'clone',
    ref_audio=clip_path,
    ref_text=ref_text,
    num_step=32,
)
elapsed = time.perf_counter() - t0
print('ELAPSED:', round(elapsed, 2), 's')
print('STATUS:', status.replace(chr(10), ' | '))
print('OUTPUT:', out_path)