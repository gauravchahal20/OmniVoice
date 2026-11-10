import sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from gradio_client import Client
c = Client('http://127.0.0.1:8001')

text = ("I have walked through fire and come out the other side, "
        "not unburned, but unbroken. Every scar is a sentence "
        "I wrote myself, and I stand by every word.")

t0 = time.perf_counter()
res = c.predict(text, 'Auto', 'Male', 'Middle-aged', 'Low Pitch', 'Auto',
    'Auto', 'Auto', 32, 2.0, 1.0, True, True, True, api_name='/_design_fn')
elapsed = time.perf_counter() - t0
print('ELAPSED:', round(elapsed, 2), 's')
print('STATUS:', str(res[1]).replace(chr(10), ' | '))
print('FILE:', res[2])