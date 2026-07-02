#!/usr/bin/env python3
"""EMI News — build stage (analysis-first; hybrid extractive→abstractive).

Mirrors the earnings system's analysis DNA (ontology + good/bad verdict + time series +
forward call + breadth + emergence) instead of dumping a feed:
  1. tag every raw article against data/ontology.json
  2. relevance-filter, then dedup into clusters
  3. score hotness; compute per-concept momentum vs data/news_history.json
  4. CONCEPTS  — entity-level volume + momentum + verdict + spark (for the treemap)
  5. RIVER     — per-concept daily volume series (for the themeriver)
  6. SYNTHESIS — Sonnet rolls the top clusters into 5-7 THEMES, each with a distributor
                 verdict (tailwind/headwind/watch), drivers, risk, affected names, evidence;
                 plus a one-paragraph weekly brief.  (extractive pre-select → abstractive synth)
                 via `claude -p --model claude-sonnet-4-6`; rule-based fallback if CLI absent.
  7. emit web/news-bundle.js (window.NEWS) + roll history (30 days).
"""
import json, os, re, sys, subprocess, math, shutil, datetime as dt
from email.utils import parsedate_to_datetime
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")
ONT = json.load(open(os.path.join(DATA, "ontology.json"), encoding="utf-8"))

SYNTH_INPUT_N = 45      # clusters fed to the synthesis LLM (extractive pre-select)
MAX_ITEMS = 1000        # evidence clusters written to the bundle (≈ whole window, so highlights and
                        # theme evidence can reference EVERY story; the feed still shows ~90)
STORE_DAYS = 30         # rolling-window length for the accumulating knowledge store
PUBLISHED_MAX_AGE_DAYS = 60   # drop items whose ARTICLE date is older than this — keeps the feed "current".
                              # Regulatory filings (Entity List, Section 232…) keep re-appearing yet carry
                              # their original publication date, so last_seen-pruning alone left 2024/2016 cruft.
CONCEPTS_N = 22         # concepts for the treemap
RIVER_N = 7             # concepts tracked in the themeriver
SOURCE_WEIGHT = {"SemiEngineering": 1.0, "EE Times": 1.0, "Federal Register": 1.0,
                 "The Register": 0.85, "SCMP Tech": 0.8, "Tom's Hardware": 0.7, "Google News": 0.65}
THEME_IMPACT = {"export_controls": 1.0, "pricing_supply": 0.95, "capacity_capex": 0.85,
                "demand_shift": 0.8, "ma_investment": 0.7, "technology": 0.65}


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        return parsedate_to_datetime(s)
    except Exception:
        pass
    if re.match(r"^\d{8}T\d{6}Z$", s):
        return dt.datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            d = dt.datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
        except Exception:
            continue
    return None


# ---------- tagging (whole-token, lookaround) -------------------------------
def _rx(term):
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower().strip()) + r"(?![a-z0-9])")

_MATCH = {}
for facet, field in [("companies", "aliases"), ("end_markets", "kw"), ("components", "kw"),
                     ("geographies", "aliases"), ("themes", "kw")]:
    _MATCH[facet] = [(o["id"], [_rx(s) for s in o[field]]) for o in ONT[facet]]

LABELS = {}
for f, pfx in [("companies", "company"), ("end_markets", "em"), ("components", "comp"),
               ("geographies", "geo"), ("themes", "theme")]:
    for o in ONT[f]:
        LABELS[pfx + ":" + o["id"]] = o.get("label") or o.get("name")


def tag(text):
    t = text.lower()
    out = {k: [] for k in _MATCH}
    for facet, entries in _MATCH.items():
        for eid, rxs in entries:
            if any(r.search(t) for r in rxs):
                out[facet].append(eid)
    return out


ROLE_OF = {c["id"]: c.get("role", "") for c in ONT["companies"]}
SUPPLY_ROLES = {"analog_power", "passives", "memory", "foundry", "equipment", "materials",
                "osat", "display", "eda_ip", "logic", "distribution"}
TRUSTED_TIERS = {"trade", "china", "official"}
KEY_THEMES = {"pricing_supply", "export_controls", "capacity_capex", "demand_shift", "ma_investment"}
# consumer / gaming / AI-model noise — irrelevant to a parts distributor unless a part signal also fires
NOISE_RX = re.compile(r"\b(gaming|game console|playstation|ps5|xbox|nintendo|geforce|gaming gpu|"
                      r"graphics card|fps|smartphone review|foldable|earbuds?|headphones?|tv review|"
                      r"chatbot|chatgpt|openai|deepseek|gemini|large language model|llm benchmark|"
                      r"crypto|bitcoin|blockchain|nft|streaming service)\b", re.I)
# SEO "market research report" mill — keyword-matching spam ("X Market Forecast to 2035", CAGR…)
REPORTMILL_RX = re.compile(r"\bcagr\b|\bspargers?\b|\bsintered metal mesh\b|"
                           r"market\b[^.]{0,45}\b20(2[7-9]|3[0-9])\b|"
                           r"\bmarket (size|share|outlook|trajectory)\b", re.I)
# investor / stock-price / fund-holding framing — trader content, NOT supply-chain intelligence
INVESTOR_RX = re.compile(
    r"\b(overvalued|undervalued|valuation|price target|moving average|top pick|buy rating|sell rating|"
    r"outperform|underperform|market cap|closed (up|down)|% ytd|year-to-date|wall ?st|stock price|"
    r"stock quote|share price|shares of|13f|investment management|asset management|capital management)\b"
    r"|\bstock \(|\b(stock|shares)\b.{0,14}\b(up|down|rose|fell|surg\w*|jump\w*|gain\w*|slump\w*|soar\w*|\d)"
    r"|\b(acquires?|boosts?|trims?|raises?|cuts?|sells?|buys?)\b[^.]{0,30}\b(shares?|stake|position|holdings?)\b"
    r"|\b(fair value|hiding in plain sight|bull case|bear case|buy the dip|price-to-earnings|p/e ratio|dividend yield)\b"
    r"|\bstock\b[^.]{0,30}\b(fair value|rally|hiding|bull|bear|upside|downside|target|undervalued|overvalued)\b", re.I)
# investor-content domains — Seeking Alpha / Trefis / simplywall.st etc. are trader sites, not supply news
INVESTOR_DOMAIN_RX = re.compile(
    r"(seekingalpha|trefis|simplywall|fool\.com|motleyfool|zacks|tipranks|benzinga|marketbeat|gurufocus|"
    r"stocktwits|barchart|insidermonkey|investorplace|24/7wallst|247wallst|nasdaq\.com/articles|stockstotrade|tradingview)", re.I)
# industry-macro signals (often have no part tag, but matter for the Macro lens) — let them through
MACRO_RX = re.compile(r"\b(book-to-bill|wsts|sia |semiconductor sales|semiconductor billings|"
                      r"semiconductor forecast|chip sales|semiconductor market|manufacturing pmi|"
                      r"ism manufacturing|semiconductor cycle|semiconductor outlook)\b", re.I)
# polarity for CONTRADICTION DETECTION — do sources disagree on supply/price direction?
POS_RX = re.compile(r"\b(shortage|tight|tighten\w*|allocation|under-?supply|sold ?out|price hike|"
                    r"price increase|prices? (?:rise|rising|jump|surge|spike)|surging|10x)\b", re.I)
NEG_RX = re.compile(r"\b(oversupply|over-?capacity|glut|price (?:cut|drop|decline|war)|"
                    r"prices? (?:fall|falling|drop)|easing|softening|soft demand|weak demand|"
                    r"inventory correction|de-?stock\w*|order cut)\b", re.I)
POS_CJK = ("涨价", "缺货", "紧缺", "短缺")
NEG_CJK = ("降价", "砍单", "过剩", "跌价", "去库存")
def polarity(text):
    p = bool(POS_RX.search(text)) or any(w in text for w in POS_CJK)
    n = bool(NEG_RX.search(text)) or any(w in text for w in NEG_CJK)
    return p, n


def relevance(tags, text, tier):
    """distributor-relevance score; strict gate keeps >= 2.0 (see is_relevant)."""
    s = 0.0
    if any(ROLE_OF.get(c) in SUPPLY_ROLES for c in tags["companies"]):
        s += 2.0                              # a component-supply-side maker / our line-card vendor
    elif tags["companies"]:
        s += 0.5                              # only a brand/OEM mention
    if tags["components"]:
        s += 2.0                              # an actual part category
    if set(tags["themes"]) & KEY_THEMES:
        s += 1.5                              # pricing/supply/policy/M&A signal
    if tags["end_markets"] and tags["components"]:
        s += 0.5                              # end-market demand tied to a part
    if tier in TRUSTED_TIERS:
        s += 2.0                              # curated component / distribution / regulator source
    if MACRO_RX.search(text):
        s += 2.0                              # industry-macro signal (book-to-bill, WSTS, chip sales…)
    if NOISE_RX.search(text):
        s -= 3.0
    if REPORTMILL_RX.search(text):
        s -= 5.0                              # SEO report-mill spam — drop it
    if INVESTOR_RX.search(text):
        s -= 4.0                              # investor/stock-price noise — keep only if a strong supply signal also fires
    return s


def is_relevant(tags, text, tier="gnews"):
    return relevance(tags, text, tier) >= 2.0


# ---- house guard: our own brands must NEVER surface in the UI -----------------
# House-name anonymisation RETIRED (2026-06-24): the user confirmed EMI contains only PUBLIC
# data (no internal/proprietary data), so house brands are shown normally — public information
# (e.g. Avnet's public earnings/8-K) is not hidden. scrub_house is kept as a no-op hook and
# HOUSE_RX is left defined so the guard can be re-enabled in one line if the policy changes.
HOUSE_RX = re.compile(r"\b(avnet|farnell|premier\s+farnell|element\s*14|element14|newark\b(?!\s+airport)|silica\s+avnet|ebv\s+elektronik)\b", re.I)
def scrub_house(s):
    return s   # retired — restore `HOUSE_RX.sub("a major distributor", s) if isinstance(s, str) and s else s` to re-enable
def scrub_bundle(b):
    """Final safety net — generalise house names across every UI-facing text field."""
    b["brief"] = scrub_house(b.get("brief", ""))
    for t in b.get("themes", []):
        for f in ("headline", "so_what", "now_what", "watch", "customer_talk", "supplier_talk"):
            if t.get(f):
                t[f] = scrub_house(t[f])
        t["drivers"] = [scrub_house(x) for x in t.get("drivers", [])]
    for a, d in (b.get("corner_insights") or {}).items():
        d["bottom_line"] = scrub_house(d.get("bottom_line", ""))
        for p in d.get("points", []):
            p["headline"] = scrub_house(p.get("headline", "")); p["so_what"] = scrub_house(p.get("so_what", ""))
    for it in b.get("items", []):
        for f in ("title", "title_en", "digest"):
            if it.get(f):
                it[f] = scrub_house(it[f])
        it["claims"] = [scrub_house(x) for x in it.get("claims", [])]
        it["subject"] = [scrub_house(x) for x in it.get("subject", [])]
    return b


# ---- angles (the distributor's 360° lenses) --------------------------------
ANGLE_LABEL = {a["id"]: a["label"] for a in ONT.get("angles", [])}
ANGLE_KW = {a["id"]: [_rx(k) for k in a.get("kw", [])] for a in ONT.get("angles", [])}
ANGLE_FROM_THEME = {"pricing_supply": ["parts", "scm"], "export_controls": ["geopolitics"],
                    "capacity_capex": ["supplier"], "technology": ["technology"],
                    "demand_shift": ["demand"], "ma_investment": ["supplier"]}


def angle_tags(tags, text):
    A = set()
    if tags["end_markets"]:
        A.add("demand")
    if any(ROLE_OF.get(c) in SUPPLY_ROLES for c in tags["companies"]):
        A.add("supplier")
    if tags["components"]:
        A.add("parts")
    for th in tags["themes"]:
        A.update(ANGLE_FROM_THEME.get(th, []))
    for aid, rxs in ANGLE_KW.items():
        if any(r.search(text) for r in rxs):
            A.add(aid)
    return sorted(A)


def tokens(s):
    """CJK-aware: Latin words (>=3 chars) + Chinese character BIGRAMS — so identical/near
    Chinese headlines (which have no spaces) cluster instead of each becoming its own item."""
    s = s.lower()
    toks = set(re.findall(r"[a-z0-9]{3,}", s))
    cjk = "".join(re.findall(r"[一-鿿]", s))
    if len(cjk) == 1:
        toks.add(cjk)
    for i in range(len(cjk) - 1):
        toks.add(cjk[i:i + 2])
    return toks


def cluster_key(title):
    """stable cross-day signature so the same storyline merges across runs (token set, CJK-aware)."""
    t = tokens(title)
    return ("|".join(sorted(t))[:240]) if t else re.sub(r"[^a-z0-9]+", "", title.lower())[:80]


def cluster(articles):
    clusters = []
    for a in articles:
        tk = tokens(a["title"])
        placed = False
        for cl in clusters:
            inter = len(tk & cl["_tok"])
            jac = inter / (len(tk | cl["_tok"]) or 1)
            if jac >= 0.55 or (inter >= 4 and inter >= 0.8 * min(len(tk), len(cl["_tok"]))):
                cl["members"].append(a); cl["_tok"] |= tk; placed = True; break
        if not placed:
            clusters.append({"rep": a, "members": [a], "_tok": tk})
    return clusters


_EMB_MODEL = None
def _embedder():
    global _EMB_MODEL
    if _EMB_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _EMB_MODEL = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _EMB_MODEL

TIER_RANK = {"trade": 0, "official": 1, "industry": 2, "china": 3, "regional": 3, "gnews": 4, "gdelt": 5}
EVENT_WINDOW_DAYS = 14   # an "event" is a burst; articles >2 weeks apart are DIFFERENT events


def _split_by_time(idxs, articles, window=EVENT_WINDOW_DAYS):
    """A semantic community can lump the same TOPIC across months (a price-hike announcement + an
    old sales report). Split it into time bursts so each cluster is one real event with a current
    date, an honest merge count, and time-coherent facts. Undated articles join the newest burst."""
    dated = sorted(((parse_date(articles[i].get("published", "")), i) for i in idxs
                    if parse_date(articles[i].get("published", ""))), key=lambda x: x[0], reverse=True)
    undated = [i for i in idxs if not parse_date(articles[i].get("published", ""))]
    if not dated:
        return [idxs]
    subs = []
    for d, i in dated:
        for s in subs:
            if abs((s["newest"] - d).days) <= window:
                s["idxs"].append(i); break
        else:
            subs.append({"newest": d, "idxs": [i]})
    subs[0]["idxs"].extend(undated)
    return [s["idxs"] for s in subs]


def _translate_titles(articles):
    """Normalise non-English headlines to English (one Sonnet call/chunk) so embedding happens in a
    single language space — the multilingual model has a language bias that otherwise lumps all
    Chinese news into one blob. Also stored as `en_title` for a readable UI. Falls back to original."""
    idx = [i for i, a in enumerate(articles) if any(ord(c) > 0x2E00 for c in a["title"])]
    out = {}
    for s in range(0, len(idx), 80):
        sub = idx[s:s + 80]
        lines = [f"{j}. {articles[i]['title'][:120]}" for j, i in enumerate(sub)]
        prompt = ("Translate each numbered news headline to concise English. Keep company, product and "
                  "part names verbatim (TSMC, MLCC, DRAM…). Return ONLY JSON "
                  '{"t":[{"i":<n>,"en":"..."}]}.\n\n' + "\n".join(lines))
        try:
            r = run_claude(prompt)
            for o in r.get("t", []):
                k = int(o.get("i", -1))
                if 0 <= k < len(sub) and o.get("en"):
                    out[sub[k]] = o["en"]
        except Exception as e:
            print(f"  translate: chunk skipped ({type(e).__name__})")
    return out


def event_cluster(articles, thr=0.72):
    """L1 — group the SAME real-world event across sources AND languages. Non-English titles are
    translated to English first (kills the multilingual model's language bias), then clustered by
    embedding cosine. Falls back to the lexical cluster() if the model/lib isn't available."""
    if len(articles) < 2:
        return cluster(articles)
    try:
        from sentence_transformers import util
        model = _embedder()
        tr = _translate_titles(articles)
        if tr:
            print(f"  translate: normalised {len(tr)} non-English titles to English")
            for i, en in tr.items():
                articles[i]["en_title"] = en
        texts = [(articles[i].get("en_title") or articles[i]["title"]) + ". " + (articles[i].get("summary", "") or "")[:160] for i in range(len(articles))]
        emb = model.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
        comm = util.community_detection(emb, threshold=thr, min_community_size=1)
        seen, clusters = set(), []
        for grp in comm:
            for i in grp:
                seen.add(i)
            for sub in _split_by_time(grp, articles):   # one real-world event per time burst
                members = sorted((articles[i] for i in sub), key=lambda m: TIER_RANK.get(m.get("tier"), 9))
                clusters.append({"rep": members[0], "members": members})
        for i in range(len(articles)):
            if i not in seen:
                clusters.append({"rep": articles[i], "members": [articles[i]]})
        print(f"  event_cluster: {len(articles)} articles -> {len(clusters)} events (semantic, thr={thr}, {EVENT_WINDOW_DAYS}d window)")
        return clusters
    except Exception as e:
        print(f"  event_cluster: embeddings unavailable ({type(e).__name__}: {str(e)[:90]}) — lexical fallback")
        return cluster(articles)


def hotness(cl, now):
    members = cl["members"]
    dates = [d for d in (parse_date(m.get("published", "")) for m in members) if d]
    if dates:
        age_h = (now - max(dates)).total_seconds() / 3600.0
        recency = max(0.0, 1.0 - age_h / 168.0)
    else:
        age_h = None            # undated — do NOT fabricate a 72h age
        recency = 0.0           # and give it no fake freshness credit
    srcs = {m["source"] for m in members}
    crosssrc = min(1.0, (len(srcs) - 1) / 3.0) if len(srcs) > 1 else (0.15 if len(members) == 1 else 0.4)
    srcw = max((SOURCE_WEIGHT.get(m["source"], 0.6) for m in members), default=0.6)
    impact = max((THEME_IMPACT.get(th, 0.5) for th in cl["tags"]["themes"]), default=0.5)
    score = round(100.0 * (0.34 * recency + 0.26 * crosssrc + 0.18 * srcw + 0.22 * impact), 1)
    return score, (round(age_h, 1) if age_h is not None else None)


def entity_keys(tags):
    keys = []
    for cid in tags["companies"]: keys.append("company:" + cid)
    for eid in tags["end_markets"]: keys.append("em:" + eid)
    for cid in tags["components"]: keys.append("comp:" + cid)
    for gid in tags["geographies"]: keys.append("geo:" + gid)
    for th in tags["themes"]: keys.append("theme:" + th)
    return keys


FACET_OF = {"company": "companies", "em": "end_markets", "comp": "components", "geo": "geographies", "theme": "themes"}
def entity_in(cl, key):
    typ, cid = key.split(":", 1)
    return cid in cl["tags"].get(FACET_OF.get(typ, ""), [])


# ---------- canonical events: cross-day store consolidation (Phase 1) ----------
def consolidate_store(ent):
    """Merge store entries that are the SAME storyline told with different wording. cluster_key()
    is a title-token signature, so re-reported events used to pile up as separate entries — this
    pass merges them semantically: cosine >= 0.80 (same local model as event_cluster) AND >=1 shared
    company/component entity AND published within EVENT_WINDOW_DAYS. The survivor is the entry first
    seen (the canonical event); it absorbs sources/tags/claims and keeps the freshest headline.
    Local + free (no LLM). Returns (consolidated_entries, n_merged)."""
    keys = list(ent.keys())
    if len(keys) < 2:
        return ent, 0
    try:
        model = _embedder()
        texts = []
        for k in keys:
            e = ent[k]
            extra = e.get("digest") or (e.get("claims") or [""])[0] or ""
            texts.append(((e.get("title_en") or e.get("title", "")) + " " + extra)[:300])
        emb = model.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
    except Exception as ex:  # model unavailable -> skip gracefully, store stays as-is
        print(f"  consolidate: skipped ({type(ex).__name__}: {str(ex)[:80]})")
        return ent, 0
    pub = []
    for k in keys:
        d = parse_date(ent[k].get("published", ""))
        pub.append(d.date() if d else None)
    ents = [{x for x in entity_keys(ent[k]["tags"]) if x.startswith(("company:", "comp:"))} for k in keys]
    # cross-language pairs (a Chinese-titled entry vs its English twin — e.g. when a day's translation
    # failed) score lower on the multilingual model, so they get a laxer threshold; the shared-entity
    # and published-window gates still guard against over-merging.
    cjk = [bool(re.search(r"[一-鿿]", t)) for t in texts]
    # RARE title tokens act as implicit entities for names the ontology doesn't know (e.g. an
    # acquisition target like "Synaptics"): a token appearing in <=2.5% of entries that two titles
    # share is a strong same-story signal the tag gate would otherwise miss.
    _STOP = set(("the a an and or of for to in on with by from as at is are its his her new says say said announces "
                 "announce announced launches launch launched unveils unveiled week today year billion million deal "
                 "chip chips semiconductor semiconductors electronics electronic market markets report reports company").split())
    toks = [{w for w in re.findall(r"[a-z0-9]{3,}", (ent[k].get("title_en") or ent[k].get("title", "")).lower())
             if w not in _STOP} for k in keys]
    df = {}
    for s in toks:
        for w in s:
            df[w] = df.get(w, 0) + 1
    rare_cut = max(5, round(0.025 * len(keys)))
    rare = [{w for w in s if df[w] <= rare_cut} for s in toks]
    parent = list(range(len(keys)))
    gsize = [1] * len(keys)                                # union-find group sizes
    MAX_GROUP = 10                                         # a true same-event chain rarely exceeds ~10
    def find(i):                                           # distinct wordings; the cap stops transitive
        while parent[i] != i:                              # chaining from snowballing a whole topic
            parent[i] = parent[parent[i]]; i = parent[i]   # (a 271-article "event" happened without it)
        return i
    sim = emb @ emb.T
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            shared = ents[i] & ents[j]
            if not shared and not (rare[i] & rare[j]):
                continue
            # >=2 shared ontology entities (e.g. acquirer + target) is the strongest signal (0.68);
            # a shared RARE title token (names the ontology doesn't know) is good but noisier (0.72);
            # otherwise plain same-language pairs need 0.80 (0.70 cross-language).
            thr = (0.68 if len(shared) >= 2 else
                   0.72 if (rare[i] & rare[j]) else
                   0.70 if (cjk[i] or cjk[j]) else 0.80)
            if sim[i, j] < thr:
                continue
            if not pub[i] or not pub[j] or abs((pub[i] - pub[j]).days) > EVENT_WINDOW_DAYS:
                continue                                   # undated or >2 weeks apart = different events
            ri, rj = find(i), find(j)
            if ri != rj and gsize[ri] + gsize[rj] <= MAX_GROUP:
                parent[rj] = ri
                gsize[ri] += gsize[rj]
    groups = {}
    for i in range(len(keys)):
        groups.setdefault(find(i), []).append(i)
    out, merged = {}, 0
    for idxs in groups.values():
        if len(idxs) == 1:
            k = keys[idxs[0]]; out[k] = ent[k]
            continue
        idxs.sort(key=lambda i: (ent[keys[i]].get("first_seen", "9999"), -ent[keys[i]].get("n_articles", 1)))
        es = [ent[keys[i]] for i in idxs]
        base = dict(es[0])                                 # canonical = earliest first_seen
        def _pd(e):
            d = parse_date(e.get("published", ""))
            return d.date() if d else dt.date.min
        fresh = max(es, key=_pd)                           # freshest metadata wins (same rule as per-key merge)
        for f in ("title", "title_en", "url", "source", "published", "summary", "digest", "etype", "metric", "subject", "object"):
            if fresh.get(f):
                base[f] = fresh[f]
        base["sources"] = sorted({s for e in es for s in (e.get("sources") or [e.get("source", "")]) if s})
        base["src_types"] = sorted({t for e in es for t in e.get("src_types", [])})
        tags = {f: set() for f in ("companies", "end_markets", "components", "geographies", "themes")}
        for e in es:
            for f in tags:
                tags[f].update((e.get("tags") or {}).get(f, []))
        base["tags"] = {f: sorted(v) for f, v in tags.items()}
        claims = []
        for e in es:
            for c in e.get("claims", []):
                if c and c not in claims:
                    claims.append(c)
        base["claims"] = claims[:8]
        base["n_articles"] = sum(e.get("n_articles", 1) for e in es)
        base["days_seen"] = max(e.get("days_seen", 1) for e in es)
        base["first_seen"] = min(e.get("first_seen", "9999") for e in es)
        base["last_seen"] = max(e.get("last_seen", "") for e in es)
        out[keys[idxs[0]]] = base
        merged += len(idxs) - 1
    return out, merged


# ---------- persistent theme registry (Phase 2) ----------
# The 6 business dimensions of the value chain — the skeleton for the (Phase-3) impact matrix.
DIMENSIONS = [
    ("products",   "Products"),
    ("technology", "Technology"),
    ("suppliers",  "Suppliers"),
    ("channel",    "Distribution & Channel"),
    ("endmarkets", "End Markets"),
    ("geopolicy",  "Geography & Policy"),
]
DIM_IDS = {d for d, _ in DIMENSIONS}
THEME_TIER_W = {"trade": 1.0, "official": 1.0, "china": 0.9, "gnews": 0.7, "gdelt": 0.6}
THEMES_PATH = os.path.join(DATA, "news_themes.json")


def _theme_strengths(reg, ent, today_key, now):
    """Local (no-LLM) scoring: strength = Σ source-tier × corroboration × recency over the theme's
    live events, normalized 0-100 vs the strongest theme. Appends today to a rolling 30-day history
    (same-day re-runs replace, so it's idempotent) and derives stage from the 3-day trajectory."""
    for th in reg["themes"].values():
        th["event_keys"] = [k for k in th.get("event_keys", []) if k in ent]
    reg["themes"] = {tid: th for tid, th in reg["themes"].items() if th["event_keys"]}
    raws = {}
    for tid, th in reg["themes"].items():
        s = 0.0
        for k in th["event_keys"]:
            e = ent[k]
            w = max((THEME_TIER_W.get(t, 0.7) for t in e.get("src_types", [])), default=0.7)
            d = parse_date(e.get("published", ""))
            try:
                age = (now.date() - d.date()).days if d else (now.date() - dt.date.fromisoformat(e.get("last_seen", today_key))).days
            except ValueError:
                age = 0
            s += w * math.log1p(len(e.get("sources", [])) or 1) * math.exp(-max(age, 0) / 10.0)
        raws[tid] = s
    mx = max(raws.values(), default=0) or 1.0
    for tid, th in reg["themes"].items():
        s = round(100.0 * raws[tid] / mx, 1)
        hist = [h for h in th.get("history", []) if h.get("d") != today_key][-29:]
        prev = hist[-1]["s"] if hist else None
        hist.append({"d": today_key, "s": s})
        th["history"], th["strength"] = hist, s
        th["delta"] = round(s - prev, 1) if prev is not None else 0.0
        base = hist[-4]["s"] if len(hist) >= 4 else (hist[0]["s"] if len(hist) > 1 else None)
        th["stage"] = ("new" if base is None else "rising" if s - base > 8 else "fading" if s - base < -8 else "steady")


def update_themes(ent, today_key, now):
    """Maintain the PERSISTENT theme registry (data/news_themes.json): named market storylines that
    accumulate evidence and strength across days — this is what turns a news pile into "where are
    the key themes". Incremental: only today's not-yet-assigned events go to ONE Sonnet call
    (skipped entirely when there's nothing new); strength/stage/history are computed locally.
    Returns the ranked board rows (with event_keys for the caller to map to item indices)."""
    reg = json.load(open(THEMES_PATH, encoding="utf-8")) if os.path.exists(THEMES_PATH) else {"themes": {}, "next_id": 1}
    assigned = {k for th in reg["themes"].values() for k in th.get("event_keys", [])}
    delta = [(k, e) for k, e in ent.items() if e.get("last_seen") == today_key and k not in assigned]
    delta.sort(key=lambda kv: len(kv[1].get("sources", [])) * 2 + kv[1].get("days_seen", 1), reverse=True)
    delta = delta[:80]                                     # cap (also bounds the one-off first-run seed)
    n_new = 0
    if delta:
        reg_lines = "\n".join(f'{tid} | {th["name"]} | {th.get("thesis", "")[:100]}'
                              for tid, th in reg["themes"].items()) or "(none yet)"
        ev_lines = []
        for i, (k, e) in enumerate(delta):
            tg = e.get("tags", {})
            ename = ",".join((tg.get("companies", []) + tg.get("components", []))[:5])
            ev_lines.append(f"[{i}] {(e.get('title_en') or e['title'])[:95]}"
                            + (f" — {e['digest'][:80]}" if e.get("digest") else "")
                            + (f" ({ename})" if ename else ""))
        prompt = (
            "You are the market-intelligence analyst for a high-service electronic-components CATALOG "
            "distributor (customers = design engineers & maintenance buyers; long-tail SKUs, small "
            "quantities, strong EMEA/APAC). You maintain the persistent THEME REGISTRY over the "
            "market-news stream.\n\n"
            f"CURRENT THEMES (id | name | thesis):\n{reg_lines}\n\n"
            "NEW EVENTS TODAY ([idx] headline — digest (entities)):\n" + "\n".join(ev_lines) + "\n\n"
            "Rules:\n"
            "- assign an event to an existing theme when it clearly advances that theme's storyline.\n"
            "- new_themes ONLY for a genuinely distinct, multi-event market storyline (never a one-off "
            "announcement); name <=6 words; thesis = 1-2 sentences: what is happening AND why it matters "
            "to the distributor.\n"
            '- dims: 1-3 of "products" (component families/pricing/supply), "technology" (tech shifts), '
            '"suppliers" (line-card vendor moves), "channel" (distribution/inventory/logistics), '
            '"endmarkets" (demand pull), "geopolicy" (policy/geopolitics).\n'
            "- update_thesis when today's events materially change a theme's storyline.\n"
            "- merge [keep, duplicate] when two themes are the same storyline.\n"
            "- routine one-offs: leave unassigned (omit).\n"
            'Return ONLY JSON: {"assign":[{"e":<idx>,"t":"<tid>"}],"new_themes":[{"name":"...","thesis":"...",'
            '"dims":["..."],"events":[<idx>]}],"update_thesis":[{"t":"<tid>","thesis":"..."}],'
            '"merge":[["<keep>","<dup>"]]}')
        try:
            out = run_claude(prompt)
            for a in out.get("assign", []):
                try:
                    i, tid = int(a.get("e")), str(a.get("t"))
                except (TypeError, ValueError):
                    continue
                if 0 <= i < len(delta) and tid in reg["themes"]:
                    ks = reg["themes"][tid]["event_keys"]
                    if delta[i][0] not in ks:
                        ks.append(delta[i][0])
            for nt in out.get("new_themes", []):
                if not nt.get("name"):
                    continue
                evs = []
                for i in nt.get("events", []):
                    try:
                        i = int(i)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= i < len(delta):
                        evs.append(delta[i][0])
                if not evs:
                    continue
                tid = f"T{reg['next_id']}"; reg["next_id"] += 1; n_new += 1
                reg["themes"][tid] = {"name": nt["name"][:60], "thesis": (nt.get("thesis") or "")[:220],
                                      "dims": [d for d in (nt.get("dims") or []) if d in DIM_IDS][:3],
                                      "event_keys": evs, "first_seen": today_key, "history": [], "stage": "new"}
            for u in out.get("update_thesis", []):
                tid = str(u.get("t"))
                if tid in reg["themes"] and u.get("thesis"):
                    reg["themes"][tid]["thesis"] = u["thesis"][:220]
            for pair in out.get("merge", []):
                if isinstance(pair, list) and len(pair) == 2:
                    keep, dup = str(pair[0]), str(pair[1])
                    if keep in reg["themes"] and dup in reg["themes"] and keep != dup:
                        dth = reg["themes"].pop(dup)
                        reg["themes"][keep]["event_keys"] = list(dict.fromkeys(
                            reg["themes"][keep]["event_keys"] + dth["event_keys"]))
        except Exception as e:  # noqa: BLE001 — LLM failure never loses the registry
            print(f"  themes: LLM skipped ({type(e).__name__}: {str(e)[:80]}) — registry kept")
    _theme_strengths(reg, ent, today_key, now)
    for th in reg["themes"].values():
        th["last_updated"] = today_key
    json.dump(reg, open(THEMES_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    board = []
    for tid, th in sorted(reg["themes"].items(), key=lambda kv: -kv[1].get("strength", 0))[:10]:
        eks = sorted(th["event_keys"], key=lambda k: -len(ent[k].get("sources", [])))
        board.append({"id": tid, "name": th["name"], "thesis": th["thesis"], "dims": th.get("dims", []),
                      "strength": th["strength"], "delta": th["delta"], "stage": th["stage"],
                      "n_events": len(th["event_keys"]), "spark": [h["s"] for h in th["history"]],
                      "first_seen": th.get("first_seen", today_key), "event_keys": eks})
    print(f"  themes: registry {len(reg['themes'])} themes ({n_new} new, {len(delta)} events considered)")
    return board


def momentum_one(cnt, prior_vals):
    avg = (sum(prior_vals) / len(prior_vals)) if prior_vals else 0.0
    delta = (cnt - avg) / (avg + 1.0)
    if not prior_vals:
        verdict = "active"
    elif avg == 0 and cnt >= 2:
        verdict = "breaking"
    elif delta > 0.4 and cnt >= 2:
        verdict = "rising"
    elif delta < -0.4:
        verdict = "cooling"
    else:
        verdict = "steady"
    return round(avg, 1), round(delta, 2), verdict


# ---------- LLM synthesis (Sonnet via Claude Code CLI) ----------------------
def _claude_bin():
    """Resolve the claude CLI to an ABSOLUTE path. The Windows Task Scheduler launches the daily
    build with a minimal PATH that often omits npm's global bin (%APPDATA%\\npm), so a bare
    'claude' isn't found and every LLM call silently fails (this is why corner_insights came up
    empty on scheduled runs while working interactively). Fall back to known install locations."""
    exe = shutil.which("claude")
    if exe:
        return exe
    for c in (os.path.expandvars(r"%APPDATA%\npm\claude.cmd"), os.path.expandvars(r"%APPDATA%\npm\claude"),
              os.path.expanduser("~/AppData/Roaming/npm/claude.cmd"),
              os.path.expanduser("~/.npm-global/bin/claude"), "/usr/local/bin/claude"):
        if os.path.exists(c):
            return c
    return "claude"


def run_claude(prompt):
    shell = (os.name == "nt")
    binp = _claude_bin()
    # strip session markers so a build launched FROM a Claude Code session doesn't make the child
    # CLI behave like a nested session (host-auth etc.) — it must auth from its own stored login
    env = {k: v for k, v in os.environ.items() if not (k.startswith("CLAUDE") or k.startswith("ANTHROPIC"))}
    cmd = (f'"{binp}" -p --model claude-sonnet-4-6 --output-format json' if shell
           else [binp, "-p", "--model", "claude-sonnet-4-6", "--output-format", "json"])
    res = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                         timeout=360, shell=shell, encoding="utf-8", env=env)
    if res.returncode != 0:
        # with --output-format json the CLI reports errors (e.g. auth 401) on STDOUT, not stderr
        err = (res.stderr or "").strip() or (res.stdout or "").strip()
        raise RuntimeError(f"CLI rc={res.returncode}: {err[:200]}")
    env = json.loads(res.stdout)
    txt = env.get("result", "") if isinstance(env, dict) else str(env)
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0) if m else txt)


EVENT_TYPES = "price-move|shortage|capacity-capex|m&a|product-launch|disruption|policy|demand-shift|partnership|results"
def decompose_events(today_clusters):
    """DECOMPOSE the top merged events into structured Signal Records — one Sonnet call.
    Returns {cluster_key: {digest,etype,subject[],object[],metric{},claims[]}} for analytics + a clean
    English digest per event. Skipped gracefully if the CLI is absent."""
    big = sorted([cl for cl in today_clusters if len(cl["members"]) >= 2], key=lambda c: len(c["members"]), reverse=True)[:20]
    if not big:
        return {}
    lines = []
    for n, cl in enumerate(big):
        heads = " || ".join((m.get("en_title") or m["title"])[:90] for m in cl["members"][:6])
        lines.append(f"{n}. {heads}")
    prompt = ("You are a component-distributor market analyst. Each numbered cluster is headlines about ONE "
              "event. Decompose each into an analyst-grade structured record:\n"
              "- digest: ONE English sentence stating the event SPECIFICALLY — who, what, how much, when "
              "(<=24 words). No vague 'companies announce' without naming them if the sources name them.\n"
              "- type: one of " + EVENT_TYPES + "\n"
              "- subject: the SPECIFIC companies the sources name (up to 4); if a headline says 'N companies' "
              "but names none, leave it and note that in a claim — do NOT invent names.\n"
              "- object: up to 2 main components/part families\n"
              '- metric: {"direction":"up|down|flat|none","magnitude":"short, e.g. +10x or +688% or \'\'"}\n'
              "- claims: up to 4 DISTINCT facts (<=18 words) that DIRECTLY support THIS event and name "
              "specifics (companies, figures, effective dates). EXCLUDE tangential market statistics, "
              "stale data from earlier months, or anything not central to the headline. A fact a "
              "distributor can act on beats a generic market-size number. Do NOT invent figures.\n"
              'Return ONLY JSON {"clusters":[{"i":<n>,"digest":"...","type":"...","subject":[],"object":[],'
              '"metric":{"direction":"","magnitude":""},"claims":[]}]}\n\n' + "\n".join(lines))
    try:
        out = run_claude(prompt)
        res = {}
        for c in out.get("clusters", []):
            if "i" not in c:
                continue
            i = int(c["i"])
            if 0 <= i < len(big):
                res[cluster_key(big[i]["rep"]["title"])] = {
                    "digest": c.get("digest", ""), "etype": c.get("type", ""),
                    "subject": c.get("subject", []) or [], "object": c.get("object", []) or [],
                    "metric": c.get("metric", {}) or {}, "claims": c.get("claims", []) or []}
        return res
    except Exception as e:
        print(f"  decompose: skipped ({type(e).__name__}: {str(e)[:80]})")
        return {}


def synthesize(top, clusters):
    """top = list of (idx, cluster). Returns {brief, themes[...]} with evidence idx validated."""
    lines = []
    for idx, cl in top:
        tg = cl["tags"]
        tagstr = ",".join((tg["companies"] + tg["components"] + tg["themes"] + tg["end_markets"])[:6])
        lines.append(f'{idx} | {cl["rep"]["title"][:120]} | {tagstr}')
    prompt = (
        "You are the lead market-intelligence analyst for an electronic-COMPONENTS DISTRIBUTOR "
        "(semis, passives, interconnect, displays, embedded). Below are this week's news clusters as "
        "`index | headline | tags`. Do ANALYSIS, not a summary — produce ranked KEY JUDGMENTS in the "
        "style of an intelligence brief (bottom-line-up-front + so-what + now-what + indicators).\n\n"
        "For each judgment:\n"
        "- direction = the distributor read: tailwind (good for us — rising component demand, pricing "
        "power, design-in) / headwind (bad — soft demand or prices, shrinking addressable market, "
        "un-sourceable shock) / watch (mixed or uncertain).\n"
        "- confidence = high / moderate / low, CONGRUENT with how much corroborating evidence exists "
        "(a single source = low).\n"
        "- so_what = the IMPLICATION for the distributor (demand, supply, pricing, sourcing, which "
        "customers/segments are affected) — diagnostic, not descriptive.\n"
        "- action = the recommended NEXT STEP, concrete (e.g. pre-book memory allocation, raise safety "
        "stock on MLCC, pass through price, qualify a second source, brief automotive customers).\n"
        "- watch = 1-2 leading INDICATORS that would confirm or break the judgment.\n"
        "- customer_track = one sentence you'd SAY TO A CUSTOMER to show you understand their market.\n"
        "- supplier_track = one sentence you'd TELL A SUPPLIER — your demand-sensing point of view.\n"
        "- angles = 1-3 lens ids from: demand, supplier, parts, scm, macro, technology, channel, geopolitics.\n"
        "Rank by importance to a distributor. Be honest about divergence and uncertainty.\n\n"
        "Return ONLY this JSON (no prose, no fences):\n"
        '{"bottom_line":"1-2 sentence BLUF — the single most important thing for a distributor this week",'
        '"judgments":[{"headline":"the judgment as a claim, <=11 words","direction":"tailwind|headwind|watch",'
        '"confidence":"high|moderate|low","so_what":"the implication for a distributor",'
        '"action":"the recommended next step","watch":"1-2 leading indicators",'
        '"customer_track":"what to say to a customer","supplier_track":"what to tell a supplier",'
        '"angles":["lens ids"],"why":["diagnostic driver phrase",...up to 3],"risk":"the main risk to this judgment",'
        '"affected":{"companies":["..."],"end_markets":["..."]},"evidence":[<cluster indices>]}]}\n'
        "Give 5 to 7 judgments.\n\nClusters:\n" + "\n".join(lines)
    )
    out = run_claude(prompt)
    nmax = len(clusters)
    themes = []
    for t in out.get("judgments", out.get("themes", [])):
        ev = [int(i) for i in t.get("evidence", []) if isinstance(i, (int, float)) and 0 <= int(i) < nmax]
        if not ev:
            continue
        t["evidence"] = ev
        t["angles"] = [a for a in (t.get("angles") or []) if a in ANGLE_LABEL]
        themes.append(t)
    return {"brief": out.get("bottom_line", out.get("brief", "")), "themes": themes}


def fallback_themes(concepts, by_entity):
    """rule-based themes if the LLM is unavailable — top theme/component concepts become minimal themes."""
    out = []
    for c in concepts:
        if c["type"] not in ("theme", "comp", "company"):
            continue
        out.append({"headline": c["label"], "direction": "watch", "confidence": "low",
                    "so_what": "", "action": "", "watch": "", "customer_track": "", "supplier_track": "",
                    "angles": [], "why": [], "risk": "",
                    "affected": {"companies": [], "end_markets": []},
                    "evidence": (by_entity.get(c["key"], []) or [])[:6]})
        if len(out) >= 6:
            break
    return {"brief": "", "themes": out}


# ---------- topic tree: the framework as a hierarchy -------------------------
# Demand (end-markets) · Supply (the value chain, layered L1→L4+channel) · Forces
# (themes) · Geography (regions). Leaves carry a coverage key (pfx:id) so the page
# reuses the existing drill-to-stories wiring. Labels/counts come from `coverage`.
TAXONOMY_SPEC = [
    ("demand", "Demand", "who buys", [
        ("End-markets", "the systems our parts go into",
         ["em:auto", "em:compute", "em:mobile", "em:comms", "em:industrial", "em:energy", "em:medical", "em:aero", "em:semi"])]),
    ("supply", "Supply", "what we sell · the value chain", [
        ("Front-end & enablers", "fabs · tools · materials · IP",
         ["comp:foundry", "comp:equipment", "comp:materials", "comp:eda_ip"]),
        ("Devices & packaging", "the components on our line-card",
         ["comp:analog_power", "comp:logic", "comp:memory", "comp:passives", "comp:display", "comp:osat"]),
        ("Assembly & channel", "who builds the box · how it reaches the board",
         ["comp:ems_odm", "comp:distribution"])]),
    ("forces", "Forces", "what moves the market", [
        ("Themes", "the forces on price, supply & roadmap",
         ["theme:pricing_supply", "theme:capacity_capex", "theme:demand_shift", "theme:technology", "theme:ma_investment", "theme:export_controls"])]),
    ("place", "Geography", "where it happens", [
        ("Greater China", "", ["geo:cn", "geo:tw"]),
        ("North Asia", "", ["geo:kr", "geo:jp"]),
        ("SE Asia · China+1", "", ["geo:sg", "geo:my", "geo:vn", "geo:th", "geo:ph"]),
        ("South Asia & Oceania", "", ["geo:in", "geo:au", "geo:nz"]),
        ("West", "", ["geo:us", "geo:eu"])]),
]
def build_taxonomy(coverage):
    cnt, lbl = {}, {}
    for grp, pfx in (("end_markets", "em"), ("components", "comp"), ("themes", "theme"), ("geographies", "geo")):
        for x in coverage.get(grp, []):
            cnt[pfx + ":" + x["id"]] = x["count"]
            lbl[pfx + ":" + x["id"]] = x["label"]
    tree = []
    for bid, blabel, bkick, groups in TAXONOMY_SPEC:
        gout = []
        for glabel, gkick, covs in groups:
            leaves = [{"cov": c, "label": lbl.get(c, c.split(":")[1]), "count": cnt.get(c, 0)} for c in covs]
            gout.append({"label": glabel, "kicker": gkick, "count": sum(l["count"] for l in leaves), "leaves": leaves})
        tree.append({"id": bid, "label": blabel, "kicker": bkick, "count": sum(g["count"] for g in gout), "groups": gout})
    return tree


# ---------- AGGREGATE: structured Signal Records -> queryable analytics -------
# Turn the per-event Signal Records (etype, metric, subject/object, tags) into trends
# that feed the framework — event-type mix, price/supply pressure by component, capacity
# & capex by region, M&A count — plus a daily roll-up persisted to history (time series).
EVENT_TYPE_LABEL = {
    "price-move": "Price moves", "shortage": "Shortage / supply", "capacity-capex": "Capacity & capex",
    "m&a": "M&A & investment", "product-launch": "Product launches", "disruption": "Disruptions",
    "policy": "Policy & controls", "demand-shift": "Demand shifts", "partnership": "Partnerships", "results": "Results",
}
_DIR_UP = {"up", "rise", "rising", "increase", "increased", "higher", "surge", "+", "▲"}
_DIR_DN = {"down", "fall", "falling", "decrease", "decreased", "lower", "drop", "-", "▼"}
def _metric_sign(metric):
    d = ((metric or {}).get("direction") or "").strip().lower()
    return 1 if d in _DIR_UP else (-1 if d in _DIR_DN else 0)
def build_signals(clusters, hist, today_key):
    recs = [c for c in clusters if c.get("etype")]
    comp_label = {c["id"]: c["label"] for c in ONT["components"]}
    geo_label = {g["id"]: g["label"] for g in ONT["geographies"]}
    # 1) event-type mix (up/down split + examples for the tooltip)
    bt = {}
    for c in recs:
        t = c["etype"]
        if t not in EVENT_TYPE_LABEL:
            continue
        d = bt.setdefault(t, {"etype": t, "label": EVENT_TYPE_LABEL[t], "count": 0, "up": 0, "down": 0, "ex": []})
        d["count"] += 1
        s = _metric_sign(c.get("metric"))
        d["up"] += s > 0; d["down"] += s < 0
        if len(d["ex"]) < 3:
            d["ex"].append((c["rep"].get("title_en") or c["rep"]["title"])[:90])
    by_type = sorted(bt.values(), key=lambda x: -x["count"])
    # 2) price & supply pressure by component (price-move + shortage; a shortage = upward pressure)
    pr = {}
    for c in recs:
        if c["etype"] not in ("price-move", "shortage"):
            continue
        s = _metric_sign(c.get("metric")) or (1 if c["etype"] == "shortage" else 0)
        for cid in c["tags"].get("components", []):
            d = pr.setdefault(cid, {"id": cid, "cov": "comp:" + cid, "label": comp_label.get(cid, cid), "up": 0, "down": 0, "n": 0})
            d["n"] += 1; d["up"] += s > 0; d["down"] += s < 0
    for d in pr.values():
        d["net"] = d["up"] - d["down"]
    price = sorted(pr.values(), key=lambda x: (-x["n"], -x["net"]))
    # 3) capacity & capex by region
    cx = {}
    for c in recs:
        if c["etype"] != "capacity-capex" and "theme:capacity_capex" not in entity_keys(c["tags"]):
            continue
        for gid in c["tags"].get("geographies", []):
            cx[gid] = cx.get(gid, 0) + 1
    capex_by_region = sorted(({"id": g, "cov": "geo:" + g, "label": geo_label.get(g, g), "count": n} for g, n in cx.items()),
                             key=lambda x: -x["count"])
    # 4) M&A / investment count
    ma_count = sum(1 for c in recs if c["etype"] == "m&a" or "theme:ma_investment" in entity_keys(c["tags"]))
    # daily roll-up -> time series (each day's aggregate, rolling 30d)
    sig_today = {"price_net": {d["id"]: d["net"] for d in price}, "etype": {t["etype"]: t["count"] for t in by_type},
                 "capex_total": sum(cx.values()), "ma": ma_count}
    sdays = hist.setdefault("signal_days", {})
    sdays[today_key] = sig_today
    hist["signal_days"] = dict(sorted(sdays.items())[-STORE_DAYS:])
    day_keys = sorted(hist["signal_days"].keys())
    for d in price[:8]:
        d["series"] = [hist["signal_days"].get(dk, {}).get("price_net", {}).get(d["id"], 0) for dk in day_keys]
    return {"as_of": today_key, "days": day_keys, "n_records": len(recs), "by_type": by_type,
            "price": price[:8], "capex_by_region": capex_by_region, "ma_count": ma_count,
            "capex_series": [hist["signal_days"].get(dk, {}).get("capex_total", 0) for dk in day_keys],
            "ma_series": [hist["signal_days"].get(dk, {}).get("ma", 0) for dk in day_keys]}


# ---------- COMBINE PER AREA: one synthesis per corner, not a global pool sliced ---------
# The fix for "every corner looks the same": instead of synthesising ONE global set of
# judgments and filtering them by angle, we bucket the atoms BY framework area (corner) and
# combine each bucket on its own lens — so Products, Suppliers and Competitors say different
# things even about the same event. One Sonnet call sees all desks together so it can keep
# them DISTINCT (and not repeat a point across desks).
CORNER_DEFS = [
    ("parts", "Products", "the PART itself — price, availability, lead time, spec, new part families. NOT a vendor's corporate news."),
    ("supplier", "Suppliers", "what our LINE-CARD vendors (TI, ADI, Infineon, ST, NXP, Microchip, Nexperia, Renesas, onsemi, Murata, TDK, Vishay...) are DOING — capacity, capex, M&A, launches, allocation policy."),
    ("demand", "End-industries", "what END-CUSTOMERS (auto, datacentre, mobile, industrial, energy, medical...) are buying or cutting — design-ins, build rates, order cuts."),
    ("channel", "Competitors", "other DISTRIBUTORS' moves (Arrow, Mouser, DigiKey, WT, Future, TTI, Rutronik, Heilind...) — line-card wins, marketplaces, pricing."),
    ("scm", "Supply chain", "lead times, inventory/book-to-bill, logistics, allocation, second-sourcing, EOL/obsolescence, nearshoring."),
    ("geopolitics", "Geopolitics", "export controls, tariffs, sanctions, localisation, compliance (RoHS/REACH/PFAS)."),
    ("technology", "Technology", "roadmaps, new nodes, SiC/GaN, advanced packaging, next-gen interfaces, design-in cycles."),
    ("macro", "Macro", "the cycle — chip billings, book-to-bill, rates, FX, PMI, recovery/downturn."),
]
def synthesize_corners(items):
    """The PRIMARY per-desk unit: SYNTHESISE analytical insights from each desk's decomposed stories
    (not single articles), each carrying the evidence item-indices it draws from (so the card opens
    its supporting stories). Runs over `items` so evidence ids == item indices. One Sonnet call."""
    buckets = {a: [] for a, _, _ in CORNER_DEFS}
    for idx, it in enumerate(items):
        title = it.get("title_en") or it["title"]
        if INVESTOR_RX.search(title) or (it.get("age_h") or 0) > 720:
            continue                                # investor noise / >30d stale never seeds an insight
        for a in angle_tags(it["tags"], title + " " + (it.get("digest", "") or "")):
            if a in buckets:
                buckets[a].append((idx, it))
    for a in buckets:
        buckets[a] = sorted(buckets[a], key=lambda p: p[1].get("hot", 0), reverse=True)[:8]
    blocks = []
    for a, label, desc in CORNER_DEFS:
        if not buckets[a]:
            continue
        lines = [f"  [{idx}] {(it.get('title_en') or it['title'])[:95]}" + (f" — {it['digest']}" if it.get("digest") else "")
                 for idx, it in buckets[a]]
        blocks.append(f"=== desk a=\"{a}\" ({label}) — lens: {desc} ===\n" + "\n".join(lines))
    if not blocks:
        return {}
    prompt = ("You are the analyst for a global electronic-components DISTRIBUTOR. Each desk below lists its "
              "stories as `[id] headline — digest`; use the desk's a=\"…\" value VERBATIM as the JSON \"a\". "
              "For EACH desk, SYNTHESISE 2-4 analytical INSIGHTS from "
              "ITS stories — COMBINE related stories into one judgement; do NOT just restate a single headline. "
              "Each insight:\n"
              "- headline: the analytical judgement in <=13 words (a conclusion, not a copied headline)\n"
              "- so_what: 1-2 sentences — what it means for the distributor AND the concrete action, through "
              "THIS desk's lens\n"
              "- direction: tailwind (good for a distributor) | headwind (bad) | watch (uncertain)\n"
              "- evidence: the [id]s the insight draws from (1-4 ids)\n"
              "Each desk's insights must be DISTINCT from the other desks (same event → different implication "
              "per lens). Plus a desk bottom_line (<=20 words).\n"
              "NEVER name Avnet/Farnell/element14/Newark — say 'a major distributor'.\n"
              'Return ONLY JSON {"desks":[{"a":"<id>","bottom_line":"...","points":[{"headline":"...",'
              '"so_what":"...","direction":"...","evidence":[<id>...]}]}]}\n\n' + "\n\n".join(blocks))
    try:
        out = run_claude(prompt)
        n = len(items)
        id_by_label = {label.lower(): aid for aid, label, _ in CORNER_DEFS}
        res = {}
        for d in out.get("desks", []):
            a = d.get("a", "")
            a = a if a in buckets else id_by_label.get(str(a).lower(), a)   # tolerate label-as-id
            if a not in buckets or not d.get("points"):
                continue
            pts = []
            for p in d["points"][:4]:
                if not p.get("headline"):
                    continue
                ev = []
                for x in (p.get("evidence") or []):
                    try:
                        xi = int(x)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= xi < n and xi not in ev:
                        ev.append(xi)
                pts.append({"headline": p["headline"], "so_what": p.get("so_what", ""),
                            "direction": p["direction"] if p.get("direction") in ("tailwind", "headwind", "watch") else "watch",
                            "evidence": ev[:5]})
            if pts:
                res[a] = {"bottom_line": d.get("bottom_line", ""), "points": pts, "n": len(buckets[a])}
        return res
    except Exception as e:
        print(f"  corners: skipped ({type(e).__name__}: {str(e)[:90]})")
        return {}


# ---------- main -------------------------------------------------------------
def main():
    raw = json.load(open(os.path.join(DATA, "news_raw.json"), encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc)
    today_key = now.date().isoformat()

    arts = []
    for a in raw["articles"]:
        if not a.get("title") or not a.get("url"):
            continue
        if INVESTOR_DOMAIN_RX.search(a.get("url", "")):
            continue                              # investor-blog domain — never supply intelligence
        text = a["title"] + " " + a.get("summary", "")
        tags = tag(text)
        if not is_relevant(tags, text, a.get("tier", "gnews")):
            continue
        a["tags"] = tags
        arts.append(a)
    print(f"Relevant: {len(arts)}/{len(raw['articles'])} (strict distributor focus)")

    today_clusters = event_cluster(arts)
    for cl in today_clusters:
        merged = {k: set() for k in ("companies", "end_markets", "components", "geographies", "themes")}
        for m in cl["members"]:
            for k in merged:
                merged[k].update(m["tags"][k])
        cl["tags"] = {k: sorted(v) for k, v in merged.items()}
    print(f"Today clusters: {len(today_clusters)}")

    signal_map = decompose_events(today_clusters)
    if signal_map:
        print(f"  decompose: structured signal records for {len(signal_map)} merged events")

    # ---- accumulating store: merge today into a rolling 30-day window so the result is DYNAMIC ----
    sp = os.path.join(DATA, "news_store.json")
    store = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
    ent = store.get("entries", {})
    for cl in today_clusters:
        rep = cl["rep"]; k = cluster_key(rep["title"])
        if not k:
            continue
        srcs = sorted({m["source"] for m in cl["members"]})
        stypes = sorted({m.get("src_type", "") for m in cl["members"] if m.get("src_type")})
        e = ent.get(k)
        if e:
            if e.get("last_seen") != today_key:
                e["days_seen"] = e.get("days_seen", 1) + 1
            e["last_seen"] = today_key
            e["sources"] = sorted(set(e.get("sources", [])) | set(srcs))
            e["src_types"] = sorted(set(e.get("src_types", [])) | set(stypes))
            e["tags"] = cl["tags"]; e["n_articles"] = len(cl["members"])
            e["title_en"] = rep.get("en_title") or rep["title"]
            if signal_map.get(k):
                e.update(signal_map[k])
            nd, od = parse_date(rep.get("published", "")), parse_date(e.get("published", ""))
            if nd and (not od or nd > od):
                e.update({"title": rep["title"], "url": rep["url"], "source": rep["source"], "published": rep["published"]})
        else:
            sig = signal_map.get(k, {})
            ent[k] = {"title": rep["title"], "title_en": rep.get("en_title") or rep["title"],
                      "url": rep["url"], "source": rep["source"],
                      "published": rep.get("published", ""), "summary": rep.get("summary", ""),
                      "tags": cl["tags"], "sources": srcs, "src_types": stypes, "n_articles": len(cl["members"]),
                      "digest": sig.get("digest", ""), "etype": sig.get("etype", ""), "subject": sig.get("subject", []),
                      "object": sig.get("object", []), "metric": sig.get("metric", {}), "claims": sig.get("claims", []),
                      "first_seen": today_key, "last_seen": today_key, "days_seen": 1}
    cutoff = (now.date() - dt.timedelta(days=STORE_DAYS)).isoformat()
    # prune by age AND purge accumulated investor/report-mill spam (older entries may pre-date the
    # source filter, so the rolling window stays clean, not just new ingestion)
    def _spam(e):
        t = (e.get("title_en") or e.get("title", ""))
        return bool(INVESTOR_RX.search(t) or REPORTMILL_RX.search(t))
    pub_cutoff = now.date() - dt.timedelta(days=PUBLISHED_MAX_AGE_DAYS)
    def _stale(e):                                          # article published too long ago (e.g. an old re-listed rule)
        pd = parse_date(e.get("published", ""))
        return pd is not None and pd.date() < pub_cutoff
    ent = {k: e for k, e in ent.items() if e.get("last_seen", "") >= cutoff and not _spam(e) and not _stale(e)}

    # CANONICAL EVENTS — merge same-storyline entries across days/wording (semantic, local, free)
    n_before = len(ent)
    ent, n_merged = consolidate_store(ent)
    print(f"  consolidate: {n_before} entries -> {len(ent)} canonical events (merged {n_merged})")

    # working set = the rolling window — this is what we synthesise, score and show
    clusters = []
    for k, e in ent.items():
        srcs = e.get("sources") or [e["source"]]
        cl = {"key": k,
              "rep": {"title": e["title"], "title_en": e.get("title_en") or e["title"], "url": e["url"], "source": e["source"],
                      "published": e.get("published", ""), "summary": e.get("summary", "")},
              "tags": e["tags"], "members": [{"source": s, "published": e.get("published", "")} for s in srcs],
              "src_types": e.get("src_types", []), "claims": e.get("claims", []), "n_articles": e.get("n_articles", len(srcs)),
              "digest": e.get("digest", ""), "etype": e.get("etype", ""), "subject": e.get("subject", []),
              "object": e.get("object", []), "metric": e.get("metric", {}),
              "first_seen": e.get("first_seen", today_key), "last_seen": e.get("last_seen", today_key),
              "days_seen": e.get("days_seen", 1)}
        cl["hot"], cl["age_h"] = hotness(cl, now)
        clusters.append(cl)
    clusters.sort(key=lambda c: c["hot"], reverse=True)
    print(f"Window clusters: {len(clusters)} (rolling {STORE_DAYS}d store, was {len(today_clusters)} today)")

    # history (prior days, before today)
    hist = {}
    hp = os.path.join(DATA, "news_history.json")
    if os.path.exists(hp):
        hist = json.load(open(hp, encoding="utf-8"))
    prior_days = [d for k, d in sorted(hist.get("days", {}).items()) if k < today_key][-7:]

    # per-entity counts over the current window
    today_counts = {}
    for cl in clusters:
        for key in set(entity_keys(cl["tags"])):
            today_counts[key] = today_counts.get(key, 0) + 1

    # items (evidence) — index aligns with clusters order
    items = []
    for cl in clusters[:MAX_ITEMS]:
        rep = cl["rep"]
        dd = parse_date(rep.get("published", ""))
        srcs = sorted({m["source"] for m in cl["members"]})
        ls = cl.get("last_seen", today_key)
        try:
            ls_age = (now.date() - dt.date.fromisoformat(ls)).days
        except ValueError:
            ls_age = 0
        status = ("new" if cl.get("first_seen") == today_key else
                  "developing" if ls == today_key else
                  "persisting" if ls_age <= 3 else "fading")
        items.append({"title": rep["title"], "url": rep["url"], "source": rep["source"],
                      "published": rep.get("published", ""), "date": dd.date().isoformat() if dd else "",
                      "age_h": cl["age_h"], "hot": cl["hot"],
                      "n": len(cl["members"]), "sources": srcs, "src_n": len(srcs), "status": status,
                      "tags": cl["tags"], "src_types": cl.get("src_types", []),
                      "title_en": rep.get("title_en") or rep["title"], "digest": cl.get("digest", ""),
                      "etype": cl.get("etype", ""), "metric": cl.get("metric", {}),
                      "subject": cl.get("subject", []), "object": cl.get("object", []),
                      "claims": cl.get("claims", []), "merged": cl.get("n_articles", 1),
                      "first_seen": cl.get("first_seen", today_key), "days_seen": cl.get("days_seen", 1),
                      "angles": angle_tags(cl["tags"], rep["title"] + " " + rep.get("summary", ""))})
    by_entity = {}
    for i, it in enumerate(items):
        for key in set(entity_keys(it["tags"])):
            by_entity.setdefault(key, []).append(i)
    by_angle = {}
    for i, it in enumerate(items):
        for a in it["angles"]:
            by_angle.setdefault(a, []).append(i)
    angles_list = sorted(({"id": a, "label": ANGLE_LABEL.get(a, a), "count": len(v)} for a, v in by_angle.items()),
                         key=lambda x: x["count"], reverse=True)

    # coverage map — counted over ALL deduped clusters (not just the top-140 shown) so the
    # completeness check is true; EVERY area incl. zero-count gaps is listed.
    full_ent, full_ang = {}, {}
    for cl in clusters:
        txt = cl["rep"]["title"] + " " + cl["rep"].get("summary", "")
        for k in set(entity_keys(cl["tags"])):
            full_ent[k] = full_ent.get(k, 0) + 1
        for a in set(angle_tags(cl["tags"], txt)):
            full_ang[a] = full_ang.get(a, 0) + 1
    def _cov(pfx, members):
        return sorted(({"id": m["id"], "label": m.get("label") or m.get("name"),
                        "count": full_ent.get(pfx + ":" + m["id"], 0)} for m in members),
                      key=lambda x: x["count"], reverse=True)
    st = {}
    for a in arts:
        k = a.get("src_type", "other") or "other"
        st[k] = st.get(k, 0) + 1
    coverage = {
        "angles": sorted(({"id": a["id"], "label": a["label"], "count": full_ang.get(a["id"], 0)} for a in ONT.get("angles", [])),
                         key=lambda x: x["count"], reverse=True),
        "end_markets": _cov("em", ONT["end_markets"]),
        "geographies": _cov("geo", ONT["geographies"]),
        "components": _cov("comp", ONT["components"]),
        "themes": _cov("theme", ONT["themes"]),
        "companies": [x for x in _cov("company", ONT["companies"]) if x["count"] > 0],
        "sources": sorted(({"id": k, "label": k[:1].upper() + k[1:], "count": v} for k, v in st.items()), key=lambda x: x["count"], reverse=True),
    }

    # CONCEPTS (treemap) — exclude geo (places are the atlas's job); rank by volume x momentum x type
    concepts = []
    for key, cnt in today_counts.items():
        typ = key.split(":")[0]
        if typ == "geo" or cnt < 2:
            continue
        avg, delta, verdict = momentum_one(cnt, [d.get(key, 0) for d in prior_days])
        impact = THEME_IMPACT.get(key.split(":")[1], 0.6) if typ == "theme" else 0.6
        typew = {"company": 1.3, "theme": 1.15, "comp": 1.1, "em": 0.75}.get(typ, 1.0)
        rscore = cnt * (1 + impact) * typew * {"breaking": 1.6, "rising": 1.3, "active": 1.0, "steady": 1.0, "cooling": 0.6}[verdict]
        spark = [d.get(key, 0) for d in prior_days] + [cnt]
        concepts.append({"key": key, "type": typ, "label": LABELS.get(key, key), "count": cnt,
                         "prev": avg, "delta": delta, "verdict": verdict,
                         "is_new": (verdict == "breaking"), "spark": spark, "_r": rscore})
    concepts.sort(key=lambda c: c["_r"], reverse=True)
    concepts = concepts[:CONCEPTS_N]
    for c in concepts:
        c.pop("_r", None)

    # RIVER (themeriver) — daily volume for the top RIVER_N concepts across history+today
    river_keys = [c["key"] for c in concepts[:RIVER_N]]
    day_keys = [k for k in sorted(hist.get("days", {}).keys()) if k < today_key] + [today_key]
    day_map = dict(hist.get("days", {})); day_map[today_key] = today_counts
    river = {"days": day_keys,
             "series": [{"key": k, "label": LABELS.get(k, k),
                         "values": [day_map.get(d, {}).get(k, 0) for d in day_keys]} for k in river_keys]}

    # SYNTHESIS (themes + brief)
    top = list(enumerate(clusters[:SYNTH_INPUT_N]))
    try:
        synth = synthesize(top, clusters[:MAX_ITEMS])
        print(f"  Synthesis: {len(synth['themes'])} themes + brief via Sonnet")
    except Exception as e:
        synth = fallback_themes(concepts, by_entity)
        print(f"  Synthesis: LLM unavailable ({type(e).__name__}: {str(e)[:110]}) — rule-based fallback")

    # attach evidence items + a volume spark to each theme
    for t in synth["themes"]:
        ev = t.get("evidence", [])
        t["items"] = ev
        t["volume"] = len(ev)
        ekeys = set()
        for i in ev:
            if i < len(items):
                for kk in entity_keys(items[i]["tags"]):
                    if not kk.startswith("geo:"):
                        ekeys.add(kk)
        t["spark"] = [sum(day_map.get(d, {}).get(k, 0) for k in ekeys) for d in day_keys] if ekeys else []
        # corroboration = independent backing for this judgment. Source TYPES (trade/aggregator/
        # regional/industry/official) are the real independence signal — distinct source NAMES
        # under-count because "Google News" collapses many outlets into one label.
        srcset, typeset = set(), set()
        for i in ev:
            if i < len(items):
                srcset.update(items[i]["sources"])
                typeset.update(items[i].get("src_types", []))
        t["corrob"] = len(srcset)
        t["corrob_types"] = len(typeset)
        t["thin"] = (t.get("confidence") == "high" and len(typeset) <= 1 and len(srcset) <= 1)

    # concept sentiment = distributor read, inherited from the themes a concept appears in
    # (so the treemap can colour by good/bad on day 1, before momentum history exists)
    sent = {}
    for t in synth["themes"]:
        d = t["direction"] if t.get("direction") in ("tailwind", "headwind", "watch") else "watch"
        ekeys = set()
        for i in t.get("items", []):
            if i < len(items):
                for k in entity_keys(items[i]["tags"]):
                    if not k.startswith("geo:"):
                        ekeys.add(k)
        for k in ekeys:
            s = sent.setdefault(k, {"tailwind": 0, "headwind": 0, "watch": 0})
            s[d] += t.get("volume", 1)
    for c in concepts:
        sc = sent.get(c["key"])
        c["sentiment"] = max(sc, key=sc.get) if sc else "neutral"

    # CONTRADICTION DETECTION — concepts where the window's sources disagree on supply/price direction
    conflicts = []
    for c in concepts:
        pos = neg = 0
        for cl in clusters:
            if entity_in(cl, c["key"]):
                p, n = polarity(cl["rep"]["title"] + " " + cl["rep"].get("summary", ""))
                pos += p; neg += n
        if pos >= 2 and neg >= 2 and min(pos, neg) >= 0.3 * max(pos, neg):
            conflicts.append({"key": c["key"], "label": c["label"], "type": c["type"], "pos": pos, "neg": neg})
    conflicts.sort(key=lambda x: -(x["pos"] + x["neg"]))

    # AGGREGATE — structured signal records -> queryable analytics (+ daily roll-up to history)
    signals = build_signals(clusters, hist, today_key)
    print(f"  signals: {signals['n_records']} records -> {len(signals['by_type'])} types, "
          f"{len(signals['price'])} price-pressure components, M&A {signals['ma_count']}")

    # COMBINE PER AREA — the PRIMARY per-desk unit: analytical insights synthesised from each desk's
    # decomposed stories, with evidence item-indices (not single-article tiles)
    corner_insights = synthesize_corners(items)
    if corner_insights:
        print(f"  corners: synthesised insights for {len(corner_insights)} desks ({', '.join(corner_insights)})")

    # PERSISTENT THEMES — named storylines with strength/lifecycle; map their events to item indices
    theme_board = update_themes(ent, today_key, now)
    key2idx = {cl.get("key"): i for i, cl in enumerate(clusters[:MAX_ITEMS]) if cl.get("key")}
    for t in theme_board:
        t["evidence"] = [key2idx[k] for k in t.pop("event_keys") if k in key2idx][:4]

    bundle = {
        "as_of": raw.get("fetched", now.isoformat(timespec="seconds")),
        "generated": now.isoformat(timespec="seconds"),
        "counts": {"raw": len(raw["articles"]), "relevant": len(arts), "clusters": len(clusters)},
        "brief": synth["brief"], "themes": synth["themes"],
        "concepts": concepts, "river": river, "angles": angles_list, "coverage": coverage,
        "taxonomy": build_taxonomy(coverage), "signals": signals,
        "corner_insights": corner_insights, "conflicts": conflicts, "theme_board": theme_board,
        "items": items, "byEntity": by_entity, "byAngle": by_angle, "labels": LABELS,
    }
    scrub_bundle(bundle)  # house-name safety net before anything is written to the page
    out_path = os.path.join(WEB, "news-bundle.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("window.NEWS = " + json.dumps(bundle, ensure_ascii=False) + ";\n")
    print(f"Wrote {len(synth['themes'])} themes, {len(concepts)} concepts, {len(items)} evidence -> {out_path}")

    hist.setdefault("days", {})[today_key] = today_counts
    hist["days"] = dict(sorted(hist["days"].items())[-30:])
    json.dump(hist, open(hp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"History: {len(hist['days'])} day(s) tracked")

    store["entries"] = ent
    store["updated"] = today_key
    json.dump(store, open(sp, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"Store: {len(ent)} clusters in rolling {STORE_DAYS}d window")
    return 0


if __name__ == "__main__":
    sys.exit(main())
