from flask import Flask, request, url_for
import html, os, json
import search_engine as se

app = Flask(__name__)

def page(title, body):
    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;max-width:900px;margin:20px auto;padding:0 16px;line-height:1.5}}
h1,h2{{margin:0.6em 0}}
form{{border:1px solid #ddd;padding:12px;border-radius:8px;margin:12px 0}}
input,textarea,select,button{{font-size:16px;padding:8px;margin:4px 0;width:100%}}
label{{font-weight:600;margin-top:6px;display:block}}
button{{cursor:pointer}}
.card{{border:1px solid #eee;padding:12px;border-radius:8px;margin:8px 0}}
.small{{color:#666;font-size:14px}}
.topbar{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}}
.topbar a{{display:inline-block;padding:8px 12px;border:1px solid #ddd;border-radius:8px;background:#fafafa;text-decoration:none;color:#111}}
pre{{white-space:pre-wrap;background:#f6f8fa;padding:12px;border-radius:8px;overflow:auto}}
code{{font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace}}
</style>
</head>
<body>
<div class="topbar">
<a href="{url_for('home')}">Home</a>
</div>
{body}
</body>
</html>
"""

@app.route("/")
def home():
    body = f"""
<h1>Mini Search</h1>
<p class="small">Crawl a few pages, build a local index, and search it.</p>

<form method="post" action="{url_for('crawl')}">
  <h2>Crawl</h2>
  <label>Seeds (space or newline separated URLs)</label>
  <textarea name="seeds" rows="3" placeholder="https://example.com"></textarea>
  <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px">
    <div><label>Limit</label><input name="limit" type="number" value="50"></div>
    <div><label>Out folder</label><input name="out" value="data"></div>
    <div><label>User Agent</label><input name="user_agent" value="mini-search/0.2"></div>
    <div><label>Delay (seconds)</label><input name="delay" value="0.2"></div>
    <div><label>Max per host (0 = unlimited)</label><input name="max_per_host" value="0"></div>
    <div><label>Proxy (http://host:port or socks5h://host:port)</label><input name="proxy" placeholder="socks5h://127.0.0.1:9050"></div>
  </div>
  <label><input type="checkbox" name="restrict"> Restrict to same hosts as seeds</label>
  <button type="submit">Start Crawl</button>
</form>

<form method="get" action="{url_for('search')}">
  <h2>Search</h2>
  <label>Data folder</label>
  <input name="data" value="data">
  <label>Query</label>
  <input name="q" placeholder="search terms">
  <label>Top K</label>
  <input name="k" value="10">
  <button type="submit">Search</button>
</form>
"""
    return page("Mini Search", body)

@app.route("/crawl", methods=["POST"])
def crawl():
    seeds_raw = request.form.get("seeds","").strip()
    seeds = [s for s in seeds_raw.replace("\r","\n").split() if s]
    limit = int(request.form.get("limit","50"))
    out = request.form.get("out","data")
    restrict = True if request.form.get("restrict")=="on" else False
    user_agent = request.form.get("user_agent","mini-search/0.2")
    delay = float(request.form.get("delay","0.2"))
    max_per_host = int(request.form.get("max_per_host","0"))
    proxy = request.form.get("proxy") or None
    if not seeds:
        return page("Crawl", "<h1>Crawl</h1><div class='card'>No seeds provided.</div>")
    se.crawl(seeds, limit, out, restrict, user_agent, delay, max_per_host, proxy)
    with open(os.path.join(out,"docs.json"),"r",encoding="utf-8") as f:
        docs = len(json.load(f))
    body = f"<h1>Crawl complete</h1><div class='card'>Saved {docs} documents to <code>{html.escape(out)}</code>.</div><a href='{url_for('home')}'>Back</a>"
    return page("Crawl complete", body)

@app.route("/search")
def search():
    data = request.args.get("data","data")
    q = request.args.get("q","").strip()
    k = int(request.args.get("k","10"))
    if not q:
        return page("Search", "<h1>Search</h1><div class='card'>Enter a query.</div>")
    try:
        results = se.search(data, q, k)
    except Exception as e:
        return page("Search", f"<h1>Error</h1><div class='card'>{html.escape(str(e))}</div>")
    items = []
    for r in results:
        u = html.escape(r.get("url",""))
        t = html.escape(r.get("title",""))
        s = html.escape(r.get("snippet",""))
        sc = r.get("score",0.0)
        items.append(f"<div class='card'><div><a href='{u}' target='_blank'>{t or u}</a></div><div class='small'>{u}</div><div>{s}</div><div class='small'>score {sc}</div></div>")
    body = "<h1>Results</h1>" + "".join(items) + f"<a href='{url_for('home')}'>Back</a>"
    return page("Results", body)

def create_app():
    return app

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
