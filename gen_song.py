import sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

text = """Dass Putt Tera Head Down Kaston
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

from gradio_client import Client
c = Client('http://127.0.0.1:8001')
t0 = time.perf_counter()
res = c.predict(text, 'Auto', 32, 2.0, 1.0, True, True, True, api_name='/_auto_fn')
elapsed = time.perf_counter() - t0
print('ELAPSED:', round(elapsed, 2), 's')
print('STATUS:', str(res[1]).replace(chr(10), ' | '))
print('FILE:', res[2])