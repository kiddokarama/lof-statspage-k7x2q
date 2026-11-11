#!/usr/bin/env python3
"""Fetches FPL data for the league and writes data.json (compact)."""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
LEAGUE = 553445
B = 'https://fantasy.premierleague.com/api/'
def get(path, tries=4, optional=False):
    for i in range(tries):
        try:
            req = urllib.request.Request(B + path, headers={'User-Agent': 'Mozilla/5.0'})
            return json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            if e.code == 404 and optional: return None
            time.sleep(1.5 * (i + 1))
        except Exception:
            time.sleep(1.5 * (i + 1))
    if optional: return None
    raise RuntimeError('failed ' + path)

def main(out='data.json'):
    bs = get('bootstrap-static/')
    events = bs['events']
    finished = [e['id'] for e in events if e['finished']]
    if not finished:
        print('No finished gameweek yet'); sys.exit(2)
    last = max(finished)
    nxt = next((e for e in events if e['id'] == last + 1), None)
    st, page = [], 1
    while True:
        d = get(f'leagues-classic/{LEAGUE}/standings/?page_standings={page}')
        st += d['standings']['results']
        if not d['standings']['has_next']: break
        page += 1
    league_name = d['league']['name']
    ids = [r['entry'] for r in st]
    gws = list(range(1, last + 1))
    with ThreadPoolExecutor(6) as ex:
        hist = dict(zip(ids, ex.map(lambda i: get(f'entry/{i}/history/'), ids)))
        jobs = [(i, g) for i in ids for g in gws]
        picks = dict(zip(jobs, ex.map(lambda j: get(f'entry/{j[0]}/event/{j[1]}/picks/', optional=True), jobs)))
        live = dict(zip(gws, ex.map(lambda g: get(f'event/{g}/live/'), gws)))
    picks = {k: v for k, v in picks.items() if v}
    owned = set()
    for p in picks.values():
        for x in p['picks']: owned.add(x['element'])
    teams = {t['id']: t['short_name'] for t in bs['teams']}
    players = {e['id']: [e['web_name'], teams[e['team']], e['element_type']] for e in bs['elements'] if e['id'] in owned}
    pts = {g: {str(x['id']): x['stats']['total_points'] for x in live[g]['elements'] if x['id'] in owned} for g in gws}
    mgr = []
    for r in st:
        i = r['entry']; h = hist[i]
        mgr.append({
            'id': i, 'name': r['player_name'], 'team': r['entry_name'],
            'gw': {str(c['event']): [c['points'], c['event_transfers_cost'], c['points_on_bench'], c['event_transfers'], c['total_points'], c['value'], c['bank']] for c in h['current']},
            'chips': [[c['name'], c['event']] for c in h['chips']],
            'picks': {str(g): {
                'p': [[x['element'], x['position'], x['multiplier'], int(x['is_captain']), int(x['is_vice_captain'])] for x in picks[(i, g)]['picks']],
                'chip': picks[(i, g)]['active_chip'],
                'subs': [[s['element_in'], s['element_out']] for s in picks[(i, g)]['automatic_subs']],
            } for g in gws if (i, g) in picks}})
    data = {
        'league': league_name, 'last': last,
        'next': {'id': nxt['id'], 'deadline': nxt['deadline_time']} if nxt else None,
        'updated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'players': players, 'pts': pts, 'mgr': mgr,
        'events': {str(e['id']): e['deadline_time'] for e in events},
    }
    json.dump(data, open(out, 'w'), separators=(',', ':'))
    print('ok', last, len(mgr), 'managers', len(players), 'players')

if __name__ == '__main__':
    main(*(sys.argv[1:2]))
