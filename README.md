# Mini Search

Web crawler, indexer, and search UI. It fetches pages you choose, builds a local TF IDF index, and lets you search your own data. It does not use Google or other search engines.

## 1) Quickstart (run and example)

Install on Windows inside your project virtual environment:
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

Run the UI:
.\.venv\Scripts\python .\ui.py
Open http://127.0.0.1:5000 in your browser.

Optional start the built in proxy:
.\.venv\Scripts\python .\mini_proxy.py 8081
In the UI Proxy field enter: http://127.0.0.1:8081

Example use:
Crawl with Seeds https://www.python.org/ Limit 30 Restrict ON Delay 0.5 then Start crawl
Search with Data data Query python or downloads Top K 10 then Run search

## 2) High level explanation

The project has three parts.

UI (ui.py) is a small Flask app that runs on your machine. It shows two forms.
Crawl lets you provide starting URLs and limits. The UI calls the engine to fetch pages, extract text, follow links according to your settings, and save everything under the data folder.
Search lets you provide a query. The UI asks the engine to load the saved index and return the best matches.

Engine (search_engine.py) is the core logic.
1) Crawl fetches pages directly or through a proxy respects robots.txt extracts readable text and links applies delay and per host limits and collects a small corpus.
2) Index converts text to tokens counts term frequency per document computes inverse document frequency over the corpus and builds an inverted index with document norms for cosine similarity.
3) Search converts your query to a TF IDF vector scores documents by cosine similarity and returns the top results.

Proxy (mini_proxy.py) is a minimal forward proxy for learning and local testing. For HTTP it forwards requests. For HTTPS it opens a tunnel using CONNECT. If you enter it in the UI the crawler routes its traffic through it. Keep it bound to 127.0.0.1 for local use.

## 3) Low level code reference

search_engine.py

normalize_url(u)
Accepts http https or file URLs removes fragments returns a cleaned absolute URL or None.

host(u)
Returns the host and optional port for a URL. Used for per host limits and same site checks.

same_site(u, seeds)
Returns True if u shares the host with any seed. Used when Restrict is on.

extract_text(html)
Parses HTML with BeautifulSoup removes non content tags returns (title, text, soup). text is normalized and soup is reused to discover links.

tokenize(text)
Lowercases and extracts alphanumeric tokens with a regular expression. No stemming or stop word removal.

can_fetch(u, ua, robots_cache, proxies=None)
Loads and caches robots.txt for the site using the same proxies if provided parses the rules and answers whether ua may fetch u. Always allows file URLs.

crawl(seeds, limit, out_dir, restrict, user_agent, delay, max_per_host, proxy)
Breadth first crawl. Builds a queue from normalized seeds tracks a seen set enforces Restrict robots.txt and per host caps. Fetches each page file via local read or web via requests.get with optional proxies parses to (title, text, soup) stores {url, title, text} extracts and enqueues unseen links sleeps for delay. Writes out_dir/docs.json then calls build_index(out_dir).

build_index(out_dir)
Loads docs.json. Tokenizes title + text counts term frequency TF accumulates document frequency DF computes idf[t] = log((N + 1) / (df + 0.5)) + 1 builds postings postings[t] = [[doc_id, count], ...] computes doc_norm[i] as the square root of the sum of squared TF IDF weights. Saves index.json with postings idf and doc_norm.

load_data(out_dir)
Loads and returns (docs, postings, idf, doc_norm) from docs.json and index.json.

search(out_dir, q, k)
Tokenizes the query builds a TF IDF query vector accumulates dot products over postings of the query terms divides by norms to get cosine similarity sorts and returns the top k results with {score, url, title, snippet}.

cli()
Command line entry point mirroring the crawl and search behavior.

ui.py

app = Flask(__name__)
Creates the local server.

page(title, body)
Produces the page layout head simple styles and body.

route "/" -> home()
Renders the Crawl and Search forms.

route "/crawl" (POST) -> crawl()
Reads form values calls search_engine.crawl(...) counts saved documents from docs.json and shows a completion message.

route "/search" -> search()
Reads Data Query and Top K calls search_engine.search(...) and renders the results.

create_app() and app.run(...)
Factory and entry point to run on http://127.0.0.1:5000.

mini_proxy.py

ProxyHandler.handle()
Reads the first request line and headers. For CONNECT host:port opens a TCP tunnel to host:port returns 200 Connection Established and relays bytes both ways used by HTTPS. For absolute form HTTP requests http://host[:port]/path connects to the target rewrites the request line to origin form forwards headers and relays the response.

_relay(client, upstream)
Copies data in both directions until either side closes.

ThreadedTCPServer and serve(port)
A simple multithreaded TCP server bound to 127.0.0.1:port.
