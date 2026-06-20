#!/usr/bin/env python3
"""EMI News — fetch stage. REGISTRY-DRIVEN: the source framework lives in data/sources.json
(feeds / query_packs / apis), so adding or retuning a source is a data edit, not a code change.

Each article is stamped with source metadata — tier (1 curated … 3 broad), type (trade /
aggregator / regional / official), region, area — so the build can audit SOURCE coverage
(by type/tier/region), not just topic coverage. Stdlib only; every source wrapped in try/except.
"""
import json, os, sys, ssl, urllib.request, urllib.parse, datetime as dt
import xml.etree.ElementTree as ET
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")
REG = json.load(open(os.path.join(DATA, "sources.json"), encoding="utf-8"))

UA = "Mozilla/5.0 (EMI-news/1.0; research)"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read()


def _text(el):
    return (el.text or "").strip() if el is not None else ""


def parse_feed(xml_bytes):
    """tolerant RSS + Atom → [{title,url,published,summary}]"""
    out = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return out
    items = root.findall(".//item")
    if items:
        for it in items:
            t, l = _text(it.find("title")), _text(it.find("link"))
            if t and l:
                out.append({"title": t, "url": l, "published": _text(it.find("pubDate")), "summary": _text(it.find("description"))})
        return out
    ns = "{http://www.w3.org/2005/Atom}"
    for e in root.findall(f".//{ns}entry"):
        t = _text(e.find(f"{ns}title"))
        le = e.find(f"{ns}link"); l = le.get("href") if le is not None else ""
        if t and l:
            out.append({"title": t, "url": l, "published": _text(e.find(f"{ns}updated")) or _text(e.find(f"{ns}published")),
                        "summary": _text(e.find(f"{ns}summary")) or _text(e.find(f"{ns}content"))})
    return out


def stamp(arts, src, source_name):
    """attach source-registry metadata to each article"""
    for a in arts:
        a["source"] = source_name
        a["tier"] = "trade" if src.get("type") == "trade" else ("china" if src.get("region") == "cn" else
                    ("official" if src.get("type") == "official" else ("gdelt" if src.get("method") == "gdelt" else "gnews")))
        a["src_type"] = src.get("type", "")
        a["src_tier"] = src.get("tier", 2)
        a["src_region"] = src.get("region", "global")
        a["src_area"] = (src.get("areas") or ["all"])[0]
    return arts


def fetch_gnews(q, lang):
    if lang == "zh":
        url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=zh-CN&gl=CN&ceid=CN:zh"
    else:
        url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=en-US&gl=US&ceid=US:en"
    return parse_feed(http_get(url))[:12]


def main():
    A = []
    print("Fetching from source registry (data/sources.json)...")
    for f in REG.get("feeds", []):
        try:
            arts = stamp(parse_feed(http_get(f["url"])), f, f["name"]); A.extend(arts); print(f"  feed  {f['name']}: {len(arts)}")
        except Exception as e:
            print(f"  feed  {f['name']}: FAIL ({type(e).__name__})")
    for pk in REG.get("query_packs", []):
        n = 0
        for i, q in enumerate(pk.get("q", [])):
            try:
                arts = stamp(fetch_gnews(q, pk.get("lang", "en")), pk, "Google News")
                for a in arts:
                    a["query"] = q
                A.extend(arts); n += len(arts)
            except Exception:
                pass
        print(f"  pack  {pk['id']} ({pk.get('region')}): {n}")
    for api in REG.get("apis", []):
        if api.get("method") == "gdelt":
            for q in api.get("q", []):
                try:
                    url = ("https://api.gdeltproject.org/api/v2/doc/doc?query=" + urllib.parse.quote(q) +
                           "&mode=ArtList&maxrecords=30&timespan=2d&format=json&sort=DateDesc")
                    data = json.loads(http_get(url).decode("utf-8", "replace"))
                    arts = [{"title": a.get("title", ""), "url": a.get("url", ""), "published": a.get("seendate", ""),
                             "summary": "", "source": a.get("domain", "GDELT")} for a in data.get("articles", [])]
                    stamp(arts, api, None)
                    for a in arts:
                        if not a["source"]:
                            a["source"] = "GDELT"
                    A.extend(arts)
                except Exception:
                    pass
            print(f"  api   gdelt: done")
        elif api.get("method") == "fedreg":
            try:
                url = ("https://www.federalregister.gov/api/v1/documents.json?per_page=20&order=newest"
                       "&conditions[term]=" + urllib.parse.quote(api["q"][0])
                       + "&conditions[agencies][]=industry-and-security-bureau")
                data = json.loads(http_get(url).decode("utf-8", "replace"))
                arts = [{"title": d.get("title", ""), "url": d.get("html_url", ""), "published": d.get("publication_date", ""),
                         "summary": d.get("abstract", "") or ""} for d in data.get("results", [])]
                stamp(arts, api, "Federal Register")
                A.extend(arts); print(f"  api   fedreg: {len(arts)}")
            except Exception as e:
                print(f"  api   fedreg: FAIL ({type(e).__name__})")

    out = {"fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "count": len(A), "articles": A}
    json.dump(out, open(os.path.join(DATA, "news_raw.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # source-mix audit
    import collections
    bt = collections.Counter(a.get("src_type", "?") for a in A)
    print(f"\nWrote {len(A)} raw articles · source mix: {dict(bt)}")
    return 0 if A else 1


if __name__ == "__main__":
    sys.exit(main())
