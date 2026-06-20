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

# ============================ TAIWAN ============================
TW_MACRO = [
    {"key": "gdp", "k": "GDP growth", "v": "+7.7%", "as_of": "2025", "source": "DGBAS", "glo": "GDP growth", "basis": "YoY",
     "view": {"metric": "value", "ref": 0, "good": "high"}, "series": [["2021", 6.6], ["2022", 2.6], ["2023", 1.1], ["2024", 4.6], ["2025", 7.7]]},
    {"key": "cpi", "k": "CPI", "v": "+2.0%", "as_of": "2025", "source": "DGBAS", "glo": "CPI", "basis": "YoY",
     "view": {"metric": "value", "ref": 0, "good": "band", "band": [0.5, 2.5]}, "series": [["2021", 2.0], ["2022", 2.9], ["2023", 2.5], ["2024", 2.2], ["2025", 2.0]]},
    {"key": "semi", "k": "Semiconductor output", "v": "NT$6.5T", "as_of": "2025", "source": "TSIA / MOEA",
     "view": {"metric": "yoy", "ref": 0, "good": "high"}, "series": [["2021", 4.1], ["2022", 4.8], ["2023", 4.3], ["2024", 5.3], ["2025", 6.5]]},
    {"key": "foundry", "k": "Global foundry share", "v": "~60%", "as_of": "2025", "source": "TrendForce", "note": "TSMC ~64% of foundry alone",
     "view": {"metric": "value", "ref": 0, "good": "none"}, "series": []},
]
TW_ROLE = [
    {"node": "Leading-edge logic ≤7nm", "scope": "TSMC", "share": 90, "disp": "~90%", "type": "hold", "source": "industry", "year": "2025", "glo": "leading-edge logic"},
    {"node": "Foundry (all nodes)", "scope": "global revenue", "share": 60, "disp": "~60%", "type": "hold", "source": "TrendForce", "year": "2025"},
    {"node": "Assembly, test & packaging", "scope": "ASE — world #1 OSAT", "share": 50, "disp": "~50%", "type": "hold", "source": "industry", "year": "2025", "glo": "OSAT"},
    {"node": "Fabless IC design", "scope": "MediaTek #4 global", "share": 25, "disp": "strong", "type": "hold", "source": "industry", "year": "2025", "glo": "IC design"},
    {"node": "Memory", "scope": "niche (Nanya, Winbond)", "share": 3, "disp": "~3%", "type": "gap", "source": "industry", "year": "2025", "glo": "HBM"},
    {"node": "Equipment & materials", "scope": "imported (US / JP / NL)", "share": 8, "disp": "imports", "type": "gap", "source": "industry", "year": "2025"},
]
TW_ROLE_TAKE = ("Taiwan owns the leading edge — TSMC makes >90% of the world's most advanced logic and Taiwan ~60% of all "
                "foundry — plus the #1 OSAT (ASE) and a top-tier fabless base (MediaTek). Its gaps are memory and the "
                "equipment & materials it must import.")
TW_CITIES = [
    {"name": "Hsinchu", "dom": "SEMI", "area": "Hsinchu Science Park (竹科)", "lon": 120.97, "lat": 24.81,
     "tagline": "Taiwan's Silicon Valley — the densest chip cluster on earth: TSMC & UMC HQ, MediaTek, Realtek and the original Science Park.",
     "clusters": [
        {"seg": "Pure-play foundry", "level": 3, "what": "TSMC & UMC headquarters and fabs — the model the world copies.", "anchors": ["TSMC", "UMC", "Vanguard (VIS)", "PSMC"]},
        {"seg": "Fabless IC design", "level": 3, "what": "MediaTek (world #4 fabless) anchors a deep design ecosystem.", "anchors": ["MediaTek", "Realtek", "Novatek", "Himax"]},
        {"seg": "Equipment & materials", "level": 2, "what": "Local sub-system makers plus the global MNCs that serve the Park.", "anchors": ["GUC", {"n": "Applied Materials", "o": "US"}, {"n": "ASML", "o": "NL"}, {"n": "Merck", "o": "DE"}]},
        {"seg": "Display & optoelectronics", "level": 2, "what": "Panel & driver-IC base.", "anchors": ["AUO", "Innolux"]},
     ],
     "subdistricts": [{"name": "Hsinchu Science Park (竹科)", "focus": "TSMC, UMC, MediaTek, Realtek"}, {"name": "Zhubei / Tongluo", "focus": "design houses, fab expansion"}],
     "valuechain": "The front-of-chain brain — chip design + leading foundry; imports tools & materials, exports wafers and IP to the world.",
     "sourcing": {"buy": ["Lithography & process tools", "photoresist, wafers, gases", "IP cores & EDA"], "sell": ["Foundry wafers (all nodes)", "fabless chips (MediaTek)", "driver ICs & panels"]},
     "tags": {"Components": 2, "Optical": 2, "Battery": 0, "Automotive": 1, "Precision": 2, "Materials": 2, "Appliances": 0, "Semiconductor": 3},
     "stats": [{"k": "TSMC", "v": "world #1 foundry"}, {"k": "MediaTek", "v": "#4 fabless globally"}, {"k": "Zone", "v": "Hsinchu Science Park"}],
     "note": "Foundry + fabless apex; the equipment & materials are largely imported (US / JP / NL) — Taiwan's main dependency."},
    {"name": "Tainan", "dom": "SEMI", "area": "Southern Taiwan Science Park (南科)", "lon": 120.20, "lat": 23.10,
     "tagline": "The leading-edge frontier — TSMC's Fab 18 gigafab makes the world's 3nm & 2nm chips; ASE's giant back-end sits next door in Kaohsiung.",
     "clusters": [
        {"seg": "Leading-edge logic", "level": 3, "what": "TSMC Fab 18 — 3nm in volume, 2nm ramping; the most advanced chips on Earth.", "anchors": ["TSMC"]},
        {"seg": "Assembly, test & packaging", "level": 3, "what": "ASE (Kaohsiung) — the world's largest OSAT, incl. advanced/panel-level packaging.", "anchors": ["ASE", "SPIL"]},
        {"seg": "Optoelectronics & compound", "level": 2, "what": "LED / compound-semi and panel supply.", "anchors": ["Episil", "AUO"]},
     ],
     "subdistricts": [{"name": "Southern Taiwan Science Park (南科)", "focus": "TSMC Fab 18 — 3nm / 2nm gigafab"}, {"name": "Kaohsiung", "focus": "ASE advanced packaging, materials"}],
     "valuechain": "Where the world's most advanced logic is fabricated and packaged — the tip of the spear, then straight to OSAT.",
     "sourcing": {"buy": ["EUV tools & advanced materials", "substrates & bonding materials", "ultra-pure gases & chemicals"], "sell": ["3nm / 2nm logic wafers", "advanced-packaged AI chips", "test & assembly services"]},
     "tags": {"Components": 1, "Optical": 2, "Battery": 0, "Automotive": 0, "Precision": 2, "Materials": 1, "Appliances": 0, "Semiconductor": 3},
     "stats": [{"k": "TSMC Fab 18", "v": "3nm / 2nm"}, {"k": "ASE", "v": "world #1 OSAT"}, {"k": "Zone", "v": "Southern TW Science Park"}],
     "note": "The single most strategically important square-mile of the chip world — and the core of the 'silicon shield'."},
    {"name": "Taichung", "dom": "SEMI", "area": "Central Taiwan Science Park (中科)", "lon": 120.67, "lat": 24.15,
     "tagline": "TSMC's advanced central cluster — Fab 15 plus a new 2nm gigafab — wrapped in Taiwan's precision-machinery heartland.",
     "clusters": [
        {"seg": "Advanced foundry", "level": 3, "what": "TSMC Fab 15 (7/5nm) + new 2nm Fab 25 build-out.", "anchors": ["TSMC"]},
        {"seg": "Precision machinery & automation", "level": 2, "what": "Machine tools & robotics feeding fab construction & equipment.", "anchors": ["Hiwin", "Tongtai"]},
        {"seg": "PCB & components", "level": 2, "what": "Boards & passive supply.", "anchors": ["Unimicron", "Chin-Poon"]},
     ],
     "subdistricts": [{"name": "Central Taiwan Science Park (中科)", "focus": "TSMC Fab 15, 2nm Fab 25"}, {"name": "Taichung machinery belt", "focus": "machine tools, automation"}],
     "valuechain": "Advanced fabrication plus the precision-machinery base that builds and tools the fabs.",
     "sourcing": {"buy": ["Fab tools & sub-systems", "wafers, gases, chemicals", "automation & robotics"], "sell": ["Advanced logic wafers", "machine tools & automation", "PCBs"]},
     "tags": {"Components": 2, "Optical": 1, "Battery": 0, "Automotive": 1, "Precision": 3, "Materials": 1, "Appliances": 0, "Semiconductor": 3},
     "stats": [{"k": "TSMC", "v": "Fab 15 + 2nm Fab 25"}, {"k": "Hiwin", "v": "global linear-motion"}, {"k": "Zone", "v": "Central TW Science Park"}],
     "note": "Pairs advanced foundry with the world-class precision-machinery cluster that supports it."},
    {"name": "Taipei", "dom": "ELEC", "area": "Taipei · New Taipei", "lon": 121.50, "lat": 25.05,
     "tagline": "The brand & ODM capital — Hon Hai (Foxconn), Pegatron, Quanta, ASUS, Acer HQs: the world's notebook & AI-server makers.",
     "clusters": [
        {"seg": "ODM / EMS", "level": 3, "what": "The companies that build most of the world's PCs, servers and Apple hardware.", "anchors": ["Hon Hai (Foxconn)", "Pegatron", "Wistron", "Quanta", "Compal"]},
        {"seg": "Brands", "level": 2, "what": "Global PC & device brands.", "anchors": ["ASUS", "Acer"]},
        {"seg": "AI servers & networking", "level": 2, "what": "The AI-server ODM boom (GPU racks for hyperscalers).", "anchors": ["Wiwynn", "Gigabyte", "Accton"]},
     ],
     "subdistricts": [{"name": "Tucheng / New Taipei", "focus": "Hon Hai HQ, EMS"}, {"name": "Neihu / Beitou", "focus": "ODM & brand HQs"}],
     "valuechain": "Integration & brand apex — buys chips, panels and components, ships finished electronics and AI servers worldwide.",
     "sourcing": {"buy": ["Chips, GPUs, memory, panels", "passives, connectors, power", "enclosures & thermals"], "sell": ["Notebooks & PCs", "AI / cloud servers", "networking & finished devices"]},
     "tags": {"Components": 2, "Optical": 1, "Battery": 0, "Automotive": 0, "Precision": 1, "Materials": 0, "Appliances": 1, "Semiconductor": 1},
     "stats": [{"k": "Hon Hai", "v": "world #1 EMS"}, {"k": "Servers", "v": "AI-server ODM hub"}, {"k": "Brands", "v": "ASUS, Acer"}],
     "note": "Demand & integration side — a major net consumer of components for PCs, servers and devices."},
]
TAIWAN = {
    "name": "Taiwan", "code": "tw", "dom": "SEMI",
    "tagline": "The leading edge — TSMC makes >90% of the world's most advanced logic; ~60% of all foundry, #1 OSAT (ASE) and top fabless (MediaTek).",
    "macro": TW_MACRO, "role": TW_ROLE, "role_take": TW_ROLE_TAKE, "cities": TW_CITIES,
    "domains": DOMAINS, "taxonomy": TAX, "glossary": GLOSSARY,
}

# ============================ SOUTH KOREA ============================
KR_MACRO = [
    {"key": "gdp", "k": "GDP growth", "v": "+1.9%", "as_of": "2025", "source": "Bank of Korea", "glo": "GDP growth", "basis": "YoY",
     "view": {"metric": "value", "ref": 0, "good": "high"}, "series": [["2021", 4.3], ["2022", 2.6], ["2023", 1.4], ["2024", 2.0], ["2025", 1.9]]},
    {"key": "cpi", "k": "CPI", "v": "+2.0%", "as_of": "2025", "source": "Statistics Korea", "glo": "CPI", "basis": "YoY",
     "view": {"metric": "value", "ref": 0, "good": "band", "band": [0.5, 2.5]}, "series": [["2021", 2.5], ["2022", 5.1], ["2023", 3.6], ["2024", 2.3], ["2025", 2.0]]},
    {"key": "semi", "k": "Semiconductor exports", "v": "US$173B", "as_of": "2025", "source": "MOTIE / KITA", "note": "record high; ~20% of all exports",
     "view": {"metric": "yoy", "ref": 0, "good": "high"}, "series": [["2021", 128], ["2022", 129], ["2023", 99], ["2024", 141], ["2025", 173]]},
    {"key": "bok", "k": "BOK base rate", "v": "2.75%", "as_of": "2025", "source": "Bank of Korea", "note": "easing cycle",
     "view": {"metric": "value", "ref": 0, "good": "none"}, "series": [["2021", 1.0], ["2022", 3.25], ["2023", 3.5], ["2024", 3.0], ["2025", 2.75]]},
]
KR_ROLE = [
    {"node": "Memory (DRAM / NAND)", "scope": "Samsung + SK hynix", "share": 60, "disp": "~60%", "type": "hold", "source": "TrendForce", "year": "2025", "glo": "HBM"},
    {"node": "HBM (AI memory)", "scope": "SK hynix-led", "share": 60, "disp": "~60%", "type": "hold", "source": "TrendForce", "year": "2025", "glo": "HBM"},
    {"node": "OLED displays", "scope": "Samsung Display, LGD", "share": 70, "disp": "~70%", "type": "hold", "source": "industry", "year": "2025"},
    {"node": "EV batteries", "scope": "LG ES, SK on, Samsung SDI", "share": 30, "disp": "top-3", "type": "hold", "source": "SNE Research", "year": "2025"},
    {"node": "Leading-edge foundry", "scope": "Samsung — distant #2 to TSMC", "share": 10, "disp": "~10%", "type": "gap", "source": "TrendForce", "year": "2025", "glo": "leading-edge logic"},
    {"node": "Equipment & materials", "scope": "imported (US / JP / NL)", "share": 10, "disp": "imports", "type": "gap", "source": "industry", "year": "2025"},
]
KR_ROLE_TAKE = ("Korea owns memory — Samsung & SK hynix make ~60% of the world's DRAM and the bulk of the HBM that feeds "
                "AI accelerators — plus OLED displays and a top-3 EV-battery industry. Its gaps are foundry (a distant #2 "
                "to TSMC) and imported equipment & materials.")
KR_CITIES = [
    {"name": "Gyeonggi (Capital area)", "dom": "SEMI", "area": "Pyeongtaek · Hwaseong · Yongin · Icheon", "lon": 127.10, "lat": 37.30,
     "tagline": "The world's memory heartland — Samsung (Pyeongtaek/Hwaseong) + SK hynix (Icheon) + the new Yongin 'Semiconductor Mega-Cluster'.",
     "clusters": [
        {"seg": "Memory (DRAM / NAND / HBM)", "level": 3, "what": "Samsung & SK hynix make most of the world's memory and HBM here.", "anchors": ["Samsung", "SK hynix"]},
        {"seg": "Foundry", "level": 2, "what": "Samsung Foundry — 3nm GAA; the only credible non-Taiwan leading-edge foundry.", "anchors": ["Samsung Foundry"]},
        {"seg": "Displays", "level": 3, "what": "Samsung Display & LG Display — the OLED world leaders.", "anchors": ["Samsung Display", "LG Display"]},
        {"seg": "Equipment & materials", "level": 2, "what": "Local tool/material makers plus global MNCs.", "anchors": ["SEMES", {"n": "Applied Materials", "o": "US"}, {"n": "ASML", "o": "NL"}]},
     ],
     "subdistricts": [{"name": "Pyeongtaek (Samsung)", "focus": "world's largest memory fab campus"}, {"name": "Icheon (SK hynix)", "focus": "DRAM / HBM HQ & fabs"}, {"name": "Yongin Mega-Cluster", "focus": "new fab city (Samsung + SK, to 2040s)"}],
     "valuechain": "The memory & display apex — imports tools & materials, exports the DRAM, NAND, HBM and OLED the world's devices run on.",
     "sourcing": {"buy": ["Litho & process tools", "photoresist, wafers, gases", "display materials"], "sell": ["DRAM / NAND / HBM", "OLED panels", "foundry wafers"]},
     "tags": {"Components": 2, "Optical": 3, "Battery": 1, "Automotive": 1, "Precision": 2, "Materials": 2, "Appliances": 1, "Semiconductor": 3},
     "stats": [{"k": "Samsung+SK", "v": "~60% world DRAM"}, {"k": "HBM", "v": "SK hynix ~60%"}, {"k": "Yongin", "v": "mega-cluster build-out"}],
     "note": "The single densest memory & display cluster on earth; foundry is the one area where it trails Taiwan."},
    {"name": "Chungcheong (Cheongju)", "dom": "SEMI", "area": "Cheongju · Cheonan · Ochang", "lon": 127.49, "lat": 36.64,
     "tagline": "NAND & battery belt — SK hynix's M15 NAND fab, Samsung packaging (Cheonan/Asan) and LG Energy Solution's battery base.",
     "clusters": [
        {"seg": "NAND memory", "level": 3, "what": "SK hynix M15 — a flagship 3D-NAND fab.", "anchors": ["SK hynix"]},
        {"seg": "EV batteries", "level": 3, "what": "LG Energy Solution (Ochang) — a global battery leader.", "anchors": ["LG Energy Solution"]},
        {"seg": "Packaging & display", "level": 2, "what": "Samsung back-end & display module base (Cheonan/Asan).", "anchors": ["Samsung", "Samsung Display"]},
     ],
     "subdistricts": [{"name": "Cheongju", "focus": "SK hynix NAND (M15)"}, {"name": "Ochang", "focus": "LG Energy Solution batteries"}, {"name": "Cheonan / Asan", "focus": "Samsung packaging & display"}],
     "valuechain": "NAND fabrication plus battery cell manufacturing — memory and energy-storage in one corridor.",
     "sourcing": {"buy": ["Fab tools, gases, chemicals", "cathode / anode materials", "separators & electrolyte"], "sell": ["3D-NAND flash", "EV battery cells", "packaged chips & modules"]},
     "tags": {"Components": 1, "Optical": 1, "Battery": 3, "Automotive": 1, "Precision": 1, "Materials": 2, "Appliances": 0, "Semiconductor": 3},
     "stats": [{"k": "SK hynix", "v": "M15 NAND fab"}, {"k": "LG ES", "v": "global battery leader"}, {"k": "Focus", "v": "NAND + batteries"}],
     "note": "Where Korea's memory and EV-battery strengths physically overlap."},
    {"name": "Gumi", "dom": "ELEC", "area": "Gyeongbuk · Gumi", "lon": 128.34, "lat": 36.12,
     "tagline": "The legacy electronics base — Samsung & LG's display, mobile and components heartland inland.",
     "clusters": [
        {"seg": "Displays & modules", "level": 2, "what": "Panel & module manufacturing for Samsung/LG.", "anchors": ["Samsung Display", "LG Display"]},
        {"seg": "Mobile & electronics", "level": 2, "what": "Handset, network-gear and electronics assembly.", "anchors": ["Samsung Electronics", "LG Electronics"]},
        {"seg": "Components & EMS", "level": 2, "what": "Passive & connector supply, contract manufacturing.", "anchors": ["KH Vatec", "Partron"]},
     ],
     "subdistricts": [{"name": "Gumi National Industrial Complex", "focus": "display, mobile, electronics"}],
     "valuechain": "Mid-stream electronics manufacturing — displays, devices and components feeding Korea's brands.",
     "sourcing": {"buy": ["Display & panel materials", "components, passives, connectors", "chips & modules"], "sell": ["Displays & modules", "mobile / network devices", "EMS assemblies"]},
     "tags": {"Components": 2, "Optical": 2, "Battery": 0, "Automotive": 0, "Precision": 1, "Materials": 1, "Appliances": 1, "Semiconductor": 1},
     "stats": [{"k": "Base", "v": "Samsung / LG legacy"}, {"k": "Focus", "v": "display + mobile"}, {"k": "Zone", "v": "Gumi Industrial Complex"}],
     "note": "An established components & display base; volume has been shifting to SE-Asia / Vietnam over time."},
]
KOREA = {
    "name": "South Korea", "code": "kr", "dom": "SEMI",
    "tagline": "Memory & displays — Samsung & SK hynix make ~60% of the world's DRAM and most of its HBM; OLED leader; top-3 EV batteries.",
    "macro": KR_MACRO, "role": KR_ROLE, "role_take": KR_ROLE_TAKE, "cities": KR_CITIES,
    "domains": DOMAINS, "taxonomy": TAX, "glossary": GLOSSARY,
}

# ============================ JAPAN ============================
JP_MACRO = [
    {"key": "gdp", "k": "GDP growth", "v": "+1.0%", "as_of": "2025", "source": "Cabinet Office / IMF", "glo": "GDP growth", "basis": "YoY",
     "view": {"metric": "value", "ref": 0, "good": "high"}, "series": [["2021", 2.6], ["2022", 1.0], ["2023", 1.5], ["2024", 0.1], ["2025", 1.0]]},
    {"key": "cpi", "k": "CPI", "v": "+2.7%", "as_of": "2025", "source": "Statistics Bureau", "glo": "CPI", "basis": "YoY",
     "view": {"metric": "value", "ref": 0, "good": "band", "band": [0.5, 2.5]}, "series": [["2021", -0.2], ["2022", 2.5], ["2023", 3.3], ["2024", 2.7], ["2025", 2.7]]},
    {"key": "boj", "k": "BOJ policy rate", "v": "0.5%", "as_of": "2025", "source": "Bank of Japan", "note": "exited negative rates 2024",
     "view": {"metric": "value", "ref": 0, "good": "none"}, "series": [["2021", -0.1], ["2022", -0.1], ["2023", -0.1], ["2024", 0.1], ["2025", 0.5]]},
    {"key": "equip", "k": "Chip-equipment sales", "v": "¥4.9T", "as_of": "FY2025", "source": "SEAJ", "note": "~30% of world WFE",
     "view": {"metric": "value", "ref": 0, "good": "none"}, "series": []},
]
JP_ROLE = [
    {"node": "Semiconductor equipment (WFE)", "scope": "Tokyo Electron, Canon, Screen", "share": 30, "disp": "~30%", "type": "hold", "source": "industry", "year": "2025", "glo": "Semiconductor equipment"},
    {"node": "Materials & chemicals", "scope": "photoresist, wafers, gases", "share": 50, "disp": "~50%+", "type": "hold", "source": "industry", "year": "2025"},
    {"node": "Passive components (MLCC)", "scope": "Murata, TDK, Taiyo Yuden", "share": 50, "disp": "~50%", "type": "hold", "source": "industry", "year": "2025"},
    {"node": "Image sensors (CIS)", "scope": "Sony", "share": 50, "disp": "~50%", "type": "hold", "source": "industry", "year": "2025"},
    {"node": "Power / SiC & auto MCU", "scope": "ROHM, Renesas, Mitsubishi", "share": 20, "disp": "strong", "type": "hold", "source": "industry", "year": "2025"},
    {"node": "Leading-edge logic", "scope": "rebuilding — Rapidus 2nm, TSMC JASM", "share": 2, "disp": "building", "type": "gap", "source": "industry", "year": "2025", "glo": "leading-edge logic"},
]
JP_ROLE_TAKE = ("Japan owns the picks-and-shovels — ~30% of chip-making equipment and the materials nearly every fab "
                "depends on (photoresist, wafers, gases), plus the world's MLCC (Murata) and image sensors (Sony). Its gap "
                "is leading-edge logic, now being rebuilt via TSMC's Kumamoto fab and Rapidus's 2nm bet.")
JP_CITIES = [
    {"name": "Kanto (Tokyo)", "dom": "SEMI", "area": "Tokyo · Kanagawa · Ibaraki", "lon": 139.70, "lat": 35.68,
     "tagline": "The equipment & R&D brain — Tokyo Electron, Canon, Nikon, Advantest, Sony and Renesas headquarters.",
     "clusters": [
        {"seg": "Semiconductor equipment", "level": 3, "what": "Front-end tools, lithography & test — a global WFE pillar.", "anchors": ["Tokyo Electron", "Canon", "Nikon", "Advantest", {"n": "Applied Materials", "o": "US"}]},
        {"seg": "Image sensors & devices", "level": 3, "what": "Sony — the world's #1 CMOS image-sensor maker.", "anchors": ["Sony"]},
        {"seg": "Auto / MCU & passives", "level": 2, "what": "Microcontrollers and passive components HQ.", "anchors": ["Renesas", "TDK", "Taiyo Yuden"]},
     ],
     "subdistricts": [{"name": "Tokyo metro", "focus": "Tokyo Electron, Advantest, Sony, Renesas HQ"}, {"name": "Kanagawa / Ibaraki", "focus": "R&D fabs & equipment plants"}],
     "valuechain": "Upstream tools + materials + R&D — sells the equipment and image sensors the rest of the world's fabs and cameras depend on.",
     "sourcing": {"buy": ["Precision parts & optics", "specialty chemicals & metals", "chips for own devices"], "sell": ["Fab equipment & test handlers", "CMOS image sensors", "MCUs & passives"]},
     "tags": {"Components": 3, "Optical": 3, "Battery": 0, "Automotive": 2, "Precision": 3, "Materials": 2, "Appliances": 1, "Semiconductor": 3},
     "stats": [{"k": "Tokyo Electron", "v": "#3 WFE globally"}, {"k": "Sony", "v": "~50% image sensors"}, {"k": "Advantest", "v": "#1 chip testers"}],
     "note": "The capital of chip equipment & sensors — the tools half of the supply chain, not volume fabrication."},
    {"name": "Kansai (Osaka–Kyoto)", "dom": "COMP", "area": "Osaka · Kyoto · Shiga", "lon": 135.50, "lat": 34.80,
     "tagline": "The passives & materials powerhouse — Murata, Nidec, Kyocera, ROHM, Nitto and Panasonic: the world's MLCC heart.",
     "clusters": [
        {"seg": "Passive components", "level": 3, "what": "Murata alone makes ~40% of the world's MLCCs; deep passive ecosystem.", "anchors": ["Murata", "Nidec", "Kyocera", "Nichicon"]},
        {"seg": "Power & analog semis", "level": 2, "what": "Power devices, SiC and analog.", "anchors": ["ROHM"]},
        {"seg": "Materials & batteries", "level": 2, "what": "Films, materials and battery/appliance manufacturing.", "anchors": ["Nitto Denko", "Panasonic"]},
     ],
     "subdistricts": [{"name": "Kyoto (Murata, Kyocera, ROHM, Nidec)", "focus": "passives, power, motors"}, {"name": "Osaka (Panasonic, Nitto)", "focus": "materials, batteries, appliances"}],
     "valuechain": "The components & materials supplier to the world — passives, motors, films and power devices that every electronic product needs.",
     "sourcing": {"buy": ["Ceramic & metal powders", "specialty films & chemicals", "wafers for power devices"], "sell": ["MLCCs & passives", "precision motors (Nidec)", "power semis & materials"]},
     "tags": {"Components": 3, "Optical": 1, "Battery": 2, "Automotive": 2, "Precision": 3, "Materials": 3, "Appliances": 2, "Semiconductor": 2},
     "stats": [{"k": "Murata", "v": "~40% world MLCC"}, {"k": "Nidec", "v": "global #1 motors"}, {"k": "Focus", "v": "passives + materials"}],
     "note": "Arguably the most irreplaceable passive-component & materials cluster in the world."},
    {"name": "Kyushu (Kumamoto)", "dom": "SEMI", "area": "Kumamoto · Nagasaki · Oita", "lon": 130.70, "lat": 32.80,
     "tagline": "'Silicon Island' reborn — TSMC's JASM fab, Sony image sensors and ROHM SiC anchor a fast-growing auto-chip & sensor hub.",
     "clusters": [
        {"seg": "Foundry", "level": 3, "what": "TSMC JASM — 12-28nm in volume, a 6/7nm (later 2nm) Fab 2 coming; ~44 suppliers followed.", "anchors": [{"n": "TSMC (JASM)", "o": "TW"}, "Sony"]},
        {"seg": "Image sensors", "level": 3, "what": "Sony's image-sensor fabs (Kumamoto / Nagasaki).", "anchors": ["Sony"]},
        {"seg": "Power & compound semis", "level": 2, "what": "SiC and power devices for autos & industry.", "anchors": ["ROHM", "Mitsubishi Electric"]},
     ],
     "subdistricts": [{"name": "Kikuyo / Kumamoto", "focus": "TSMC JASM fab + supplier ecosystem"}, {"name": "Nagasaki", "focus": "Sony image-sensor fabs"}],
     "valuechain": "Volume fabrication reborn — foundry, image sensors and power devices, heavily feeding the auto & sensor markets.",
     "sourcing": {"buy": ["Fab tools, gases, chemicals", "SiC / Si wafers", "substrates & materials"], "sell": ["Mature-node foundry wafers", "CMOS image sensors", "SiC / power devices"]},
     "tags": {"Components": 1, "Optical": 3, "Battery": 0, "Automotive": 2, "Precision": 2, "Materials": 2, "Appliances": 0, "Semiconductor": 3},
     "stats": [{"k": "TSMC JASM", "v": "12-28nm + Fab 2"}, {"k": "Sony", "v": "image-sensor fabs"}, {"k": "Suppliers", "v": "~44 followed TSMC"}],
     "note": "Japan's volume-fab revival, led by a Taiwanese foundry (TSMC) — front-end manufacturing it had largely lost."},
    {"name": "Chubu (Nagoya)", "dom": "AUTO", "area": "Aichi · Gifu · Mie", "lon": 136.90, "lat": 35.18,
     "tagline": "The automotive-electronics core — Toyota, Denso and Aisin: the demand centre that pulls power, MCU and sensor content.",
     "clusters": [
        {"seg": "Automotive & EV", "level": 3, "what": "Toyota plus the Denso/Aisin mega-suppliers — a vast auto-electronics demand engine.", "anchors": ["Toyota", "Denso", "Aisin", "Toyota Industries"]},
        {"seg": "Auto semiconductors", "level": 2, "what": "MCUs, power and sensors for vehicles (Denso/Renesas JV ecosystem).", "anchors": ["Denso", "Renesas"]},
     ],
     "subdistricts": [{"name": "Toyota City / Kariya", "focus": "Toyota, Denso, Aisin HQ"}, {"name": "Nagoya metro", "focus": "auto-electronics suppliers"}],
     "valuechain": "A net CONSUMER of components — the world's largest automaker cluster pulling chips, power and sensors into vehicles.",
     "sourcing": {"buy": ["Auto MCUs & power semis", "sensors & connectors", "batteries & power modules"], "sell": ["Vehicles & EVs", "auto-electronics systems", "Tier-1 modules"]},
     "tags": {"Components": 2, "Optical": 1, "Battery": 1, "Automotive": 3, "Precision": 3, "Materials": 1, "Appliances": 0, "Semiconductor": 1},
     "stats": [{"k": "Toyota", "v": "world #1 automaker"}, {"k": "Denso", "v": "#2 global Tier-1"}, {"k": "Pull", "v": "auto-chip demand"}],
     "note": "The demand side — where Japan's chips & components get consumed into cars."},
    {"name": "Hokkaido (Chitose)", "dom": "SEMI", "area": "Chitose · Sapporo", "lon": 141.65, "lat": 42.82,
     "tagline": "The 2nm frontier — Rapidus, backed by Toyota/Sony/SoftBank and partnered with IBM, aims to mass-produce 2nm logic by 2027.",
     "clusters": [
        {"seg": "Leading-edge logic", "level": 3, "what": "Rapidus — Japan's bet to re-enter cutting-edge logic (2nm, IBM partnership).", "anchors": ["Rapidus", {"n": "IBM", "o": "US"}]},
        {"seg": "Supporting ecosystem", "level": 1, "what": "Emerging tool/material suppliers around the new fab.", "anchors": ["Hokkaido cluster"]},
     ],
     "subdistricts": [{"name": "Chitose", "focus": "Rapidus 2nm fab (IIM-1)"}],
     "valuechain": "A green-field leading-edge fab — the most ambitious, least-proven part of Japan's semiconductor revival.",
     "sourcing": {"buy": ["EUV tools & advanced materials", "ultra-pure gases & chemicals", "substrates"], "sell": ["2nm logic wafers (target 2027)"]},
     "tags": {"Components": 0, "Optical": 0, "Battery": 0, "Automotive": 0, "Precision": 1, "Materials": 1, "Appliances": 0, "Semiconductor": 2},
     "stats": [{"k": "Rapidus", "v": "2nm target 2027"}, {"k": "Partner", "v": "IBM"}, {"k": "Backers", "v": "Toyota, Sony, SoftBank"}],
     "note": "High-risk, high-reward — Japan's attempt to leapfrog back to the leading edge it exited decades ago."},
]
JAPAN = {
    "name": "Japan", "code": "jp", "dom": "SEMI",
    "tagline": "Equipment & materials backbone — ~30% of chip-making tools, the materials every fab needs, the world's MLCC (Murata) & image sensors (Sony); leading-edge rebuilding.",
    "macro": JP_MACRO, "role": JP_ROLE, "role_take": JP_ROLE_TAKE, "cities": JP_CITIES,
    "domains": DOMAINS, "taxonomy": TAX, "glossary": GLOSSARY,
}


# ---- End-market demand matrix (the Asia landing hero). DISTRIBUTOR ANGLE: which industries manufacture
# electronics-rich products, where, and how component-hungry they are — not who fabricates the chips.
# Strength v: 0 none · 1 present · 2 strong · 3 leads. Geography = where that industry's electronics
# manufacturing concentrates. Sourcing: Mordor Intelligence, Business Research Insights (distribution
# end-market split: Automotive 28% · Comms&Computing 25% · Industrial 18% · Medical 12%), industry.
VC_THESIS = ("For a components distributor the market isn't 'chips' — it's every industry now building "
             "electronics-rich products. Automotive and industrial alone pull ~46% of component demand; an EV "
             "carries 2–3× the silicon of a petrol car and AI data-centres are the fastest-rising draw. Chip makers "
             "are themselves a customer. Follow where the factories — and the demand — actually are.")
VC_STAGES = [
    ("auto", "Automotive & EV"), ("compute", "Computing & data centre"), ("mobile", "Mobile & consumer"),
    ("comms", "Comms & networking"), ("industrial", "Industrial & automation"), ("energy", "Energy & renewables"),
    ("medical", "Medical & healthcare"), ("aero", "Aerospace & defence"), ("semi", "Semiconductor & equipment"),
]
VC_COLS = [
    ("cn", "China", False), ("tw", "Taiwan", False), ("kr", "South Korea", False), ("jp", "Japan", False),
    ("sg", "Singapore", False), ("my", "Malaysia", False), ("vn", "Vietnam", False), ("th", "Thailand", False),
    ("in", "India", False),
]
def _c(v, s="", f="", ck=False): return {"v": v, "s": s, "f": f, "ck": ck}
VC_MATRIX = {
    "auto":       {"cn": _c(3, "world #1 in NEVs", "BYD, CATL, Geely, Bosch"), "tw": _c(1, "ADAS / EV components", "Foxconn EV, Delta"), "kr": _c(2, "", "Hyundai-Kia, LG, Samsung SDI"), "jp": _c(3, "Toyota–Denso ecosystem", "Toyota, Denso, Renesas"), "sg": _c(1), "my": _c(2, "auto-electronics, China+1", "Infineon, Bosch, Continental"), "vn": _c(1, "", "VinFast"), "th": _c(3, "'Detroit of Asia'", "Toyota, Honda, BYD, Delta"), "in": _c(2, "fast-growing", "Tata, Mahindra, Bosch")},
    "compute":    {"cn": _c(3, "servers, PCs, AI", "Lenovo, Inspur, Huawei"), "tw": _c(3, "world's server / AI-server ODM", "Foxconn, Quanta, Wiwynn, Wistron"), "kr": _c(2, "server memory", "Samsung, SK hynix"), "jp": _c(1), "sg": _c(2, "data-centre & HQ hub", "hyperscalers"), "my": _c(2, "DC boom (Johor)", "Nvidia/MS/GDS DC, EMS"), "vn": _c(1), "th": _c(1), "in": _c(1, "emerging DC")},
    "mobile":     {"cn": _c(3, "phones, TVs, wearables", "Apple OEM, Xiaomi, OPPO, TCL"), "tw": _c(2, "ODM / brands", "Foxconn, Pegatron"), "kr": _c(2, "", "Samsung, LG"), "jp": _c(2, "imaging / AV", "Sony, Panasonic"), "sg": _c(1), "my": _c(1), "vn": _c(3, "Samsung's largest phone base", "Samsung, LG, Foxconn"), "th": _c(2, "appliances / AV", ""), "in": _c(3, "#2 phone maker", "Apple (Foxconn/Tata), Samsung")},
    "comms":      {"cn": _c(3, "5G / telecom #1", "Huawei, ZTE"), "tw": _c(2, "networking ODM", "Accton, Zyxel"), "kr": _c(2, "", "Samsung Networks"), "jp": _c(2, "", "NEC, Fujitsu"), "sg": _c(1), "my": _c(1), "vn": _c(1), "th": _c(1), "in": _c(2, "5G rollout")},
    "industrial": {"cn": _c(3, "largest industrial base", "Inovance, Midea-KUKA"), "tw": _c(2, "IPC / automation", "Advantech, Delta"), "kr": _c(1), "jp": _c(3, "robots & automation", "Fanuc, Yaskawa, Mitsubishi, Keyence"), "sg": _c(2, "precision / automation", ""), "my": _c(1), "vn": _c(1), "th": _c(2, "", ""), "in": _c(2, "")},
    "energy":     {"cn": _c(3, "solar ~80%+, batteries, inverters", "LONGi, CATL, Sungrow, Huawei"), "tw": _c(1), "kr": _c(2, "EV batteries", "LG, SK, Samsung SDI"), "jp": _c(1), "sg": _c(1), "my": _c(2, "solar PV mfg", "First Solar, Hanwha"), "vn": _c(2, "solar modules", ""), "th": _c(1), "in": _c(2, "solar push", "")},
    "medical":    {"cn": _c(2, "", ""), "tw": _c(1), "kr": _c(1), "jp": _c(2, "", "Olympus, Terumo"), "sg": _c(3, "med-tech hub", "Medtronic, Siemens Healthineers, GE"), "my": _c(3, "medical devices (Penang)", "B. Braun, Boston Scientific"), "vn": _c(1), "th": _c(1, "medical / gloves", ""), "in": _c(2, "pharma + devices", "")},
    "aero":       {"cn": _c(2, "", "COMAC, AVIC"), "tw": _c(1), "kr": _c(2, "", "KAI, Hanwha"), "jp": _c(2, "", "Mitsubishi Heavy"), "sg": _c(3, "aerospace / MRO hub", "ST Engineering, P&W, Rolls-Royce MRO"), "my": _c(1), "vn": _c(1), "th": _c(1), "in": _c(2, "defence / space", "HAL, ISRO")},
    "semi":       {"cn": _c(3, "fabs + equipment buyer", "SMIC, Hua Hong"), "tw": _c(3, "TSMC, OSAT", "TSMC, ASE"), "kr": _c(3, "memory giants", "Samsung, SK hynix"), "jp": _c(3, "equipment & materials", "Tokyo Electron"), "sg": _c(3, "fabs & equipment", "GlobalFoundries, Micron, AMAT"), "my": _c(2, "OSAT / back-end", "Inari, Infineon"), "vn": _c(1), "th": _c(1), "in": _c(1, "first fabs", "Tata, Micron")},
}
# Demand drivers — the fastest-rising end-markets a distributor should watch (replaces supply chokepoints).
VC_DRIVERS = [
    {"label": "Automotive & EV", "size": "~28% of distribution · ~8% CAGR", "parts": "power (SiC/IGBT) · MCU · sensors · connectors", "detail": "EVs & ADAS carry 2–3× the component content of a petrol car — the single biggest demand driver.", "source": "Business Research Insights / Mordor"},
    {"label": "Computing & AI data centre", "size": "fastest-rising · AI capex surge", "parts": "memory (HBM/DDR5) · power · optical · connectors", "detail": "AI-server build-out is pulling memory, power-delivery and optical interconnect at record rates.", "source": "industry"},
    {"label": "Industrial & automation", "size": "~18% of distribution", "parts": "MCU · analog · power · sensors", "detail": "Factory automation, robotics and IoT keep MCU, analog and power demand structurally rising.", "source": "Business Research Insights"},
    {"label": "Energy & renewables", "size": "solar · storage · EV charging", "parts": "power semis · passives · connectors", "detail": "Solar, battery storage and charging infrastructure are a fast-growing power-electronics market.", "source": "industry"},
    {"label": "Mobile & consumer", "size": "largest base ~34%", "parts": "SoCs · small passives · displays", "detail": "Huge but maturing — still the volume floor of component demand.", "source": "Mordor"},
]
# Each country's manufacturing PROFILE for a distributor (categorical) — drives the map colouring + legend.
ROLES = {
    "cn": ("World's factory — all end-markets", "#185FA5"),
    "tw": ("Computing & AI servers (ODM)", "#D85A30"),
    "kr": ("Memory, displays & batteries", "#7F77DD"),
    "jp": ("Automotive, industrial & precision", "#EF9F27"),
    "sg": ("Med-tech, aerospace & semicap", "#1D9E75"),
    "my": ("EMS, data centre & medical", "#639922"),
    "vn": ("Mobile, consumer & EMS", "#D4537E"),
    "th": ("Automotive & appliances", "#0F6E56"),
    "ph": ("Electronics assembly & test", "#888780"),
    "in": ("Mobile, appliances & emerging", "#534AB7"),
}

# ---- Asia registry: drives the atlas overview map (one row per country). status live|planned.
# chip = curated electronics/chip supply-chain weight (0-100). gdp = 2025 real growth %. lon/lat = map centroid.
REGISTRY = {
    "layers": [
        {"key": "chip", "name": "Chip supply-chain weight", "unit": "/100"},
        {"key": "gdp", "name": "GDP growth", "unit": "% YoY"},
    ],
    "countries": [
        {"code": "cn", "name": "China", "status": "live", "href": "china.html", "lon": 103, "lat": 36, "chip": 100, "gdp": 5.0, "headline": "Biggest market + mature-node base; owns 85-98% of the clean-energy/materials stack."},
        {"code": "tw", "name": "Taiwan", "status": "live", "href": "taiwan.html", "lon": 121, "lat": 23.8, "chip": 98, "gdp": 7.7, "headline": "Leading-edge logic — TSMC, UMC, ASE, MediaTek; the chips China lacks."},
        {"code": "kr", "name": "South Korea", "status": "live", "href": "korea.html", "lon": 127.8, "lat": 36.5, "chip": 90, "gdp": 1.9, "headline": "Memory & display — Samsung, SK hynix (DRAM/NAND/HBM)."},
        {"code": "jp", "name": "Japan", "status": "live", "href": "japan.html", "lon": 138, "lat": 37, "chip": 80, "gdp": 1.0, "headline": "Materials, equipment & passives — Murata, Tokyo Electron, Shin-Etsu, Sony."},
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
    write("taiwan", TAIWAN)
    write("korea", KOREA)
    write("japan", JAPAN)
    for c in REGISTRY["countries"]:
        r = ROLES.get(c["code"])
        if r:
            c["role"], c["rc"] = r[0], r[1]
    REGISTRY["thesis"] = VC_THESIS
    REGISTRY["vc"] = {"stages": VC_STAGES, "cols": VC_COLS, "matrix": VC_MATRIX, "drivers": VC_DRIVERS}
    geo_f = WEB / "vendor" / "asia.geo.json"
    if geo_f.exists():
        REGISTRY["geo"] = json.loads(geo_f.read_text(encoding="utf-8"))
    blob = json.dumps(REGISTRY, ensure_ascii=False, separators=(",", ":"))
    (WEB / "asia-registry.js").write_text("window.ASIA = " + blob + ";\n", encoding="utf-8")
    live = sum(1 for c in REGISTRY["countries"] if c["status"] == "live")
    print(f"wrote web/asia-registry.js — {len(REGISTRY['countries'])} countries ({live} live), {len(VC_STAGES)}×{len(VC_COLS)} end-market demand matrix, {len(VC_DRIVERS)} demand drivers")


if __name__ == "__main__":
    main()
