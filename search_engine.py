import os, re, json, math, time, argparse, collections, urllib.parse, urllib.robotparser
from bs4 import BeautifulSoup
import requests

def normalize_url(u):
    try:
        p=urllib.parse.urlsplit(u)
        if p.scheme not in ("http","https","file"): return None
        p=p._replace(fragment="")
        return urllib.parse.urlunsplit(p)
    except: return None

def host(u):
    try:
        return urllib.parse.urlsplit(u).netloc
    except: return ""

def same_site(u, seeds):
    try:
        uh=host(u)
        for s in seeds:
            if host(s)==uh: return True
        return False
    except: return False

def extract_text(html):
    soup=BeautifulSoup(html,"html.parser")
    for x in soup(["script","style","noscript","header","footer","svg","img","nav"]): x.decompose()
    title=soup.title.string.strip() if soup.title and soup.title.string else ""
    text=soup.get_text(separator=" ")
    text=re.sub(r"\s+"," ",text).strip()
    return title,text,soup

def tokenize(text):
    return re.findall(r"[A-Za-z0-9]+",text.lower())

def can_fetch(u, ua, robots_cache, proxies=None):
    s = urllib.parse.urlsplit(u)
    if s.scheme == "file": return True
    base = f"{s.scheme}://{s.netloc}"
    if base not in robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", timeout=5, headers={"User-Agent": ua}, proxies=proxies or {})
            rp.parse(r.text.splitlines())
        except Exception:
            rp = None
        robots_cache[base] = rp
    rp = robots_cache[base]
    if not rp: return True
    try:
        return rp.can_fetch(ua, u)
    except:
        return True


def crawl(seeds,limit,out_dir,restrict,user_agent,delay,max_per_host,proxy):
    os.makedirs(out_dir,exist_ok=True)
    q=collections.deque()
    seen=set()
    per_host=collections.Counter()
    robots_cache={}
    for s in seeds:
        n=normalize_url(s)
        if n and n not in seen:
            seen.add(n); q.append(n)
    docs=[]
    proxies={"http":proxy,"https":proxy} if proxy else None
    while q and len(docs)<limit:
        u=q.popleft()
        if restrict and not same_site(u,seeds): continue
        if not can_fetch(u,user_agent,robots_cache): continue
        h=host(u)
        if max_per_host and per_host[h]>=max_per_host: continue
        try:
            s=urllib.parse.urlsplit(u)
            if s.scheme=="file":
                with open(urllib.parse.unquote(s.path),"r",encoding="utf-8",errors="ignore") as f:
                    html=f.read()
            else:
                r=requests.get(u,timeout=10,headers={"User-Agent":user_agent},proxies=proxies,allow_redirects=True)
                if "text/html" not in r.headers.get("Content-Type",""): continue
                html=r.text
            title,text,soup=extract_text(html)
            if not text: continue
            docs.append({"url":u,"title":title,"text":text[:200000]})
            per_host[h]+=1
            for a in soup.find_all("a",href=True):
                v=normalize_url(urllib.parse.urljoin(u,a["href"]))
                if not v or v in seen: continue
                seen.add(v); q.append(v)
            time.sleep(max(0.0,delay))
        except:
            pass
    with open(os.path.join(out_dir,"docs.json"),"w",encoding="utf-8") as f:
        json.dump(docs,f,ensure_ascii=False)
    build_index(out_dir)

def build_index(out_dir):
    with open(os.path.join(out_dir,"docs.json"),"r",encoding="utf-8") as f:
        docs=json.load(f)
    dfs={}
    tfs_per_doc=[]
    for d in docs:
        terms=tokenize(d["title"]+" "+d["text"])
        tf=collections.Counter(terms)
        tfs_per_doc.append(tf)
        for term in tf.keys():
            dfs[term]=dfs.get(term,0)+1
    N=len(docs)
    idf={t:math.log((N+1)/(df+0.5))+1 for t,df in dfs.items()}
    postings={t:{} for t in dfs.keys()}
    for i,tf in enumerate(tfs_per_doc):
        for t,c in tf.items():
            postings[t][i]=c
    doc_norm=[0.0]*N
    for i,tf in enumerate(tfs_per_doc):
        s=0.0
        for t,c in tf.items():
            w=(1+math.log(c))*idf[t] if c>0 else 0.0
            s+=w*w
        doc_norm[i]=math.sqrt(s) if s>0 else 1.0
    postings_list={t:[[int(i),int(c)] for i,c in d.items()] for t,d in postings.items()}
    with open(os.path.join(out_dir,"index.json"),"w",encoding="utf-8") as f:
        json.dump({"postings":postings_list,"idf":idf,"doc_norm":doc_norm},f)

def load_data(out_dir):
    with open(os.path.join(out_dir,"docs.json"),"r",encoding="utf-8") as f:
        docs=json.load(f)
    with open(os.path.join(out_dir,"index.json"),"r",encoding="utf-8") as f:
        idx=json.load(f)
    return docs,idx["postings"],idx["idf"],idx["doc_norm"]

def search(out_dir,q,k):
    docs,postings,idf,doc_norm=load_data(out_dir)
    q_terms=tokenize(q)
    q_tf=collections.Counter(q_terms)
    q_vec={t:(1+math.log(c))*idf.get(t,0.0) for t,c in q_tf.items() if t in idf}
    q_norm=math.sqrt(sum(w*w for w in q_vec.values())) or 1.0
    scores={}
    for t,wq in q_vec.items():
        for doc_id,c in postings[t]:
            wd=(1+math.log(c))*idf[t]
            scores[doc_id]=scores.get(doc_id,0.0)+wq*wd
    results=[]
    for i,s in scores.items():
        sc=s/(q_norm*doc_norm[i]) if doc_norm[i]>0 else 0.0
        results.append((sc,i))
    results.sort(reverse=True)
    out=[]
    for sc,i in results[:k]:
        d=docs[i]
        out.append({"score":round(sc,4),"url":d["url"],"title":d["title"],"snippet":d["text"][:240]})
    return out

def cli():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="cmd")
    ap_crawl=sub.add_parser("crawl")
    ap_crawl.add_argument("--seeds",nargs="+",required=True)
    ap_crawl.add_argument("--limit",type=int,default=50)
    ap_crawl.add_argument("--out",required=True)
    ap_crawl.add_argument("--restrict",action="store_true")
    ap_crawl.add_argument("--user_agent",default="mini-search/0.2")
    ap_crawl.add_argument("--delay",type=float,default=0.2)
    ap_crawl.add_argument("--max_per_host",type=int,default=0)
    ap_crawl.add_argument("--proxy",default=None)
    ap_search=sub.add_parser("search")
    ap_search.add_argument("--data",required=True)
    ap_search.add_argument("--q",required=True)
    ap_search.add_argument("--k",type=int,default=10)
    args=ap.parse_args()
    if args.cmd=="crawl":
        crawl(args.seeds,args.limit,args.out,args.restrict,args.user_agent,args.delay,args.max_per_host,args.proxy)
    elif args.cmd=="search":
        print(json.dumps(search(args.data,args.q,args.k),ensure_ascii=False,indent=2))

if __name__=="__main__":
    cli()
