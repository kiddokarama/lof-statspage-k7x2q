#!/usr/bin/env python3
"""Builds index.html from template.html + data.json."""
import json, sys
d = json.load(open('data.json'))
t = open('template.html', encoding='utf-8').read()
out = t.replace('/*__DATA__*/null', json.dumps(d, separators=(',', ':'), ensure_ascii=False).replace('</', '<\\/'))
open(sys.argv[1] if len(sys.argv) > 1 else 'index.html', 'w', encoding='utf-8').write(out)
print('built', len(out))
