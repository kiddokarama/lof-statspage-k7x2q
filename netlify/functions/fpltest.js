// Test only: checks whether FPL answers requests coming from Netlify's servers.
const B = 'https://fantasy.premierleague.com/api/';
const paths = ['bootstrap-static/', 'event/10/live/', 'leagues-classic/553445/standings/', 'fixtures/?event=10'];
exports.handler = async () => {
  const out = [];
  for (const p of paths) {
    const t = Date.now();
    try {
      const r = await fetch(B + p, { headers: { 'User-Agent': 'Mozilla/5.0' } });
      const txt = await r.text();
      out.push({ path: p, status: r.status, bytes: txt.length, ms: Date.now() - t, head: r.status === 200 ? '' : txt.slice(0, 120) });
    } catch (e) {
      out.push({ path: p, error: String(e), ms: Date.now() - t });
    }
  }
  return { statusCode: 200, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' }, body: JSON.stringify({ node: process.version, region: process.env.AWS_REGION || null, results: out }, null, 1) };
};
