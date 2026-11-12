#!/usr/bin/env python3
"""Decides whether the site needs a fresh Netlify deploy (each deploy costs 15 of the free plan's 300 monthly credits).
Writes public/version.txt and sets deploy=true/false for the workflow."""
import hashlib, json, os, sys, urllib.request
SITE = 'https://lof-k7x2q-stats.netlify.app'
d = json.load(open('data.json'))
code = hashlib.sha256()
for f in ('template.html', 'build.py', 'fetch.py', 'netlify/functions/live.js'):
    try: code.update(open(f, 'rb').read())
    except FileNotFoundError: pass
nxt = d['next'] or {}
sig = f"last={d['last']};fin={d['fin']};next={nxt.get('id')}@{nxt.get('deadline')};code={code.hexdigest()[:12]}"
os.makedirs('public', exist_ok=True)
open('public/version.txt', 'w').write(sig)
try:
    live = urllib.request.urlopen(urllib.request.Request(SITE + '/version.txt?x=' + hashlib.md5(sig.encode()).hexdigest(), headers={'User-Agent': 'Mozilla/5.0'}), timeout=20).read().decode().strip()
except Exception as e:
    live = ''; print('could not read live version:', e)
force = os.environ.get('FORCE') == 'true'
deploy = force or live != sig
print('live :', live); print('new  :', sig); print('deploy:', deploy)
if os.environ.get('GITHUB_OUTPUT'):
    open(os.environ['GITHUB_OUTPUT'], 'a').write(f"deploy={'true' if deploy else 'false'}\n")
