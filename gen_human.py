import sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from gradio_client import Client
c = Client('http://127.0.0.1:8001')

text = ("Zindagi ek safar hai jo har din naye mod lekar aata hai. "
        "Kabhi khushi milti hai, kabhi gham. Lekin jo insaan apne sapno ke peeche "
        "chalta hai, woh kabhi haar nahi maanta. Har mushkil ek naya sabaq deti hai, "
        "aur har sabaq humein aur mazboot banata hai. Socho, agar aap apni zindagi "
        "ko ek kitaab samjho, toh har din ek naya page hai. Aap us page ko kaise "
        "likhna chahte ho, yeh aapke haath mein hai. Toh utho, chalo, aur apni "
        "kahani likho jo duniya yaad rakhe.")

# Soft settings: low guidance, no postprocess (keeps natural pauses)
t0 = time.perf_counter()
res = c.predict(text, 'Hindi', 'Male', 'Middle-aged', 'Low Pitch', 'Auto',
    'Auto', 'Auto', 32, 1.0, 1.0, True, True, False, api_name='/_design_fn')
elapsed = time.perf_counter() - t0
print('ELAPSED:', round(elapsed, 2), 's')
print('STATUS:', str(res[1]).replace(chr(10), ' | '))
print('FILE:', res[2])