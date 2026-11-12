// Live scores for the League of Football page.
// Reads FPL's public API and works out each manager's gameweek points right now
// (captain doubling, vice-captain cover, automatic substitutions, chips, hits).
const B = 'https://fantasy.premierleague.com/api/';
const LEAGUE = 553445;
const H = { 'User-Agent': 'Mozilla/5.0' };

async function api(path, tries = 3) {
  let err;
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(B + path, { headers: H });
      if (r.ok) return await r.json();
      err = new Error(path + ' -> ' + r.status);
    } catch (e) { err = e; }
    await new Promise(r => setTimeout(r, 400 * (i + 1)));
  }
  throw err;
}

// kept between calls while the function stays warm
const memo = { boot: null, bootAt: 0, picks: new Map(), entries: null, entriesAt: 0 };

async function bootstrap() {
  if (!memo.boot || Date.now() - memo.bootAt > 3600e3) {
    const b = await api('bootstrap-static/');
    memo.boot = { team: new Map(b.elements.map(e => [e.id, e.team])), pos: new Map(b.elements.map(e => [e.id, e.element_type])) };
    memo.bootAt = Date.now();
  }
  return memo.boot;
}
async function entries() {
  if (!memo.entries || Date.now() - memo.entriesAt > 6 * 3600e3) {
    const out = []; let page = 1;
    for (;;) {
      const d = await api(`leagues-classic/${LEAGUE}/standings/?page_standings=${page}`);
      out.push(...d.standings.results.map(r => r.entry));
      if (!d.standings.has_next) break;
      page++;
    }
    memo.entries = out; memo.entriesAt = Date.now();
  }
  return memo.entries;
}
async function picksOf(id, gw) {
  const k = gw + ':' + id, c = memo.picks.get(k);
  if (c && Date.now() - c.at < 6 * 3600e3) return c.v;
  const v = await api(`entry/${id}/event/${gw}/picks/`);
  memo.picks.set(k, { v, at: Date.now() });
  return v;
}

// gross points for one manager, given the live numbers
function score(p, live, teamOf, posOf, done) {
  const pk = p.picks, chip = p.active_chip;
  const pts = id => (live.get(id) || {}).total_points || 0;
  const mins = id => (live.get(id) || {}).minutes || 0;
  const mult = new Map(pk.map(x => [x.element, x.multiplier]));
  let xi = pk.filter(x => x.position <= 11).map(x => x.element);
  const bench = pk.filter(x => x.position > 11).sort((a, b) => a.position - b.position).map(x => x.element);
  if (chip === 'bboost') {
    bench.forEach(id => { if (!mult.get(id)) mult.set(id, 1); });
    xi = xi.concat(bench);
  } else {
    const cnt = k => xi.filter(id => posOf(id) === k).length;
    const valid = (list) => { const c = k => list.filter(id => posOf(id) === k).length; return c(1) === 1 && c(2) >= 3 && c(3) >= 2 && c(4) >= 1; };
    const used = new Set();
    for (const out of xi.slice()) {
      if (mins(out) > 0 || !done(out)) continue;
      for (const b of bench) {
        if (used.has(b) || mins(b) === 0) continue;
        if ((posOf(out) === 1) !== (posOf(b) === 1)) continue;
        const next = xi.map(id => id === out ? b : id);
        if (!valid(next)) continue;
        xi = next; used.add(b); mult.set(out, 0); mult.set(b, 1);
        break;
      }
    }
  }
  // armband: vice-captain takes over if the captain never played
  const cap = pk.find(x => x.is_captain), vc = pk.find(x => x.is_vice_captain);
  if (cap && vc && xi.includes(cap.element) && mins(cap.element) === 0 && done(cap.element) && mins(vc.element) > 0 && xi.includes(vc.element)) {
    mult.set(vc.element, cap.multiplier); mult.set(cap.element, 1);
  }
  return xi.reduce((a, id) => a + pts(id) * (mult.get(id) || 0), 0);
}

async function compute(gw) {
  const [boot, live, fixtures, ids] = await Promise.all([bootstrap(), api(`event/${gw}/live/`), api(`fixtures/?event=${gw}`), entries()]);
  const liveMap = new Map(live.elements.map(e => [e.id, e.stats]));
  const fx = {};
  fixtures.forEach(f => [f.team_h, f.team_a].forEach(t => (fx[t] = fx[t] || []).push(!!(f.finished || f.finished_provisional))));
  const teamDone = t => !fx[t] || fx[t].every(Boolean);
  const done = id => teamDone(boot.team.get(id));
  const posOf = id => boot.pos.get(id);
  const scores = {}, pts = {};
  const res = await Promise.all(ids.map(async id => { try { return [id, await picksOf(id, gw)]; } catch (e) { return [id, null]; } }));
  for (const [id, p] of res) {
    if (!p) continue;
    scores[id] = [score(p, liveMap, id2 => boot.team.get(id2), posOf, done), p.entry_history.event_transfers_cost || 0];
    p.picks.forEach(x => { pts[x.element] = (liveMap.get(x.element) || {}).total_points || 0; });
  }
  return { scores, pts, p: fixtures.filter(f => f.finished || f.finished_provisional).length, x: fixtures.length, ts: Date.now() };
}

exports.compute = compute;
exports.handler = async (event) => {
  const gw = parseInt((event.queryStringParameters || {}).gw, 10);
  if (!(gw >= 1 && gw <= 38)) return { statusCode: 400, body: 'gw?' };
  try {
    const body = JSON.stringify(await compute(gw));
    return { statusCode: 200, body, headers: { 'content-type': 'application/json', 'cache-control': 'public, max-age=0, must-revalidate', 'netlify-cdn-cache-control': 'public, s-maxage=45, stale-while-revalidate=60' } };
  } catch (e) {
    return { statusCode: 502, body: JSON.stringify({ error: String(e) }), headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } };
  }
};
