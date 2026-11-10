import sys, time, shutil, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from gradio_client import Client
c = Client('http://127.0.0.1:8001')

text = "Zindagi ek safar hai jo har din naye mod lekar aata hai."

variants = [
    ("default", "Male", "Middle-aged", "Low Pitch", 32, 2.0, True, True),
    ("soft", "Male", "Middle-aged", "Low Pitch", 32, 1.0, True, False),
    ("natural", "Male", "Middle-aged", "Low Pitch", 16, 1.5, True, True),
    ("female", "Female", "Young Adult", "Moderate Pitch", 32, 1.5, True, True),
]

for name, gender, age, pitch, steps, gs, dn, po in variants:
    t0 = time.perf_counter()
    res = c.predict(text, 'Hindi', gender, age, pitch, 'Auto', 'Auto', 'Auto',
        steps, gs, 1.0, dn, True, po, api_name='/_design_fn')
    elapsed = time.perf_counter() - t0
    src = res[2]
    dst = f"C:/Users/MSII/OMNIVOICE/variant_{name}.wav"
    shutil.copy2(src, dst)
    print(f"[{name}] steps={steps} gs={gs} dn={dn} post={po} -> {round(elapsed,2)}s | file={dst}")