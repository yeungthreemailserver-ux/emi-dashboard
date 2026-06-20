"""Build the APAC single-country bundles: web/singapore-bundle.js and web/malaysia-bundle.js
(each window.COUNTRY). Rendered by the shared web/country.js (reuses china.css). English-only.

Singapore = a city-state → one country-level "Key clusters" dossier (no city selector).
Malaysia  = country + key-city dossiers (Penang, Kulim, Klang Valley, Johor).

Phase 2 adds the city/cluster dossiers. Macro & role figures are widely-cited official /
industry sources, each labelled with source + period. No live fetch.
"""
import json
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"

GLOSSARY = {
    "GDP growth": "Real gross domestic product growth, year-over-year.",
    "Core CPI": "Core consumer inflation (excludes accommodation & private transport) — MAS's main price gauge.",
    "CPI": "Headline consumer price inflation, year-over-year.",
    "NODX": "Non-Oil Domestic Exports — Singapore's key export gauge (locally-made goods, ex-oil); electronics is a big share.",
    "Electronics PMI": "Electronics-sector Purchasing Managers' Index (SIPMM) — >50 = the chip cluster is expanding.",
    "Unemployment": "Resident unemployment rate (seasonally adjusted).",
    "OPR": "Overnight Policy Rate — Bank Negara Malaysia's benchmark interest rate.",
    "E&E exports": "Electrical & electronics exports — Malaysia's largest export category (~40% of total), incl. semiconductors.",
    "OSAT": "Outsourced Semiconductor Assembly & Test — the chip 'back-end': packaging & testing finished wafers into usable chips.",
    "ATP": "Assembly, Test & Packaging — the semiconductor back-end (same idea as OSAT).",
    "Advanced packaging": "High-density chip packaging (2.5D/3D, chiplets) — where more performance gains now come from; Malaysia is only now building it.",
    "IC design": "Designing the chip itself (the high-value front-of-chain step) — minimal in SE-Asia, which is mostly mid-stream.",
    "Semiconductor equipment": "The tools that make chips (deposition, etch, test handlers) — Singapore is a major production base.",
    "Wafer fab": "Front-end chip fabrication (turning silicon wafers into circuits); SE-Asia runs mainly mature/specialty fabs.",
    "SiC": "Silicon carbide — a wide-bandgap power semiconductor for efficient EV/industrial power electronics.",
    "leading-edge logic": "The most advanced chips (≤7nm) for CPUs/GPUs/AI — fabricated only in Taiwan & Korea, not SE-Asia.",
    "HBM": "High-Bandwidth Memory — stacked DRAM for AI accelerators; designed/made by SK hynix, Samsung & Micron.",
    "substrate": "The package base that connects a chip die to the circuit board — a tight global bottleneck (mostly Japan/Korea/Taiwan).",
    "FIZ": "Free Industrial Zone — a duty-free manufacturing zone for export industries; Penang's Bayan Lepas FIZ is the original electronics cluster.",
    "JS-SEZ": "Johor-Singapore Special Economic Zone — a 2025 cross-border zone channelling Singapore's spillover and China+1 investment into Johor.",
    "KHTP": "Kulim Hi-Tech Park — Malaysia's flagship high-tech park (Kedah), home to power-semiconductor fabs and Infineon's SiC hub.",
}

# Industry-domain colours + per-city taxonomy — IDENTICAL keys to the China bundle so the atlas
# colours dots and renders the manufacturing-type heatmap the same way for every country.
DOMAINS = {
    "SEMI": ("Semiconductor", "#D85A30", "半导体"),
    "COMP": ("Components / Materials", "#7F77DD", "元件 / 材料"),
    "AUTO": ("Automotive / EV", "#EF9F27", "汽车 / 电动车"),
    "BAT":  ("Battery / Clean-energy", "#1D9E75", "电池 / 清洁能源"),
    "ELEC": ("Electronics / EMS", "#378ADD", "电子 / EMS"),
    "APPL": ("Appliances / Precision", "#64748b", "家电 / 精密"),
}
TAX = ["Components", "Optical", "Battery", "Automotive", "Precision", "Materials", "Appliances", "Semiconductor"]

# ---- macro tiles (view.good: high / band / low / none) ----
SG_MACRO = [
    {"key": "gdp", "k": "GDP growth", "v": "+4.8%", "as_of": "2025", "source": "MTI", "glo": "GDP growth", "basis": "YoY",
     "view": {"metric": "value", "ref": 0, "good": "high"}, "series": [["2021", 9.7], ["2022", 3.8], ["2023", 1.1], ["2024", 4.4], ["2025", 4.8]]},
    {"key": "cpi", "k": "Core CPI", "v": "+1.0%", "as_of": "2025", "source": "MAS", "glo": "Core CPI", "basis": "YoY",
     "view": {"metric": "value", "ref": 0, "good": "band", "band": [0.5, 2.5]}, "series": [["2021", 0.9], ["2022", 4.1], ["2023", 4.2], ["2024", 2.8], ["2025", 1.0]]},
    {"key": "nodx", "k": "NODX", "v": "+4.8%", "as_of": "2025", "source": "Enterprise SG", "glo": "NODX", "basis": "YoY",
     "view": {"metric": "value", "ref": 0, "good": "high"}, "series": [["2021", 12.0], ["2022", 3.0], ["2023", -13.1], ["2024", 0.2], ["2025", 4.8]]},
    {"key": "unemp", "k": "Unemployment", "v": "1.9%", "as_of": "2025", "source": "MOM", "glo": "Unemployment",
     "view": {"metric": "value", "ref": 2.5, "good": "low"}, "series": [["2021", 2.7], ["2022", 2.1], ["2023", 1.9], ["2024", 1.9], ["2025", 1.9]]},
    {"key": "epmi", "k": "Electronics PMI", "v": "50.9", "as_of": "Dec 2025", "source": "SIPMM", "glo": "Electronics PMI",
     "view": {"metric": "value", "ref": 50, "good": "high"}, "series": [["Dec 2025", 50.9]]},
]
MY_MACRO = [
    {"key": "gdp", "k": "GDP growth", "v": "+4.9%", "as_of": "2025", "source": "DOSM / IMF", "glo": "GDP growth", "basis": "YoY",
     "view": {"metric": "value", "ref": 0, "good": "high"}, "series": [["2021", 3.3], ["2022", 8.9], ["2023", 3.6], ["2024", 5.1], ["2025", 4.9]]},
    {"key": "cpi", "k": "CPI", "v": "+1.4%", "as_of": "2025", "source": "DOSM", "glo": "CPI", "basis": "YoY",
     "view": {"metric": "value", "ref": 0, "good": "band", "band": [0.5, 3.0]}, "series": [["2021", 2.5], ["2022", 3.3], ["2023", 2.5], ["2024", 1.8], ["2025", 1.4]]},
    {"key": "ee", "k": "E&E exports", "v": "RM711B", "as_of": "2025", "source": "MITI / MATRADE", "glo": "E&E exports",
     "view": {"metric": "yoy", "ref": 0, "good": "high"}, "series": [["2021", 455], ["2022", 593], ["2023", 575], ["2024", 601], ["2025", 711]]},
    {"key": "opr", "k": "OPR", "v": "2.75%", "as_of": "2025", "source": "BNM", "glo": "OPR", "note": "eased Jul 2025",
     "view": {"metric": "value", "ref": 0, "good": "none"}, "series": [["2021", 1.75], ["2022", 2.75], ["2023", 3.0], ["2024", 3.0], ["2025", 2.75]]},
]

# ---- role maps (global share per node; "hold" = strength, "gap" = mid-stream/limited; no 50% line) ----
SG_ROLE = [
    {"node": "Semiconductor equipment", "scope": "global output", "share": 20, "disp": "~20%", "type": "hold", "source": "A*STAR / industry", "year": "2024", "glo": "Semiconductor equipment"},
    {"node": "Semiconductor output", "scope": "global total", "share": 10, "disp": "~10%", "type": "hold", "source": "A*STAR", "year": "2024", "glo": "Wafer fab"},
    {"node": "Wafer fab capacity", "scope": "mature / specialty", "share": 5, "disp": "~5%", "type": "hold", "source": "A*STAR", "year": "2024", "glo": "Wafer fab"},
    {"node": "Leading-edge logic", "scope": "≤7nm · GF tops out ~12nm", "share": 0, "disp": "0%", "type": "gap", "source": "industry", "year": "2024", "glo": "leading-edge logic"},
    {"node": "Advanced memory (HBM)", "scope": "design & lead supply elsewhere", "share": 1, "disp": "~1%", "type": "gap", "source": "industry", "year": "2024", "glo": "HBM"},
]
SG_ROLE_TAKE = ("Singapore is the region's high-value front: ~20% of global semiconductor equipment output, ~10% of "
                "world chip output and ~5% of wafer-fab capacity (mature/specialty), plus the equipment that makes chips. "
                "It doesn't do leading-edge logic or advanced memory — those stay in Taiwan & Korea.")

MY_ROLE = [
    {"node": "Assembly, test & packaging", "scope": "global back-end (Penang/Kulim)", "share": 13, "disp": "~13%", "type": "hold", "source": "MSIA / MIDA", "year": "2024", "glo": "ATP"},
    {"node": "Advanced packaging", "scope": "7% target by 2035", "share": 1, "disp": "~0%", "type": "gap", "source": "MIDA / MAPC", "year": "2024", "glo": "Advanced packaging"},
    {"node": "Wafer fabrication", "scope": "SilTerra + new Kulim fabs", "share": 1, "disp": "~1%", "type": "gap", "source": "industry", "year": "2024", "glo": "Wafer fab"},
    {"node": "IC design", "scope": "front-of-chain · moving upstream", "share": 2, "disp": "~2%", "type": "gap", "source": "AMRO", "year": "2024", "glo": "IC design"},
    {"node": "Leading-edge logic", "scope": "≤7nm · none", "share": 0, "disp": "0%", "type": "gap", "source": "industry", "year": "2024", "glo": "leading-edge logic"},
]
MY_ROLE_TAKE = ("Malaysia is the world's back-end powerhouse — ~13% of global assembly, test & packaging and the 6th-largest "
                "chip exporter — and the prime 'China+1' destination. Its push now is upstream: advanced packaging (a 7%-by-2035 "
                "target), wafer fabs and IC design, where it's still minimal.")

# ---- Malaysia key-city dossiers (anchor = "Local Co" string OR {"n":"MNC","o":"US"} for foreign HQ) ----
MY_CITIES = [
    {"name": "Penang", "dom": "SEMI", "area": "George Town · Bayan Lepas FIZ", "lon": 100.30, "lat": 5.34, "tagline": "“Silicon Valley of the East” — the back-end heart: chip assembly/test/packaging, homegrown test-equipment champions and EMS.",
     "clusters": [
        {"seg": "Semiconductor assembly & test (OSAT)", "level": 3, "what": "Intel's first overseas plant (1972) seeded a dense MNC + homegrown back-end cluster.", "anchors": [{"n": "Intel", "o": "US"}, {"n": "AMD", "o": "US"}, {"n": "Broadcom", "o": "US"}, {"n": "Micron", "o": "US"}, {"n": "ASE", "o": "TW"}, "Unisem", "Carsem"]},
        {"seg": "Test equipment & automation", "level": 3, "what": "Homegrown champions in ATE, machine vision & factory automation — a genuine local IP base.", "anchors": ["Inari Amertron", "ViTrox", "Pentamaster", "Greatech", "Globetronics"]},
        {"seg": "EMS & test instruments", "level": 2, "what": "Contract manufacturing plus test & measurement.", "anchors": [{"n": "Jabil", "o": "US"}, {"n": "Flex", "o": "US"}, {"n": "Plexus", "o": "US"}, {"n": "Keysight", "o": "US"}]},
        {"seg": "Optoelectronics & medical devices", "level": 2, "what": "LED/sensor optoelectronics plus a growing MNC medtech base diversifying the cluster.", "anchors": [{"n": "ams OSRAM", "o": "AT"}, {"n": "B. Braun", "o": "DE"}, {"n": "Boston Scientific", "o": "US"}]},
     ],
     "subdistricts": [
        {"name": "Bayan Lepas FIZ", "focus": "Island free-industrial zone — Intel, AMD, Broadcom, Keysight, ams OSRAM"},
        {"name": "Batu Kawan", "focus": "Mainland park — Micron, Boston Scientific & newer MNC expansions"},
        {"name": "Seberang Perai (Prai)", "focus": "Established mainland estate — EMS & supporting industries"},
     ],
     "valuechain": "Mid-stream back-end: imports finished wafers, substrates & bonding materials → assembles, packages & tests → exports packaged devices and (uniquely) the test/inspection equipment itself.",
     "sourcing": {"buy": ["Wafers & dies", "substrates / leadframes", "bonding wire, mould compound", "test sockets & handlers"], "sell": ["Packaged & tested ICs", "RF / optoelectronic modules", "test & inspection equipment", "EMS assemblies"]},
     "tags": {"Components": 2, "Optical": 2, "Battery": 0, "Automotive": 1, "Precision": 3, "Materials": 1, "Appliances": 1, "Semiconductor": 3},
     "stats": [{"k": "Role", "v": "OSAT / back-end"}, {"k": "Anchor zone", "v": "Bayan Lepas FIZ"}, {"k": "Seeded by", "v": "Intel (1972)"}],
     "note": "Back-end (assembly/test/packaging), not front-end wafer fab — bare wafers are imported, then packaged & tested here. The genuinely local IP is the test/inspection equipment (Inari, ViTrox, Pentamaster)."},
    {"name": "Kulim", "dom": "SEMI", "area": "Kedah · Kulim Hi-Tech Park", "lon": 100.56, "lat": 5.37, "tagline": "Kulim Hi-Tech Park — power & compound semis and wafer fabs; home to Infineon's global silicon-carbide hub.",
     "clusters": [
        {"seg": "Power & compound semis (SiC)", "level": 3, "what": "Infineon's Kulim site — among the world's largest 200mm SiC power-fab investments.", "anchors": [{"n": "Infineon", "o": "DE"}, {"n": "Fuji Electric", "o": "JP"}]},
        {"seg": "Wafer fab & logic", "level": 2, "what": "One of the few Malaysian sites doing front-end fabrication.", "anchors": [{"n": "Intel", "o": "US"}, "SilTerra"]},
        {"seg": "IC substrate", "level": 2, "what": "Package-substrate capacity — a global bottleneck being built out here.", "anchors": [{"n": "AT&S", "o": "AT"}]},
        {"seg": "Solar", "level": 2, "what": "PV cell / module manufacturing.", "anchors": [{"n": "First Solar", "o": "US"}]},
     ],
     "subdistricts": [
        {"name": "Kulim Hi-Tech Park (KHTP)", "focus": "Infineon SiC power fab, Intel, First Solar, Fuji Electric"},
        {"name": "KHTP expansion", "focus": "New 200mm SiC & advanced power-device capacity build-out"},
     ],
     "valuechain": "Malaysia's main move UPSTREAM — wafer fabrication, power-device (SiC) front-end and IC substrates, beyond the Penang back-end.",
     "sourcing": {"buy": ["SiC / Si wafers", "gases & chemicals", "fab equipment", "substrate materials"], "sell": ["SiC / Si power devices", "logic wafers", "IC substrates", "PV modules"]},
     "tags": {"Components": 1, "Optical": 0, "Battery": 1, "Automotive": 1, "Precision": 1, "Materials": 2, "Appliances": 0, "Semiconductor": 3},
     "stats": [{"k": "Park", "v": "Kulim Hi-Tech Park"}, {"k": "Focus", "v": "Power / SiC / wafer fab"}, {"k": "Anchor", "v": "Infineon SiC hub"}],
     "note": "Front-end (wafer) site — rare for Malaysia, which is overwhelmingly back-end. The SiC power-device fab is the strategic differentiator vs Penang's assembly/test base."},
    {"name": "Klang Valley", "dom": "ELEC", "area": "Kuala Lumpur · Selangor · Cyberjaya", "lon": 101.69, "lat": 3.14, "tagline": "The demand & integration hub — hyperscale data centres, contract EMS and the MNC regional-HQ / distribution base.",
     "clusters": [
        {"seg": "Data centres / cloud", "level": 3, "what": "Hyperscale build-out across Selangor & Cyberjaya.", "anchors": [{"n": "Microsoft", "o": "US"}, {"n": "Google", "o": "US"}, {"n": "AWS", "o": "US"}, "Bridge Data Centres"]},
        {"seg": "EMS / box-build", "level": 2, "what": "Local contract manufacturers serving global brands.", "anchors": ["VS Industry", "SKP Resources", "ATA IMS"]},
        {"seg": "Storage & electronics", "level": 2, "what": "Data-storage & components manufacturing.", "anchors": [{"n": "Western Digital", "o": "US"}]},
     ],
     "subdistricts": [
        {"name": "Cyberjaya", "focus": "Data centres, MSC tech hub, shared-services / BPO"},
        {"name": "Selangor (Shah Alam · Sepang)", "focus": "EMS box-build, hyperscale DC parks, light electronics"},
        {"name": "Kuala Lumpur core", "focus": "MNC regional HQ, distribution & finance"},
     ],
     "valuechain": "A net CONSUMER of components — data-centre capacity, EMS box-build and regional HQ/distribution around the capital.",
     "sourcing": {"buy": ["Servers, GPUs, networking", "power & cooling gear", "components for EMS"], "sell": ["Cloud / DC capacity", "finished electronic products", "EMS box-build"]},
     "tags": {"Components": 2, "Optical": 0, "Battery": 0, "Automotive": 0, "Precision": 1, "Materials": 1, "Appliances": 1, "Semiconductor": 1},
     "stats": [{"k": "Role", "v": "Data centres + EMS + HQ"}, {"k": "Hub", "v": "Selangor / Cyberjaya"}, {"k": "Storage", "v": "Western Digital"}],
     "note": "Demand & integration, not chip making — it buys components (servers, GPUs) rather than exporting them; the value here is cloud capacity, box-build and the regional HQ/distribution base."},
    {"name": "Johor", "dom": "ELEC", "area": "Iskandar · Kulai · Johor-Singapore SEZ", "lon": 103.76, "lat": 1.49, "tagline": "The diversification frontier — SE-Asia's hottest data-centre market and a “China+1” electronics magnet, riding the Singapore spillover.",
     "clusters": [
        {"seg": "AI data centres", "level": 3, "what": "Fastest-growing DC cluster in SE-Asia, absorbing Singapore's power/land spillover.", "anchors": [{"n": "Nvidia", "o": "US"}, "YTL Power", {"n": "Microsoft", "o": "US"}, {"n": "GDS", "o": "CN"}]},
        {"seg": "Electronics & China+1", "level": 2, "what": "Relocated assembly & component investment under the Johor-Singapore SEZ.", "anchors": [{"n": "Simmtech", "o": "KR"}, "China+1 EMS"]},
     ],
     "subdistricts": [
        {"name": "Iskandar · Kulai", "focus": "Hyperscale AI data centres — Nvidia, Microsoft, GDS, YTL Power"},
        {"name": "Johor-Singapore SEZ (JS-SEZ)", "focus": "China+1 electronics & assembly relocation; Singapore spillover"},
        {"name": "Pasir Gudang · Tanjung Langsat", "focus": "Port-industrial zone — petrochem & supporting components"},
     ],
     "valuechain": "The frontier absorbing China+1 and Singapore-adjacent demand — data centres, substrates and relocated assembly.",
     "sourcing": {"buy": ["Servers / GPUs", "substrate & assembly inputs", "construction & power"], "sell": ["DC capacity", "relocated electronics output", "substrates"]},
     "tags": {"Components": 1, "Optical": 0, "Battery": 0, "Automotive": 0, "Precision": 1, "Materials": 1, "Appliances": 0, "Semiconductor": 1},
     "stats": [{"k": "Role", "v": "Data centres / China+1"}, {"k": "Zone", "v": "Iskandar / JS-SEZ"}, {"k": "DC growth", "v": "Fastest in SE-Asia"}],
     "note": "An emerging frontier, not yet a deep manufacturing base — growth is data centres plus China+1 / Singapore-spillover assembly under the 2025 JS-SEZ; depth in components is still thin."},
]

# ---- Singapore country-level "Key clusters" (one dossier, no city selector) ----
SG_CLUSTERS = [
    {"seg": "Wafer fabrication (mature / specialty)", "level": 3, "what": "A top global hub for mature & specialty-node fabs.", "anchors": [{"n": "GlobalFoundries", "o": "US"}, {"n": "UMC", "o": "TW"}, {"n": "Micron", "o": "US"}, {"n": "Soitec", "o": "FR"}, {"n": "Vanguard (VIS)", "o": "TW"}]},
    {"seg": "Semiconductor equipment", "level": 3, "what": "~20% of global chip-equipment output; a major MNC tool & sub-system base.", "anchors": [{"n": "Applied Materials", "o": "US"}, {"n": "Lam Research", "o": "US"}, {"n": "ASML", "o": "NL"}]},
    {"seg": "Memory & storage", "level": 2, "what": "NAND assembly/test plus the data-storage cluster.", "anchors": [{"n": "Micron", "o": "US"}, {"n": "Western Digital", "o": "US"}, {"n": "Seagate", "o": "US"}]},
    {"seg": "Analog / power / RF", "level": 2, "what": "MNC fabs and design centres.", "anchors": [{"n": "STMicroelectronics", "o": "EU"}, {"n": "Infineon", "o": "DE"}, {"n": "NXP", "o": "NL"}]},
]
SG_VALUECHAIN = ("High-value front-of-chain for the region — mature/specialty wafer fabs, the equipment that makes chips, "
                 "and memory/storage; an MNC magnet and regional-HQ base. Net exporter of wafers, equipment & storage.")
SG_SOURCING = {"buy": ["Silicon wafers, gases, chemicals", "fab sub-systems & parts", "photomasks"], "sell": ["Mature/specialty wafers & ICs", "semiconductor equipment & parts", "NAND / storage devices"]}
SG_SUBDISTRICTS = [
    {"name": "Tampines / Pasir Ris wafer-fab belt", "focus": "GlobalFoundries, Micron, UMC, Soitec fabs"},
    {"name": "North Coast / Woodlands", "focus": "New mega-fab expansions (UMC, GlobalFoundries Fab 7)"},
    {"name": "one-north / Fusionopolis", "focus": "A*STAR IME — R&D, IC design & advanced-packaging research"},
]
SG_TAGS = {"Components": 2, "Optical": 1, "Battery": 0, "Automotive": 0, "Precision": 3, "Materials": 2, "Appliances": 0, "Semiconductor": 3}
SG_STATS = [{"k": "Chip equipment", "v": "~20% of global output"}, {"k": "World chip output", "v": "~10%"}, {"k": "Wafer fab", "v": "~5% (mature/specialty)"}]
SG_NOTE = ("High-value front-of-chain (mature/specialty fabs + the equipment that makes chips), not back-end assembly. "
           "No leading-edge logic or advanced memory (HBM) — those stay in Taiwan & Korea.")

SINGAPORE = {
    "name": "Singapore", "code": "sg", "dom": "SEMI",
    "tagline": "Advanced fabs, semiconductor equipment & HQ hub — the high-value front of the SE-Asia chip chain.",
    "macro": SG_MACRO, "role": SG_ROLE, "role_take": SG_ROLE_TAKE,
    "clusters": SG_CLUSTERS, "subdistricts": SG_SUBDISTRICTS, "valuechain": SG_VALUECHAIN, "sourcing": SG_SOURCING,
    "tags": SG_TAGS, "stats": SG_STATS, "note": SG_NOTE,
    "domains": DOMAINS, "taxonomy": TAX, "glossary": GLOSSARY,
}
MALAYSIA = {
    "name": "Malaysia", "code": "my",
    "tagline": "Penang/Kulim back-end powerhouse — ~13% of global assembly, test & packaging; the “China+1” magnet now pushing upstream.",
    "macro": MY_MACRO, "role": MY_ROLE, "role_take": MY_ROLE_TAKE,
    "cities": MY_CITIES,
    "domains": DOMAINS, "taxonomy": TAX, "glossary": GLOSSARY,
}


# ---- Asia registry: drives the asia.html overview map (one row per country). status live|planned.
# chip = curated electronics/chip supply-chain weight (0-100). gdp = 2025 real growth %. lon/lat = map centroid.
REGISTRY = {
    "layers": [
        {"key": "chip", "name": "Chip supply-chain weight", "unit": "/100"},
        {"key": "gdp", "name": "GDP growth", "unit": "% YoY"},
    ],
    "countries": [
        {"code": "cn", "name": "China", "status": "live", "href": "china.html", "lon": 103, "lat": 36, "chip": 100, "gdp": 5.0, "headline": "Biggest market + mature-node base; owns 85-98% of the clean-energy/materials stack."},
        {"code": "tw", "name": "Taiwan", "status": "planned", "href": "", "lon": 121, "lat": 23.8, "chip": 98, "gdp": 4.0, "headline": "Leading-edge logic — TSMC, UMC, ASE, MediaTek; the chips China lacks."},
        {"code": "kr", "name": "South Korea", "status": "planned", "href": "", "lon": 127.8, "lat": 36.5, "chip": 90, "gdp": 1.8, "headline": "Memory & display — Samsung, SK hynix (DRAM/NAND/HBM)."},
        {"code": "jp", "name": "Japan", "status": "planned", "href": "", "lon": 138, "lat": 37, "chip": 80, "gdp": 1.0, "headline": "Materials, equipment & passives — Murata, Tokyo Electron, Shin-Etsu, Sony."},
        {"code": "sg", "name": "Singapore", "status": "live", "href": "singapore.html", "lon": 103.82, "lat": 1.31, "chip": 60, "gdp": 4.8, "headline": "~20% of global chip equipment + mature/specialty fabs; MNC & HQ hub."},
        {"code": "my", "name": "Malaysia", "status": "live", "href": "malaysia.html", "lon": 101.5, "lat": 3.8, "chip": 55, "gdp": 4.9, "headline": "Back-end powerhouse — ~13% of global assembly/test/packaging; China+1 magnet."},
        {"code": "vn", "name": "Vietnam", "status": "planned", "href": "", "lon": 106, "lat": 16, "chip": 45, "gdp": 6.5, "headline": "Fast-rising assembly/EMS base — Samsung, Foxconn, Amkor, Intel ATP."},
        {"code": "ph", "name": "Philippines", "status": "planned", "href": "", "lon": 122, "lat": 13, "chip": 35, "gdp": 5.7, "headline": "Long-standing assembly & test base."},
        {"code": "th", "name": "Thailand", "status": "planned", "href": "", "lon": 101, "lat": 15, "chip": 35, "gdp": 2.8, "headline": "HDD/data-storage & electronics assembly hub."},
        {"code": "in", "name": "India", "status": "planned", "href": "", "lon": 79, "lat": 22, "chip": 30, "gdp": 6.5, "headline": "Emerging — first fabs/ATP (Tata, Micron Sanand); huge end-market."},
    ],
}


def write(name, obj):
    blob = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    # dual-emit: window.COUNTRY for the standalone page (country.js); window.APAC[code] so the
    # single-page atlas can load every country bundle together without clobbering.
    js = "window.COUNTRY = " + blob + ";\n(window.APAC=window.APAC||{})['" + obj["code"] + "']=window.COUNTRY;\n"
    (WEB / f"{name}-bundle.js").write_text(js, encoding="utf-8")
    kb = len((WEB / f"{name}-bundle.js").read_text(encoding="utf-8")) // 1024
    extra = f"{len(obj.get('cities', []))} cities" if obj.get("cities") else f"{len(obj.get('clusters', []))} clusters"
    print(f"wrote web/{name}-bundle.js ({kb} KB) — {len(obj['macro'])} macro, {len(obj['role'])} role, {extra}")


def main():
    write("singapore", SINGAPORE)
    write("malaysia", MALAYSIA)
    geo_f = WEB / "vendor" / "asia.geo.json"
    if geo_f.exists():
        REGISTRY["geo"] = json.loads(geo_f.read_text(encoding="utf-8"))
    blob = json.dumps(REGISTRY, ensure_ascii=False, separators=(",", ":"))
    (WEB / "asia-registry.js").write_text("window.ASIA = " + blob + ";\n", encoding="utf-8")
    live = sum(1 for c in REGISTRY["countries"] if c["status"] == "live")
    print(f"wrote web/asia-registry.js — {len(REGISTRY['countries'])} countries ({live} live)")


if __name__ == "__main__":
    main()
