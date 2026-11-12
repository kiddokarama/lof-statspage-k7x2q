#!/usr/bin/env python3
"""Fetches FPL data for the league and writes data.json (compact)."""
import json, sys, time, base64, urllib.request
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

def shirt(code):
    for i in range(3):
        try:
            req = urllib.request.Request(f'https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_{code}-66.png', headers={'User-Agent': 'Mozilla/5.0'})
            return 'data:image/png;base64,' + base64.b64encode(urllib.request.urlopen(req, timeout=30).read()).decode()
        except Exception:
            time.sleep(1.5)
    return ''

def main(out='data.json'):
    bs = get('bootstrap-static/')
    events = bs['events']
    now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    started = [e['id'] for e in events if e['deadline_time'] and e['deadline_time'] <= now_iso]
    if not started:
        print('No gameweek has started yet'); sys.exit(2)
    last = max(started)   # latest gameweek whose deadline has passed (may still be in progress)
    finished = [e['id'] for e in events if e['finished']]
    fin = max(finished) if finished else 0
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
    # fixture info per gameweek: matches, matches played, double / blank teams
    fixtures = get('fixtures/')
    tshort = {t['id']: t['short_name'] for t in bs['teams']}
    evinfo = {}
    for e in events:
        fx = [f for f in fixtures if f['event'] == e['id']]
        cnt = {}
        for f in fx:
            for t in (f['team_h'], f['team_a']): cnt[t] = cnt.get(t, 0) + 1
        evinfo[str(e['id'])] = {
            'f': int(bool(e['finished'])), 'x': len(fx), 'p': sum(1 for f in fx if f.get('finished')),
            'd': sorted(tshort[t] for t, n in cnt.items() if n >= 2),
            'b': sorted(tshort[t] for t in tshort if fx and t not in cnt)}
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
    px = {}
    for e in bs['elements']:
        if e['id'] in owned:
            px[e['id']] = [e['now_cost'], float(e['selected_by_percent']), e['total_points'], e['goals_scored'], e['assists'], e['clean_sheets'],
                           e['minutes'], e['bonus'], float(e['form']), float(e['points_per_game']), e['yellow_cards'], e['red_cards'], e['saves'],
                           e['news'] or '', e['status'], e['starts'], float(e['expected_goals'] or 0), float(e['expected_assists'] or 0), e['goals_conceded'], e['own_goals'], e['penalties_saved'] + e['penalties_missed']]
    codes = {t['short_name']: t['code'] for t in bs['teams']}
    with ThreadPoolExecutor(6) as ex:
        sh = dict(zip(codes, ex.map(lambda c: shirt(codes[c]), codes)))
    tid = {t['id']: t['short_name'] for t in bs['teams']}
    fx = [[f['event'], f['kickoff_time'], tid[f['team_h']], tid[f['team_a']], f['team_h_score'], f['team_a_score'], int(bool(f['finished'] or f.get('finished_provisional'))),
           f['team_h_difficulty'], f['team_a_difficulty'], int(bool(f['started']))] for f in fixtures if f['event']]
    tn = {t['short_name']: t['name'] for t in bs['teams']}
    data = {
        'league': league_name, 'last': last, 'fin': fin, 'ev': evinfo,
        'next': {'id': nxt['id'], 'deadline': nxt['deadline_time']} if nxt else None,
        'updated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'players': players, 'tc': {t['short_name']: t['code'] for t in bs['teams']}, 'pts': pts, 'mgr': mgr,
        'events': {str(e['id']): e['deadline_time'] for e in events},
        'livefn': '/.netlify/functions/live', 'px': px, 'sh': sh, 'fx': fx, 'tn': tn, 'nxt_all': [e['id'] for e in events],
    }
    json.dump(data, open(out, 'w'), separators=(',', ':'))
    print('ok', 'last', last, 'finished', fin, len(mgr), 'managers', len(players), 'players')

if __name__ == '__main__':
    main(*(sys.argv[1:2]))
