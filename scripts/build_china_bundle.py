"""Build web/china-bundle.js (window.CHINA = {geo, macro, cities}) for the EMI China country page.

The China geo is converted offline (vendor/china.geo.json). City dossiers are a CURATED
intelligence layer (AI-deep-researched, periodically refreshed) — separate from the live macro feeds.
Run: python scripts/build_china_bundle.py
"""
import json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

# Domain palette (primary domain -> colour) used to colour the map markers.
DOMAINS = {
    "SEMI": ("Semiconductor", "#D85A30", "半导体"),
    "COMP": ("Components / Materials", "#7F77DD", "元件 / 材料"),
    "AUTO": ("Automotive / EV", "#EF9F27", "汽车 / 电动车"),
    "BAT":  ("Battery / Clean-energy", "#1D9E75", "电池 / 清洁能源"),
    "ELEC": ("Electronics / EMS", "#378ADD", "电子 / EMS"),
    "APPL": ("Appliances / Precision", "#64748b", "家电 / 精密"),
}

# Taxonomy domains for the per-city strength tags (level 1=present,2=strong,3=leading)
TAX = ["Components", "Optical", "Battery", "Automotive", "Precision", "Materials", "Appliances", "Semiconductor"]

# Plain-language definitions for jargon — shown as hover tooltips everywhere a term appears.
GLOSSARY = {
    "NdFeB magnet": "Neodymium-iron-boron — the strongest commercial permanent magnet; powers EV/wind/robot motors, speakers, hard drives.",
    "sintered output": "Magnets made by pressing & heating powder into a solid block — the dominant high-performance NdFeB process.",
    "LFP cathode": "Lithium iron phosphate — a cheaper, safer EV-battery cathode chemistry; China makes almost all of it.",
    "mature-node": "Older, larger chip geometries (28nm and above) — for power, analog and MCUs, not cutting-edge logic.",
    "leading-edge logic": "The most advanced chips (≤7nm) for CPUs/GPUs/AI — China is constrained here by export controls.",
    "Battery cells": "The finished lithium-ion cells assembled into EV and storage battery packs.",
    "Solar modules": "Finished photovoltaic panels (cells laminated into a module).",
    "Display (LCD)": "Flat-panel display manufacturing — LCD/OLED panels for TVs, monitors, phones.",
    "High-tech exports": "Exports of R&D-intensive goods — aerospace, computers, pharma, instruments, electrical machinery (World Bank definition).",
    "Caixin Mfg PMI": "Caixin China Manufacturing PMI — compiled by S&P Global from ~500 smaller, private, export-oriented manufacturers (rebranded 'RatingDog' in 2025 after Caixin's sponsorship ended); >50 = expansion. Reported separately from, and often above, the official NBS PMI.",
    "NBS PMI": "Official PMI from China's NBS (National Bureau of Statistics) & CFLP — surveys ~3,200 mostly large & state-owned firms; the most policy-watched gauge. Tends to run below the private Caixin/RatingDog PMI; >50 = expansion.",
    "CPI": "Consumer Price Index — headline consumer inflation, year-over-year.",
    "PPI": "Producer Price Index — factory-gate inflation; leads CPI and signals industrial demand.",
    "Industrial production": "Output of 'above-scale' factories, mines & utilities, year-over-year — a core activity gauge.",
    "Retail sales": "Total retail sales of consumer goods, year-over-year — a consumption gauge.",
    "Fixed-asset investment": "Spending on infrastructure, factories, property & equipment, YTD year-over-year.",
    "Trade balance": "Exports minus imports of goods.",
    "Surveyed unemployment": "Urban surveyed jobless rate (NBS household survey).",
    "M2 growth": "Broad money supply (cash + deposits) growth — a liquidity/credit signal.",
    "Auto production": "Vehicles assembled per year (passenger + commercial), incl. NEV.",
    "OSAT": "Outsourced Semiconductor Assembly & Test — back-end chip packaging/testing.",
    "Foundry": "A fab that manufactures chips designed by others (e.g. SMIC, TSMC).",
    "DRAM": "Dynamic RAM — main-memory chips for PCs, phones, servers.",
    "NAND": "Flash memory — non-volatile storage (SSDs, phones).",
    "DDIC": "Display Driver IC — the chip that drives a panel's pixels.",
    "BMS": "Battery Management System — electronics that monitor, balance & protect cells.",
    "SiC": "Silicon carbide — wide-bandgap semiconductor for efficient EV/charging power electronics.",
    "IGBT": "Insulated-gate bipolar transistor — a power switch for motor drives & inverters.",
    "Tier-1": "A direct supplier to vehicle makers — sells finished sub-systems to the OEM.",
    "EMS": "Electronics Manufacturing Services — contract assembly of electronics for brands.",
    "ODM": "Original Design Manufacturer — designs & builds products other brands rebadge.",
    "HJT": "Heterojunction — a high-efficiency solar-cell technology.",
    "NEV": "New-Energy Vehicle — battery-electric + plug-in hybrid + fuel-cell vehicles.",
}

# Simplified-Chinese glossary (shown when the page is switched to 简体). Falls back to English if missing.
GLOSSARY_ZH = {
    "NdFeB magnet": "钕铁硼 — 最强的商用永磁体;用于电动车/风电/机器人电机、扬声器、硬盘。",
    "sintered output": "把粉末压制并加热成实心块体制成的磁体 — 主流的高性能钕铁硼工艺。",
    "LFP cathode": "磷酸铁锂 — 更便宜、更安全的电动车电池正极;中国产量几乎全球独占。",
    "mature-node": "较旧、较大的芯片制程(28nm 及以上)— 用于功率、模拟、MCU,而非尖端逻辑。",
    "leading-edge logic": "最先进的芯片(≤7nm),用于 CPU/GPU/AI — 中国在此受出口管制限制。",
    "Battery cells": "组装进电动车与储能电池包的成品锂离子电芯。",
    "Solar modules": "成品光伏组件(电池片层压成组件)。",
    "Display (LCD)": "平板显示制造 — 用于电视/显示器/手机的 LCD/OLED 面板。",
    "High-tech exports": "研发密集型产品出口 — 航空、计算机、医药、仪器、电气机械(世界银行定义)。",
    "Caixin Mfg PMI": "财新中国制造业 PMI — 由标普全球 S&P Global 编制、调查约 500 家中小型民营出口制造商(2025 年财新冠名结束后更名「RatingDog」);>50=扩张。与官方 NBS PMI 分别统计,且常高于后者。",
    "NBS PMI": "中国官方 PMI(国家统计局与中物联)— 调查约 3,200 家多为大型/国企,最受政策关注。通常低于民营的财新/RatingDog PMI;>50=扩张。",
    "CPI": "消费者物价指数 — 居民消费通胀,同比。",
    "PPI": "工业生产者出厂价格指数 — 工厂端通胀;领先 CPI,反映工业需求。",
    "Industrial production": "规模以上工厂、矿业、公用事业的产出,同比 — 核心活动指标。",
    "Retail sales": "社会消费品零售总额,同比 — 消费指标。",
    "Fixed-asset investment": "基建、工厂、房地产、设备的投资,年初至今同比。",
    "Trade balance": "货物出口减进口。",
    "Surveyed unemployment": "城镇调查失业率(国家统计局住户调查)。",
    "M2 growth": "广义货币供应(现金+存款)增速 — 流动性/信贷信号。",
    "Auto production": "每年组装的整车(乘用车+商用车,含新能源车)。",
    "OSAT": "外包半导体封装与测试 — 芯片后段封测。",
    "Foundry": "为他人设计的芯片代工制造的晶圆厂(如中芯国际、台积电)。",
    "DRAM": "动态随机存取存储器 — 用于 PC/手机/服务器的主存。",
    "NAND": "闪存 — 非易失性存储(SSD、手机)。",
    "DDIC": "显示驱动 IC — 驱动面板像素的芯片。",
    "BMS": "电池管理系统 — 监测、均衡、保护电芯的电子系统。",
    "SiC": "碳化硅 — 宽禁带半导体,用于高效电动车/充电功率电子。",
    "IGBT": "绝缘栅双极晶体管 — 用于电机驱动与逆变器的功率开关。",
    "Tier-1": "整车厂的一级供应商 — 向 OEM 提供成品子系统。",
    "EMS": "电子制造服务 — 为品牌代工组装电子产品。",
    "ODM": "原始设计制造商 — 设计并制造由其他品牌贴牌的产品。",
    "HJT": "异质结 — 一种高效太阳能电池技术。",
    "NEV": "新能源汽车 — 纯电+插电混动+燃料电池。",
}

# Provincial macro (curated/approximate, 2024) for the map choropleth. Keyed EXACTLY to geo names.
PROVINCES = {
    "Guangdong": {"gdp": 14.16, "growth": 3.5}, "Jiangsu": {"gdp": 13.70, "growth": 5.8},
    "Shandong": {"gdp": 9.86, "growth": 5.7}, "Zhejiang": {"gdp": 9.01, "growth": 5.5},
    "Sichuan": {"gdp": 6.47, "growth": 5.7}, "Henan": {"gdp": 6.36, "growth": 5.1},
    "Hubei": {"gdp": 6.00, "growth": 5.8}, "Fujian": {"gdp": 5.78, "growth": 5.5},
    "Hunan": {"gdp": 5.33, "growth": 4.8}, "Shanghai": {"gdp": 5.39, "growth": 5.0},
    "Anhui": {"gdp": 5.06, "growth": 5.8}, "Beijing": {"gdp": 4.98, "growth": 5.2},
    "Hebei": {"gdp": 4.74, "growth": 5.4}, "Shaanxi": {"gdp": 3.54, "growth": 5.3},
    "Jiangxi": {"gdp": 3.42, "growth": 5.1}, "Liaoning": {"gdp": 3.24, "growth": 5.1},
    "Chongqing": {"gdp": 3.21, "growth": 5.7}, "Yunnan": {"gdp": 3.11, "growth": 3.3},
    "Guangxi": {"gdp": 2.84, "growth": 4.6}, "Inner Mongol": {"gdp": 2.66, "growth": 5.8},
    "Shanxi": {"gdp": 2.59, "growth": 2.3}, "Guizhou": {"gdp": 2.27, "growth": 5.3},
    "Xinjiang": {"gdp": 2.05, "growth": 6.1}, "Tianjin": {"gdp": 1.80, "growth": 5.1},
    "Heilongjiang": {"gdp": 1.63, "growth": 2.7}, "Jilin": {"gdp": 1.43, "growth": 4.0},
    "Gansu": {"gdp": 1.34, "growth": 5.8}, "Hainan": {"gdp": 0.80, "growth": 3.7},
    "Ningxia": {"gdp": 0.59, "growth": 5.6}, "Qinghai": {"gdp": 0.39, "growth": 5.6},
    "Xizang": {"gdp": 0.28, "growth": 6.3},
}

# Map choropleth layers (the "macro economy status" the map can be coloured by).
LAYERS = [
    {"key": "gdp", "label": "Provincial GDP", "label_zh": "各省 GDP", "field": "gdp", "unit": "¥T", "colors": ["#e6f1fb", "#85b7eb", "#185fa5", "#042c53"]},
    {"key": "growth", "label": "GDP growth", "label_zh": "GDP 增速", "field": "growth", "unit": "%", "colors": ["#fbeaea", "#f0c98a", "#5dcaa5", "#0f6e56"]},
]

CHINA_MACRO = {
    "tagline": "Largest market + mature-node capacity; building memory, equipment & clean-energy self-sufficiency",
    "tagline_zh": "全球最大市场 + 成熟制程产能;正建立存储、设备与清洁能源的自给能力",
    "headline": [
        {"k": "GDP", "k_zh": "GDP", "v": "$18.7T", "src": "World Bank / NBS", "sid": "gdp", "unit": "$T",
         "view": {"metric": "value", "ref": 0, "good": "high", "reflbl": "0% = recession line"},
         "detail": "Nominal GDP, current US$. World's 2nd-largest economy; YoY growth has cooled from double digits to ~5%.",
         "detail_zh": "名义 GDP(现价美元)。全球第二大经济体;同比增速已从两位数放缓至约 5%。"},
        {"k": "Caixin Mfg PMI", "k_zh": "财新制造业 PMI", "v": "50.4", "src": "Caixin (press)", "sid": "pmi", "unit": "", "glo": "Caixin Mfg PMI",
         "view": {"metric": "value", "ref": 50, "good": "high", "reflbl": "50 = boom/bust"},
         "detail": "Private-survey manufacturing PMI; hovering right at the 50 boom/bust line through 2024-26 — no decisive recovery.",
         "detail_zh": "民间制造业 PMI;2024-26 一直贴着荣枯线 50,缺乏决定性复苏。"},
        {"k": "CPI", "k_zh": "CPI 通胀", "v": "0.2%", "src": "World Bank", "sid": "cpi", "unit": "%", "glo": "CPI",
         "view": {"metric": "value", "ref": 0, "good": "band", "band": [1, 3], "reflbl": "1-3% healthy"},
         "detail": "Consumer inflation has fallen to near-zero — below the healthy 1-3% band, signalling weak demand / deflation risk.",
         "detail_zh": "消费通胀已降至接近零 — 低于 1-3% 的健康区间,显示内需疲弱、存在通缩风险。"},
        {"k": "High-tech exports", "k_zh": "高科技出口", "v": "$857B", "src": "World Bank", "sid": "htx", "unit": "$B", "glo": "High-tech exports",
         "view": {"metric": "yoy", "ref": 0, "good": "high", "reflbl": "0%"},
         "detail": "R&D-intensive goods exports. YoY growth has slowed sharply from the 2010s pace.",
         "detail_zh": "研发密集型产品出口。同比增速较 2010 年代已明显放缓。"},
        {"k": "Auto production", "k_zh": "汽车产量", "v": "31M", "src": "OICA", "sid": "auto", "unit": "M",
         "view": {"metric": "yoy", "ref": 0, "good": "high", "reflbl": "0%"},
         "detail": "World's largest vehicle producer; NEVs now ~40% of output and the export growth engine.",
         "detail_zh": "全球最大汽车生产国;新能源车已占约 40%,是出口增长引擎。"},
    ],
    "more": [
        {"k": "PPI", "k_zh": "PPI 出厂价", "v": "-1.8%", "src": "NBS (approx)", "glo": "PPI", "view": {"metric": "value", "ref": 0, "good": "high"},
         "series": [["2019", -0.3], ["2020", -1.8], ["2021", 8.1], ["2022", 4.1], ["2023", -3.0], ["2024", -2.2], ["2025", -1.8]]},
        {"k": "Industrial production", "k_zh": "工业增加值", "v": "+5.8%", "src": "NBS (approx)", "glo": "Industrial production", "view": {"metric": "value", "ref": 0, "good": "high"},
         "series": [["2019", 5.7], ["2020", 2.8], ["2021", 9.6], ["2022", 3.6], ["2023", 4.6], ["2024", 5.8], ["2025", 5.8]]},
        {"k": "Retail sales", "k_zh": "社零消费", "v": "+3.5%", "src": "NBS (approx)", "glo": "Retail sales", "view": {"metric": "value", "ref": 0, "good": "high"},
         "series": [["2019", 8.0], ["2020", -3.9], ["2021", 12.5], ["2022", -0.2], ["2023", 7.2], ["2024", 3.5], ["2025", 3.5]]},
        {"k": "Fixed-asset investment", "k_zh": "固定资产投资", "v": "+3.2%", "src": "NBS (approx)", "glo": "Fixed-asset investment", "view": {"metric": "value", "ref": 0, "good": "high"},
         "series": [["2019", 5.4], ["2020", 2.9], ["2021", 4.9], ["2022", 5.1], ["2023", 3.0], ["2024", 3.2], ["2025", 3.2]]},
        {"k": "M2 growth", "k_zh": "M2 货币供应", "v": "+7.0%", "src": "PBoC (approx)", "glo": "M2 growth", "view": {"metric": "value", "ref": 0, "good": "high"},
         "series": [["2019", 8.7], ["2020", 10.1], ["2021", 9.0], ["2022", 11.8], ["2023", 9.7], ["2024", 7.0], ["2025", 7.0]]},
        {"k": "Surveyed unemployment", "k_zh": "城镇调查失业率", "v": "5.1%", "src": "NBS (approx)", "glo": "Surveyed unemployment", "view": {"metric": "value", "ref": 5.5, "good": "low"},
         "series": [["2019", 5.2], ["2020", 5.6], ["2021", 5.1], ["2022", 5.5], ["2023", 5.2], ["2024", 5.1], ["2025", 5.1]]},
        {"k": "Total exports", "k_zh": "出口总额", "v": "$3.58T", "d": "goods", "src": "Customs (approx)"},
        {"k": "Total imports", "k_zh": "进口总额", "v": "$2.59T", "d": "goods", "src": "Customs (approx)"},
        {"k": "Trade balance", "k_zh": "贸易顺差", "v": "+$0.99T", "d": "surplus", "src": "Customs (approx)", "glo": "Trade balance"},
    ],
    "industry": [
        {"k": "Battery cells", "k_zh": "电池电芯", "v": "~85%", "note": "global capacity", "note_zh": "全球产能", "glo": "Battery cells"},
        {"k": "NdFeB magnets", "k_zh": "钕铁硼磁体", "v": "94%", "note": "global sintered output", "note_zh": "全球烧结产量", "glo": "NdFeB magnet"},
        {"k": "Solar modules", "k_zh": "太阳能组件", "v": "80%+", "note": "global production", "note_zh": "全球产量", "glo": "Solar modules"},
        {"k": "LFP cathode", "k_zh": "磷酸铁锂正极", "v": "98%+", "note": "global", "note_zh": "全球", "glo": "LFP cathode"},
        {"k": "Display (LCD)", "k_zh": "显示面板", "v": "#1", "note": "global panel output", "note_zh": "全球面板产量", "glo": "Display (LCD)"},
        {"k": "Leading-edge logic", "k_zh": "先进逻辑芯片", "v": "<1%", "note": "export-control constrained", "note_zh": "受出口管制限制", "glo": "leading-edge logic"},
    ],
}

# ---- City dossiers (curated). Full = Ningbo, Guangzhou. Others = light markers. ----
def cl(seg, level, what, anchors):
    return {"seg": seg, "level": level, "what": what, "anchors": anchors}

CITIES = [
    {
        "name": "Ningbo", "name_zh": "宁波", "lon": 121.55, "lat": 29.87, "dom": "COMP",
        "tagline": "Not a chip town — a components, specialty-materials & Tier-1 auto-electronics powerhouse; overwhelmingly private, port-driven (world's #1 cargo port).",
        "tagline_zh": "并非芯片之城 — 而是元件、特殊材料与汽车电子 Tier-1 重镇;民营主导、依托全球第一大货运港。",
        "clusters": [
            cl("Rare-earth NdFeB magnets", 3, "China's 'Magnet Capital' — 40%+ of national output; for EV/wind/robot motors. Geopolitically hot (2025 rare-earth export controls).", ["Yunsheng (韵升) — ~25% China NEV traction-magnet share", "Ketian", "Newland"]),
            cl("Automotive electronics / Tier-1", 3, "China's densest private Tier-1 cluster; ~5,000 auto-parts firms within 50km; 4 in global top-100.", ["Joyson 均胜 (¥55.9B, #2 global passive safety)", "Tuopu 拓普 (thermal/NVH, Tesla Optimus actuators)", "Minth 敏实 (EV battery enclosures #1)", "Huaxiang", "Jifeng"]),
            cl("Battery materials", 3, "World #1 in artificial-graphite anode and high-nickel cathode.", ["Shanshan 杉杉 (anode + LCD polarizer)", "Ronbay 容百 (high-nickel cathode)"]),
            cl("Precision optics", 3, "1-in-3 Android camera modules; #1 automotive lens.", ["Sunny Optical 舜宇 (Yuyao)", "Exciton 激智 (optical films)"]),
            cl("Relays / connectors / low-voltage", 3, "Relay output 200M+/yr; Guanhaiwei = world's largest European-socket base.", ["Forward 先锋", "Huaguan 华冠", "Tianbo 天波", "Bull 公牛 (sockets ~50% China)"]),
            cl("Small appliances", 3, "Cixi makes ~60% of the world's small appliances (irons 60%, hair dryers 30%).", ["Fotile 方太", "Bull 公牛"]),
            cl("Molds / plastics + injection machines", 3, "Yuyao = China's Plastics City / mold capital; injection-molding machines #1 world.", ["Haitian 海天 International"]),
            cl("Inverters / ESS + PV", 2, "Major inverter/storage exporters; HJT solar.", ["Deye 德业", "Risen 东方日升"]),
            cl("Semiconductor materials / OSAT", 2, "Sputtering targets #1 world; OSAT #14 global (Yuyao).", ["Jiangfeng 江丰", "Yongsi 甬矽"]),
        ],
        "subdistricts": [
            {"name": "Cixi 慈溪", "focus": "Small appliances + sockets/connectors + bearings; magnets"},
            {"name": "Yuyao 余姚", "focus": "Plastics City + mold capital; Sunny Optical; semi targets"},
            {"name": "Beilun 北仑", "focus": "Deep-water port; auto-parts parks; magnets; steel"},
            {"name": "Yinzhou 鄞州", "focus": "HQ district — Yunsheng, Shanshan, Ronbay; auto Tier-1"},
            {"name": "Zhenhai 镇海", "focus": "Sinopec ZRCC — China's largest refinery (plastics/film feedstock)"},
            {"name": "Jiangbei 江北", "focus": "Optical-film hub; sensors"},
        ],
        "valuechain": "Sits at the components / specialty-materials / Tier-1 sub-system layer — not chips, not final assembly, not design. Private-enterprise DNA (民企 96.7% of entities, 85% of jobs); export+port-driven.",
        "sourcing": {
            "buy": ["Relays, connectors, low-voltage electrical", "NdFeB magnets & assemblies", "Precision plastic enclosures / molds", "Camera modules & optical films", "Battery anode/cathode materials"],
            "sell": ["Automotive MCUs / power semis / SiC-GaN (to Joyson, Tuopu)", "Connectors for auto harnesses", "Specialty graphite/silicon (to Shanshan)", "Test & measurement equipment"],
        },
        "tags": {"Components": 3, "Optical": 3, "Battery": 3, "Automotive": 3, "Precision": 3, "Materials": 3, "Appliances": 3, "Semiconductor": 1},
        "stats": [{"k": "2024 trade", "v": "¥1.42T (China #5)"}, {"k": "Mfg champions", "v": "104+ (#1 city)"}, {"k": "Port", "v": "#1 cargo / #3 container"}],
        "note": "AI-deep-researched, cross-verified (caught common errors: Delixi=Wenzhou, Vatti=Guangdong, Fuyao=Fujian — not Ningbo).",
    },
    {
        "name": "Guangzhou", "name_zh": "广州", "lon": 113.26, "lat": 23.13, "dom": "AUTO",
        "tagline": "China's auto-manufacturing capital + commerce/trade gateway (Canton Fair) + 'World Display Capital' — SOE/JV-led & assembly-oriented, the opposite of Shenzhen's private design ecosystem.",
        "tagline_zh": "中国汽车制造之都 + 贸易门户(广交会)+ '世界显示之都';以国企/合资和整车组装为主,与深圳的民营设计生态相反。",
        "clusters": [
            cl("Automobiles & NEV", 3, "A top auto-output city — ~3.18M vehicles in 2024 (38% NEV), full ICE+hybrid+BEV across six OEM brands; growing car-export hub via Nansha.", ["GAC Group 广汽 (2.0M units)", "GAC-Toyota (756k)", "GAC-Honda", "Dongfeng Nissan (Huadu)", "GAC Aion (EV, Panyu)", "XPeng 小鹏 (HQ Tianhe)"]),
            cl("Display panels / Ultra-HD", 3, "'World Display Capital' — TCL CSOT T9 8.6-gen fab (180k sheets/mo, ~¥30B/yr) + buying LG Display's Guangzhou LCD plant. #2 global TV panel.", ["TCL CSOT 华星光电 (T9 8.6G)", "LG Display GZ (→CSOT)"]),
            cl("Auto parts / automotive electronics", 2, "Deep Tier-1/Tier-2 supplier clusters (Huadu, Panyu) feeding local assembly + export.", ["Guangzhou Auto Parts City (Huadu)", "Bosch / Continental / Denso (regional supply)"]),
            cl("Biomedicine / pharma", 2, "Major biopharma cluster — Bio Island, 4,000+ firms, ¥210B revenue.", ["Guangzhou Pharma 广药", "Bio Island"]),
            cl("Petrochemicals", 2, "Pearl-River-mouth refining (smaller than Maoming/Zhanjiang).", ["Sinopec Guangzhou", "CNOOC refinery"]),
            cl("Semiconductor (mature-node)", 1, "GZ's only significant fab — specialty analog/power/display-driver (180–55nm); revenue +53% to ¥2.58B (2025) but deeply loss-making, ChiNext IPO pending.", ["CanSemi / Yuexin 粤芯半导体"]),
        ],
        "subdistricts": [
            {"name": "Huangpu / GDD 黄埔", "focus": "Flagship advanced-mfg zone — ~40% of GZ industrial output; CanSemi fabs, GAC-Honda NEV plant, biopharma"},
            {"name": "Nansha 南沙", "focus": "Port/FTZ (20.5M TEU, world top-10); GAC-Toyota; petrochem; auto exports +68%"},
            {"name": "Panyu 番禺", "focus": "GAC Aion EV plant + R&D; XPeng (incl. Aeroht flying-car trial plant)"},
            {"name": "Huadu 花都", "focus": "Dongfeng Nissan plants + Guangzhou Auto Parts City"},
            {"name": "Zengcheng 增城", "focus": "Precision metal stamping / connector-terminal manufacturing"},
            {"name": "Tianhe 天河", "focus": "XPeng HQ campus + corporate/tech services"},
        ],
        "valuechain": "Assembly + trade-gateway + heavy-industry tier — a net CONSUMER of chips, sensors, power devices and panels (assembles them into cars), not a component originator. More SOE/JV-led than private Shenzhen (GAC, Sinopec, CNOOC, Guangzhou Pharma). Canton Fair = China's largest B2B export-matching platform.",
        "sourcing": {
            "buy": ["CanSemi mature-node wafers (180–55nm analog/power/display-driver)", "Connector terminals / precision stamping (Zengcheng)", "Display ecosystem parts (OCA / FPC / backlight)"],
            "sell": ["Automotive semis — MCU / power / ADAS / CAN-LIN for GAC's 2M+ vehicles", "EV power devices — SiC / IGBT / gate drivers for Aion & XPeng", "Display driver ICs + PMIC for CSOT T9", "BMS & AI-compute SoC / LiDAR driver for XPeng smart-EV"],
        },
        "tags": {"Components": 1, "Optical": 3, "Battery": 2, "Automotive": 3, "Precision": 2, "Materials": 1, "Appliances": 1, "Semiconductor": 1},
        "stats": [{"k": "GDP 2024", "v": "¥3.1T (China #4)"}, {"k": "Vehicles 2024", "v": "~3.18M (38% NEV)"}, {"k": "Nansha port", "v": "20.5M TEU (top-10)"}],
        "note": "AI-deep-researched (Sonnet), cross-verified — flagged: XPeng mfg split GZ+Zhaoqing; Dongfeng Nissan parent HQ'd in Wuhan; the planned Nansha ethylene cracker was relocated to Zhanjiang.",
    },
    # ---- full dossiers (AI-deep-researched, Sonnet, cross-verified) ----
    {
        "name": "Shanghai", "name_zh": "上海", "lon": 121.47, "lat": 31.23, "dom": "SEMI",
        "tagline": "China's only city with a complete vertically-integrated semiconductor stack — foundry, advanced IC design, materials & equipment — anchored by SMIC & Hua Hong in Zhangjiang; plus Tesla EV.",
        "clusters": [
            cl("Foundry / wafer fab", 3, "SMIC (HQ; record 2024 revenue ¥57.8B, +27.7%, ~5.5% global foundry share) + Hua Hong; new Lingang fab JV.", ["SMIC", "Hua Hong"]),
            cl("IC design", 3, "China's #1 IC-design city — ~¥179.5B in 2024 (~27% of national ¥668.9B); hundreds of Zhangjiang design houses.", ["Zhaoxin", "Awinic", "HiSilicon (R&D)"]),
            cl("Semi equipment & materials", 2, "Growing domestic tool/material firms in Zhangjiang & Lingang bonded zone.", ["AMEC", "NAURA (Beijing)"]),
            cl("Automotive / EV", 2, "Tesla Gigafactory Shanghai ~950k vehicles/yr (3-millionth Nov 2024); SAIC.", ["Tesla", "SAIC", "NIO"]),
        ],
        "subdistricts": [
            {"name": "Zhangjiang 张江", "focus": "IC design + SMIC/Hua Hong fabs ('China's Silicon Valley')"},
            {"name": "Lingang 临港", "focus": "New SMIC fab JV + Tesla Gigafactory; bonded-zone semi incentives"},
            {"name": "Jinqiao 金桥", "focus": "Hua Hong 8-inch fabs, electronics EMS"},
        ],
        "valuechain": "Design → fab → packaging at mature-node depth (China leader, 14-28nm); SOE/state-backed at the fab layer (SMIC), private & FDI at design and EMS.",
        "sourcing": {"buy": ["Mature-node logic ICs (28-90nm), MCUs, power & analog", "8-inch wafers", "domestic EDA licenses"], "sell": ["Semiconductor equipment", "advanced-packaging materials", "OSAT services", "PCB substrates"]},
        "tags": {"Components": 2, "Optical": 1, "Battery": 1, "Automotive": 2, "Precision": 2, "Materials": 2, "Appliances": 0, "Semiconductor": 3},
        "stats": [{"k": "SMIC 2024", "v": "¥57.8B (+27.7%)"}, {"k": "IC design 2024", "v": "¥179.5B (#1 city)"}, {"k": "GDP 2024", "v": ">¥5T"}],
        "note": "Tesla is US-HQ, Foxconn Taiwan-HQ; Hua Hong's leading 12-inch fabs are in Wuxi, not Shanghai.",
    },
    {
        "name": "Shenzhen", "name_zh": "深圳", "lon": 114.06, "lat": 22.54, "dom": "ELEC",
        "tagline": "China's hardware Silicon Valley — fabless chip design (HiSilicon), finished electronics (DJI), vertically-integrated EV (BYD) and the Huaqiangbei component market coexist; Dongguan assembles what Shenzhen designs.",
        "clusters": [
            cl("Fabless IC / AI chip design", 3, "HiSilicon designs Kirin SoCs & Ascend AI accelerators; >25,000 national hi-tech firms (12/km²).", ["HiSilicon", "Huawei"]),
            cl("Intelligent terminals / consumer electronics", 3, "Foxconn Longhua iPhone OEM (~300k workers); DJI >70% of global consumer drones.", ["DJI", "Foxconn", "BYD Electronics", "Skyworth"]),
            cl("NEV & EV supply chain", 3, "BYD 10-millionth NEV Nov 2024; Shenzhen = 22.3% of China NEV output; in-city cells + IGBT.", ["BYD", "BYD Semiconductor"]),
            cl("Software / internet / cloud", 3, "Tencent; strategic emerging industries = 42.3% of GDP; R&D 6.46% of GDP (#1 city).", ["Tencent", "ZTE", "Ping An"]),
            cl("Component spot-market", 2, "Huaqiangbei — world's largest electronics-component market; same-day BOM fulfilment.", ["Huaqiangbei (SEG)"]),
        ],
        "subdistricts": [
            {"name": "Nanshan 南山", "focus": "Tencent, DJI, Huawei HQ; hi-tech park; VC cluster"},
            {"name": "Longhua 龙华", "focus": "Foxconn iPhone final assembly"},
            {"name": "Pingshan 坪山", "focus": "BYD auto/NEV + IGBT power semiconductor"},
            {"name": "Futian 福田", "focus": "Huaqiangbei component market; finance"},
            {"name": "Guangming 光明", "focus": "Semi equipment, advanced materials, PV"},
        ],
        "valuechain": "Design + brand + integration apex of the PRD chain; overwhelmingly private (Huawei/BYD/DJI/Tencent); net exporter of IP-rich finished products.",
        "sourcing": {"buy": ["Bare-die chips (TSMC via Taiwan)", "precision molds (Dongguan)", "battery cells", "PCBs", "rare-earth magnets"], "sell": ["Smartphones, drones, NEVs, 5G base stations, AI servers, IoT — via ¥4.5T export (#1 city)"]},
        "tags": {"Components": 3, "Optical": 2, "Battery": 3, "Automotive": 3, "Precision": 2, "Materials": 1, "Appliances": 1, "Semiconductor": 3},
        "stats": [{"k": "GDP 2024", "v": "¥3.68T (+5.8%)"}, {"k": "Exports 2024", "v": "¥4.5T (#1 city)"}, {"k": "NEV share", "v": "22.3% of China"}],
        "note": "Foxconn HQ Taiwan (Shenzhen = its largest ops); HiSilicon is a Huawei subsidiary.",
    },
    {
        "name": "Beijing", "name_zh": "北京", "lon": 116.40, "lat": 39.90, "dom": "SEMI",
        "tagline": "China's semiconductor R&D + equipment capital (not a volume-fab city) — Naura (#1 domestic equipment), SMIC Beijing fab, the Zhongguancun IC-design cluster, BOE HQ, and the most-permissioned robotaxi zone.",
        "clusters": [
            cl("Semiconductor equipment", 3, "Naura — #6 globally in fab equipment (2024), revenue ¥29.8B (+35%); ~25% of China's etch/deposition WFE.", ["Naura", "Huafeng Test"]),
            cl("IC design (fabless)", 3, "Haidian IC revenue ¥43B (2024, +13%); GigaDevice = world #2 SPI NOR Flash; Cambricon AI NPUs.", ["GigaDevice", "Cambricon", "Montage"]),
            cl("Wafer fabrication", 2, "SMIC Beijing FAB4 (Yizhuang) — mature nodes ≥28nm, part of SMIC's 1.2M+ wpm network.", ["SMIC"]),
            cl("Display", 2, "BOE global HQ (management/R&D-heavy; advanced OLED production is in Chengdu/Wuhan).", ["BOE"]),
            cl("Autonomous driving / AI", 2, "Yizhuang — Baidu Apollo Go + China's first driverless robotaxi permits (>17M cumulative rides).", ["Baidu Apollo", "Horizon Robotics"]),
        ],
        "subdistricts": [
            {"name": "Haidian / Zhongguancun 海淀", "focus": "IC design, EDA, AI, university spinouts (Tsinghua, PKU, CAS)"},
            {"name": "Yizhuang / BDA 亦庄", "focus": "Naura, SMIC Beijing fab, BOE line, Baidu Apollo Park"},
        ],
        "valuechain": "Upstream R&D + equipment layer — private fabless (GigaDevice, Cambricon) + state-backed equipment (Naura) & foundry (SMIC); 'Big Fund' capital.",
        "sourcing": {"buy": ["Silicon wafers, specialty gases, photomasks, packaging substrates"], "sell": ["Fab equipment (domestic + export)", "NOR Flash chips", "AI / edge NPUs", "display panels (via BOE HQ)", "robotaxi services"]},
        "tags": {"Components": 2, "Optical": 1, "Battery": 0, "Automotive": 1, "Precision": 2, "Materials": 1, "Appliances": 0, "Semiconductor": 3},
        "stats": [{"k": "Naura 2024", "v": "¥29.8B (#6 global equip.)"}, {"k": "Haidian IC", "v": "¥43B (+13%)"}, {"k": "GigaDevice", "v": "#2 global NOR Flash"}],
        "note": "Hua Hong has NO Beijing fab (all in Shanghai). BOE's most advanced OLED is in Chengdu/Wuhan, not Beijing.",
    },
    {
        "name": "Tianjin", "name_zh": "天津", "lon": 117.20, "lat": 39.13, "dom": "AUTO",
        "tagline": "North China's port-industrial base — automobiles (FAW-Toyota), Airbus A320 final-assembly, petrochemicals and emerging EV/electronics, anchored by Tianjin Port and the Binhai New Area.",
        "clusters": [
            cl("Automobiles", 2, "FAW-Toyota + FAW heritage; growing NEV assembly in the northern auto belt.", ["FAW Toyota", "FAW"]),
            cl("Aerospace", 2, "Airbus A320 Final Assembly Line — the first outside Europe; aerospace & rocket plants.", ["Airbus Tianjin", "CASIC"]),
            cl("Petrochemicals", 2, "Large refining & chemical base (Nangang petrochemical zone).", ["Sinopec", "PetroChina"]),
            cl("Electronics / EV components", 1, "Display, EV battery/components and electronics in Binhai/TEDA (Samsung presence reduced).", []),
        ],
        "subdistricts": [
            {"name": "Binhai New Area 滨海新区", "focus": "Port, petrochem, aerospace, electronics"},
            {"name": "TEDA 经开区", "focus": "Autos, electronics, FDI manufacturing"},
        ],
        "valuechain": "Heavy-industry + assembly + port logistics; SOE-heavy (FAW, Sinopec, PetroChina) with FDI in autos/aerospace.",
        "sourcing": {"buy": ["Auto components", "petrochemical feedstock", "electronics"], "sell": ["Automotive semiconductors / EV power devices", "industrial electronics"]},
        "tags": {"Components": 1, "Optical": 0, "Battery": 1, "Automotive": 2, "Precision": 1, "Materials": 2, "Appliances": 1, "Semiconductor": 0},
        "stats": [{"k": "Role", "v": "Auto + Airbus A320 FAL + port"}, {"k": "GDP", "v": "~¥1.8T"}],
        "note": "Curated (lighter than the deep-researched cities) — Tianjin is more heavy-industry/port than electronics; flag for a deeper pass if needed.",
    },
    {
        "name": "Suzhou", "name_zh": "苏州", "lon": 120.62, "lat": 31.32, "dom": "ELEC",
        "tagline": "China's top FDI-driven electronics & advanced-components belt ('Sunan model') — Samsung, Bosch, ZEISS + thousands of Taiwanese firms in PCB, OSAT, precision components and biomedicine.",
        "clusters": [
            cl("FDI electronics & EMS", 3, "Suzhou Industrial Park GDP ¥400B (2024); city industrial output >¥4.7T; high-tech 54.7%.", ["Samsung", "Foxconn", "Luxshare", "Flex", "USI", "Bosch"]),
            cl("Semiconductor packaging / OSAT", 2, "Major OSAT cluster — Samsung Suzhou DRAM packaging + Taiwanese OSAT.", ["Samsung Semi Suzhou", "ASE"]),
            cl("PCB & electronic materials", 2, "Kunshan Taiwanese PCB makers; Dongshan Precision (top domestic PCB/precision group).", ["Dongshan Precision", "Unimicron"]),
            cl("Optical / precision instruments", 2, "ZEISS R&D+mfg site (2024); Sodick precision EDM.", ["ZEISS", "Sodick"]),
            cl("Biomedicine", 2, "BioBAY — China's leading biomedical cluster, >1,200 firms.", ["Roche", "Hengrui"]),
        ],
        "subdistricts": [
            {"name": "Suzhou Industrial Park (SIP)", "focus": "Semi, biotech, R&D — GDP ¥400B (2024)"},
            {"name": "Kunshan 昆山", "focus": "Taiwanese PCB/EMS/servers (¥100B AI-server target 2027)"},
            {"name": "Wuzhong 吴中", "focus": "Dongshan Precision; auto-electronics suppliers"},
        ],
        "valuechain": "FDI + Taiwan capital at mid-to-advanced electronics tiers; strong back-end semi + sub-assembly; SOE role limited ('Sunan model').",
        "sourcing": {"buy": ["DRAM packaging", "SMT/EMS sub-assembly", "rigid & flex PCB", "precision machined parts", "optical coatings"], "sell": ["Semiconductor capital equipment", "ABF/BT substrates", "cleanroom consumables", "automation systems"]},
        "tags": {"Components": 3, "Optical": 2, "Battery": 1, "Automotive": 2, "Precision": 2, "Materials": 2, "Appliances": 1, "Semiconductor": 2},
        "stats": [{"k": "GDP 2024", "v": "¥2,672B (+6%)"}, {"k": "High-tech output", "v": "¥2,572B (54.7%)"}, {"k": "SIP GDP", "v": "¥400B"}],
        "note": "Samsung (KR), ZEISS (DE), Foxconn (TW), ASE (TW), Unimicron (TW) are foreign/Taiwan-HQ.",
    },
    {
        "name": "Wuxi", "name_zh": "无锡", "lon": 120.30, "lat": 31.57, "dom": "SEMI",
        "tagline": "China's #1 IC packaging/test base + Hua Hong's newest 12-inch specialty foundry + SK hynix's DRAM fab + the nation's sole state-designated IoT cluster.",
        "clusters": [
            cl("IC packaging & test (OSAT)", 3, "#1 nationally; Hi-Tech District IC output >¥170B (2024); 500+ IC firms.", ["Changdian / JCET"]),
            cl("Foundry (12-inch specialty)", 3, "Hua Hong Wuxi phase-2 (40nm MCU/eNVM), targeting 83k wpm; STMicro 40nm eNVM transfer.", ["Hua Hong", "STMicroelectronics"]),
            cl("DRAM / memory", 2, "SK hynix Wuxi DRAM ~180-190k wpm, ~90% on 1a DDR5; 49.9% stake sold to Wuxi state (2024).", ["SK hynix", "WIDG"]),
            cl("IoT / sensors", 3, "China's sole national IoT advanced-mfg cluster; >3,000 IoT firms; ¥401B (2022).", ["China Mobile IoT", "CAS Wuxi"]),
        ],
        "subdistricts": [{"name": "Wuxi National Hi-Tech District (Xinwu) 新吴", "focus": "IC foundry + packaging + IoT; 500+ IC firms"}],
        "valuechain": "Full-stack semiconductor: design (light) → foundry → OSAT → IoT app layer; fab & IoT SOE-guided, packaging large-cap private (Changdian).",
        "sourcing": {"buy": ["Packaged ICs / OSAT services", "specialty 12-inch wafers (MCU/power/NVM)", "DRAM modules", "IoT sensor modules"], "sell": ["Packaging equipment & materials (wire-bond, flip-chip, WLP)", "precision leadframes", "IoT connectivity modules"]},
        "tags": {"Components": 2, "Optical": 1, "Battery": 0, "Automotive": 1, "Precision": 2, "Materials": 1, "Appliances": 0, "Semiconductor": 3},
        "stats": [{"k": "Hi-Tech IC output", "v": ">¥170B (#2 nat'l 3yr)"}, {"k": "SK hynix Wuxi", "v": "~180-190k wpm"}, {"k": "IoT (2022)", "v": "¥401B"}],
        "note": "Hua Hong HQ Shanghai (Wuxi = its largest production base); SK hynix HQ Korea (partial stake now Chinese state).",
    },
    {
        "name": "Hefei", "name_zh": "合肥", "lon": 117.23, "lat": 31.82, "dom": "SEMI",
        "tagline": "China's boldest 'state-as-VC' city — municipal bets on BOE (display), CXMT (DRAM) and NIO/VW (EV) made it a triple leader in memory, large-panel display and premium EV.",
        "clusters": [
            cl("DRAM / memory", 3, "CXMT — China's sole volume DRAM producer; ~160k wpm; ~7.7% global share; DDR5 ramping (~80% yield).", ["CXMT"]),
            cl("Large-panel display", 3, "BOE (Hefei-backed since 2008) — LCD G8.5 + WOLED.", ["BOE"]),
            cl("EV / automotive", 3, "NIO (Hefei JV) + VW Anhui (€2.5B); ~1.37M NEV in 2024 (8.3% of China's output).", ["NIO", "VW Anhui", "JAC"]),
            cl("Home appliances", 2, "Midea / Gree Hefei plants.", ["Midea", "Gree"]),
        ],
        "subdistricts": [
            {"name": "Xinzhan Hi-Tech 新站", "focus": "BOE + CXMT fabs, semiconductor cluster"},
            {"name": "Neo Park 新桥", "focus": "NIO EV manufacturing + supply-chain park"},
            {"name": "HETA 经开区", "focus": "VW Anhui; home appliances"},
        ],
        "valuechain": "State-directed at every anchor (Hefei gov holds equity in CXMT, NIO, BOE, VW Anhui) — the most interventionist municipal model; operating cos are listed/private/JV.",
        "sourcing": {"buy": ["DRAM (DDR4/5, LPDDR5X)", "large LCD/OLED panels", "EV battery packs & drivetrain"], "sell": ["DRAM & display fab equipment", "EV manufacturing automation", "semiconductor materials"]},
        "tags": {"Components": 1, "Optical": 1, "Battery": 2, "Automotive": 3, "Precision": 1, "Materials": 1, "Appliances": 2, "Semiconductor": 3},
        "stats": [{"k": "GDP 2024", "v": "¥1,350B (+6.1%)"}, {"k": "NEV 2024", "v": "1.37M (8.3% China)"}, {"k": "CXMT", "v": "~7.7% global DRAM"}],
        "note": "NIO HQ Shanghai; BOE HQ Beijing; VW HQ Germany — Hefei is the manufacturing base + major state investor.",
    },
    {
        "name": "Wuhan", "name_zh": "武汉", "lon": 114.30, "lat": 30.59, "dom": "SEMI",
        "tagline": "China's only vertically-integrated memory-plus-photonics hub — YMTC's 3D NAND anchors the world's densest fibre-optic / optoelectronics cluster ('Optics Valley').",
        "clusters": [
            cl("3D NAND flash memory", 3, "YMTC ~130k wpm (→200k+ post-Phase III); targeting ~15% global NAND share by 2026.", ["YMTC"]),
            cl("Fibre optics & cable", 3, "Optics Valley ~40% of global fibre-preform output; YOFC = global #3 fibre maker.", ["YOFC", "Fiberhome", "Accelink"]),
            cl("Display LCD / OLED", 2, "BOE + TCL CSOT fabs; CSOT t8 Gen-8.6 inkjet-printed OLED (world-first).", ["BOE", "TCL CSOT"]),
            cl("Optoelectronics & lasers", 2, ">15,000 firms; ¥600B industry (2024); fibre lasers, LiDAR, photonic chips.", ["Raycus", "Accelink"]),
        ],
        "subdistricts": [
            {"name": "East Lake Hi-Tech / Optics Valley 光谷", "focus": "Fibre, YMTC, display, laser — >¥1.2T output"},
            {"name": "WEDZ 车谷", "focus": "Automotive & EV assembly"},
        ],
        "valuechain": "Upstream-to-mid in memory (YMTC full-stack NAND) + photonics (preform → cable → device); state-backed, limited FDI post-sanctions.",
        "sourcing": {"buy": ["NAND flash (YMTC)", "optical fibre & cable", "optoelectronic modules", "display panels"], "sell": ["Storage chips to OEMs", "fibre to telecom carriers", "panels to TV/auto brands"]},
        "tags": {"Components": 2, "Optical": 3, "Battery": 0, "Automotive": 1, "Precision": 2, "Materials": 2, "Appliances": 0, "Semiconductor": 3},
        "stats": [{"k": "YMTC", "v": "~130k wpm (→200k+)"}, {"k": "Fibre preform", "v": "~40% of global"}, {"k": "Optoelectronics", "v": "¥600B (2024)"}],
        "note": "YMTC on US Entity List since 2022; BOE/CSOT are branch fabs (HQ Beijing/Shenzhen); YMTC volumes are analyst estimates.",
    },
    {
        "name": "Xi'an", "name_zh": "西安", "lon": 108.94, "lat": 34.34, "dom": "SEMI",
        "tagline": "The only Chinese city pairing Samsung's largest non-Korea NAND complex (~40% of Samsung NAND) with LONGi's world-leading solar campus and a deep aerospace-defence electronics base.",
        "clusters": [
            cl("NAND flash", 3, "Samsung Xi'an (X1+X2) = ~40% of Samsung's global NAND; ramping 236→286-layer V9.", ["Samsung"]),
            cl("Solar wafer & cell", 3, "LONGi HQ — ¥45.2B expansion toward 100GW wafer + 50GW cell capacity.", ["LONGi"]),
            cl("Aerospace & defence electronics", 2, "AVIC Xi'an Aircraft; radiation-hardened ICs for space.", ["AVIC", "Xi'an Microelectronics (CASC)"]),
            cl("Semiconductor packaging", 1, "Micron back-end (status uncertain after the 2023 CAC review).", ["Micron"]),
        ],
        "subdistricts": [
            {"name": "Xi'an ETDZ", "focus": "LONGi HQ + manufacturing"},
            {"name": "Xi'an Hi-Tech Zone", "focus": "Samsung fab complex, IC design"},
            {"name": "Chang'an / NW corridor", "focus": "AVIC, CASC defence electronics"},
        ],
        "valuechain": "Split: Samsung fab = export FDI; LONGi = private global champion; defence/aerospace = SOE with closed supply chains.",
        "sourcing": {"buy": ["NAND flash (Samsung)", "solar wafers/cells (LONGi)", "avionics/radar", "space-grade ICs"], "sell": ["NAND to global storage OEMs", "solar wafers/cells to module makers"]},
        "tags": {"Components": 2, "Optical": 1, "Battery": 2, "Automotive": 0, "Precision": 3, "Materials": 2, "Appliances": 0, "Semiconductor": 3},
        "stats": [{"k": "Samsung Xi'an", "v": "~40% of Samsung NAND"}, {"k": "LONGi expansion", "v": "¥45.2B"}, {"k": "LONGi target", "v": "100GW wafer"}],
        "note": "Samsung HQ Korea (holds a US export exemption); LONGi solar defines Xi'an though it's not classic semiconductor.",
    },
    {
        "name": "Chengdu", "name_zh": "成都", "lon": 104.07, "lat": 30.57, "dom": "ELEC",
        "tagline": "China's western EMS-plus-packaging node — Foxconn assembles MacBooks/iPads, Intel runs its China chip-packaging expansion, plus growing IC design and a top gaming hub.",
        "clusters": [
            cl("EMS — consumer electronics", 3, "Foxconn (iPads since 2010, MacBooks, Apple Watch); higher-value SKU mix.", ["Foxconn", "Pegatron", "Compal", "Jabil"]),
            cl("Semi packaging & test", 2, "Intel Chengdu $300M expansion (server-chip packaging) + customer centre.", ["Intel", "JCET"]),
            cl("IC design", 2, "China's 'fourth IC city'; AMEC ¥3.05B equipment base; automotive-chip cluster in Tianfu.", ["AMEC", "Fujitsu Semi design"]),
            cl("Gaming & software", 3, "Largest gaming hub after Shanghai/Shenzhen (Tencent/NetEase/miHoYo) — drives GPU/datacentre demand.", ["Tencent", "NetEase"]),
        ],
        "subdistricts": [
            {"name": "Chengdu Hi-Tech Zone", "focus": "Intel, Foxconn, IC design, AMEC"},
            {"name": "Tianfu New Area 天府新区", "focus": "IC-design startups, automotive chips"},
        ],
        "valuechain": "Mid-to-downstream: final assembly (Foxconn) is largest; Intel packaging adds back-end depth; IC design early-stage; FDI-heavy mfg + private IC/gaming.",
        "sourcing": {"buy": ["OSAT/packaging (Intel)", "consumer-electronics assembly (Foxconn)", "IC design", "semi equipment (AMEC)"], "sell": ["Tablets/notebooks/MacBooks", "packaged server chips"]},
        "tags": {"Components": 2, "Optical": 0, "Battery": 0, "Automotive": 1, "Precision": 2, "Materials": 0, "Appliances": 1, "Semiconductor": 2},
        "stats": [{"k": "Intel Chengdu", "v": "+$300M (server packaging)"}, {"k": "Foxconn", "v": "iPad / MacBook base"}, {"k": "AMEC base", "v": "¥3.05B"}],
        "note": "Foxconn (TW), Intel (US), Pegatron (TW) are branch ops; no confirmed UMC Chengdu fab found.",
    },
    {
        "name": "Chongqing", "name_zh": "重庆", "lon": 106.55, "lat": 29.56, "dom": "ELEC",
        "tagline": "World's largest laptop-production city (~30% of global notebooks, #1 for 11+ years), now layering NEV auto-electronics and display on its EMS base.",
        "clusters": [
            cl("Laptop / notebook EMS", 3, "~80M laptops + 100M+ smart terminals/yr; ~30% of global notebooks; HP/Dell/Lenovo/Acer/Asus.", ["Quanta", "Inventec", "Compal", "Foxconn", "Wistron"]),
            cl("NEV & automotive electronics", 3, "2.54M vehicles (2024), 953k NEV (+90.5%); #3 in China.", ["Changan", "AVATR", "Seres"]),
            cl("Semiconductor packaging", 2, "SK hynix Chongqing back-end packaging plant.", ["SK hynix"]),
            cl("Display", 2, "BOE line; part of the Chengdu-Chongqing display corridor.", ["BOE"]),
        ],
        "subdistricts": [
            {"name": "Xiyong Bonded Zone 西永", "focus": "Laptop ODMs + Chongqing-Europe rail freight"},
            {"name": "Liangjiang New Area 两江", "focus": "Changan auto, NEV, advanced mfg"},
        ],
        "valuechain": "Final-assembly + packaging (FDI Taiwanese ODMs for laptops, Korean back-end for memory); auto shifting toward a domestic chain; rail-logistics edge.",
        "sourcing": {"buy": ["Notebooks (Quanta/Inventec)", "NEVs (Changan/AVATR/Seres)", "DRAM/NAND packaging", "display panels"], "sell": ["Laptops to OEM brands", "NEVs", "packaged memory chips"]},
        "tags": {"Components": 2, "Optical": 0, "Battery": 1, "Automotive": 3, "Precision": 1, "Materials": 0, "Appliances": 1, "Semiconductor": 2},
        "stats": [{"k": "Laptops", "v": "~30% global (#1 11yr)"}, {"k": "NEV 2024", "v": "953k (+90.5%)"}, {"k": "GDP 2024", "v": "¥3.22T"}],
        "note": "Quanta/Inventec/Foxconn (TW), SK hynix (KR) are branch ops; HP/Dell are brand clients, not manufacturers.",
    },
    {
        "name": "Dongguan", "name_zh": "东莞", "lon": 113.75, "lat": 23.02, "dom": "ELEC",
        "tagline": "The PRD's mass-production backbone — ~32 specialized towns; Chang'an outputs ~195 phones/minute and the city makes ~1 in 5 of the world's mobile phones; competes on tooling speed + supplier density, not brands or chip IP.",
        "clusters": [
            cl("Smartphone / consumer OEM-ODM", 3, "Chang'an electronics output ¥232.6B (2024); ~1/5 of world phones since 1995.", ["OPPO", "vivo (BBK)", "Luxshare", "Huaqin"]),
            cl("PCB & PCBA", 2, "One of China's 3 biggest PCB hubs (Houjie/Hengli/Dalang); linked to Shenzhen design houses.", ["Kinwong", "Agilian"]),
            cl("Battery packs", 2, "Cell-to-pack for phones/TWS/power tools (cells from Shenzhen/Huizhou).", ["BYD", "EVE"]),
            cl("Precision stamping & molds", 3, "Chang'an/Houjie mold cluster (~¥50B); molds exported globally.", ["SME tool-and-die"]),
        ],
        "subdistricts": [
            {"name": "Chang'an 长安", "focus": "Smartphone OEM/ODM + molds — GDP >¥105B"},
            {"name": "Houjie 厚街", "focus": "PCB sub-cluster (+ furniture)"},
            {"name": "Liaobu 寮步", "focus": "Battery-pack assembly, precision hardware"},
        ],
        "valuechain": "Classic Tier-1/2 OEM — converts Shenzhen designs/components into finished assemblies; private SME-heavy, thin margins, diversifying to smart-manufacturing.",
        "sourcing": {"buy": ["ICs/modules (Huaqiangbei/import)", "bare PCBs", "battery cells", "stampings", "displays"], "sell": ["Assembled phones, TWS, power-tool packs, PCBA — to Shenzhen brands / export"]},
        "tags": {"Components": 3, "Optical": 1, "Battery": 2, "Automotive": 1, "Precision": 3, "Materials": 1, "Appliances": 1, "Semiconductor": 0},
        "stats": [{"k": "GDP 2024", "v": "¥1,228B (+4.6%)"}, {"k": "Chang'an electronics", "v": "¥232.6B"}, {"k": "Output", "v": "~195 phones/min"}],
        "note": "OPPO/vivo are anchored in Chang'an (BBK group); the '1/5 of world phones' figure is order-of-magnitude.",
    },
    {
        "name": "Foshan", "name_zh": "佛山", "lon": 113.12, "lat": 23.02, "dom": "APPL",
        "tagline": "The PRD's appliance + industrial-materials heartland — Shunde houses Midea (appliances + KUKA robotics) and Galanz, the largest white-goods concentration on earth; Foshan makes what goes inside homes.",
        "clusters": [
            cl("Home appliances / white goods", 3, "Shunde output ~¥370B; 25% of global rice cookers, 48% of microwaves; Midea revenue ¥409B (2024).", ["Midea", "Galanz"]),
            cl("Industrial robotics", 3, "Midea-KUKA Shunde park — China's largest industrial-robot base (>80,000 delivered).", ["KUKA", "Midea Robotics"]),
            cl("Ceramic tiles", 3, "~54% of China / ~25% of world output; 350+ makers, ~1.2B m²/yr.", ["Dongpeng / Marco Polo"]),
            cl("Aluminum profiles", 2, "Nanhai — China's leading architectural aluminum-extrusion hub.", ["NAPA members"]),
        ],
        "subdistricts": [
            {"name": "Shunde 顺德", "focus": "Appliances — Midea/Galanz/KUKA"},
            {"name": "Chancheng 禅城", "focus": "Ceramic tiles"},
            {"name": "Nanhai 南海", "focus": "Aluminum extrusions, furniture hardware"},
        ],
        "valuechain": "Mid-to-finished consumer durables + construction materials; heavily private (Midea/Galanz); Midea vertically integrated (makes own compressors/motors/chips).",
        "sourcing": {"buy": ["Steel & compressor parts", "copper wire", "aluminum ingot", "rare-earth motors", "MCU/SoC for smart appliances (via Shenzhen)"], "sell": ["Air-con/washers/rice cookers/microwaves", "industrial robots", "ceramic tiles", "aluminum profiles"]},
        "tags": {"Components": 1, "Optical": 0, "Battery": 0, "Automotive": 1, "Precision": 2, "Materials": 3, "Appliances": 3, "Semiconductor": 0},
        "stats": [{"k": "Midea 2024", "v": "¥409B revenue"}, {"k": "Ceramics", "v": "54% China / 25% world"}, {"k": "KUKA", "v": ">80,000 robots"}],
        "note": "KUKA HQ Germany (Shunde = mfg base); Hisense HQ Qingdao (has Foshan plants, not Foshan-HQ).",
    },
    {
        "name": "Ningde", "name_zh": "宁德", "lon": 119.52, "lat": 26.66, "dom": "BAT",
        "tagline": "The world's most concentrated single-city battery ecosystem — a purpose-built battery capital around CATL where upstream materials, cell production and recycling co-locate; >¥300B output.",
        "clusters": [
            cl("Battery cells (power + storage)", 3, "CATL HQ — world #1 EV battery 9 years running, 39.2% global share (2025); 661 GWh sold.", ["CATL"]),
            cl("Battery supply chain", 3, ">90 upstream/downstream firms; >60% local materials (cathode/anode/separator/electrolyte).", ["Xiamen Tungsten New Energy", "Shanshan Energy"]),
            cl("Energy storage", 2, "CATL ESS shipments 36 GWh in Q3 2025; Tener / Shenxing cells.", ["CATL ESS"]),
            cl("Battery recycling", 2, "BRUNP (CATL) recycles end-of-life cells into precursors.", ["BRUNP"]),
        ],
        "subdistricts": [
            {"name": "Jiaocheng 蕉城", "focus": "CATL main campus + HQ, gigafactories"},
            {"name": "Dongqiao Industrial Zone", "focus": "Battery supply-chain & materials"},
        ],
        "valuechain": "Almost entirely private (CATL, Zeng Yuqun-controlled); cell + materials manufacturing; sells cells to global OEMs; very little SOE presence.",
        "sourcing": {"buy": ["Lithium, cobalt, nickel", "graphite anode", "PVDF binder", "electrolyte solvents"], "sell": ["EV power cells/packs (NMC/LFP/Kirin)", "grid ESS systems", "recycled precursor materials"]},
        "tags": {"Components": 1, "Optical": 0, "Battery": 3, "Automotive": 1, "Precision": 1, "Materials": 2, "Appliances": 0, "Semiconductor": 0},
        "stats": [{"k": "Cluster output 2025", "v": "¥300B+"}, {"k": "CATL 2025", "v": "¥423.7B rev / ¥72.2B profit"}, {"k": "Share", "v": "39.2% global, #1 9yr"}],
        "note": "CATL also has fabs in Liyang/Qingdao/Yichun etc.; the '330 GWh' figure is group-wide, not Ningde-only.",
    },
    {
        "name": "Changzhou", "name_zh": "常州", "lon": 119.97, "lat": 31.79, "dom": "BAT",
        "tagline": "The most complete EV new-energy supply chain of any city outside Shenzhen — CATL, SVOLT, CALB (cells), Li Auto (assembly) and Trina Solar (PV) all manufacture here.",
        "clusters": [
            cl("Battery cell manufacturing", 3, "Three makers in parallel — CATL Liyang, SVOLT (HQ Jintan), CALB (HQ Changzhou); Jintan alone 108.5 GWh (~20% of China).", ["CATL", "SVOLT", "CALB"]),
            cl("EV assembly", 3, "Li Auto main plant (Wujin); city NEV output 678k (2023) → 800k+ (2024).", ["Li Auto"]),
            cl("Solar PV", 3, "Trina Solar HQ — top-5 module maker; 2024 revenue $11.27B; H1 2024 34GW shipped.", ["Trina Solar"]),
            cl("EV supply-chain components", 2, "Deep Tier-1/2 — electrolyte, thermal, BMS, power electronics; new-energy output ¥768B (2023).", ["ArcelorMittal Changzhou"]),
        ],
        "subdistricts": [
            {"name": "Jintan 金坛", "focus": "SVOLT HQ — largest Jiangsu battery base"},
            {"name": "Liyang 溧阳", "focus": "CATL + CALB cells; battery materials"},
            {"name": "Wujin 武进", "focus": "Li Auto EV assembly"},
            {"name": "Xinbei 新北", "focus": "Trina Solar HQ; PV module production"},
        ],
        "valuechain": "Mixed SOE/private; mid-stream cell manufacturing + finished assembly; sources materials regionally, exports via the Yangtze River Delta.",
        "sourcing": {"buy": ["LFP/NMC cathode", "anode graphite", "copper foil, Al casing", "silicon wafers, EVA/backsheet"], "sell": ["EV cells/packs", "EVs / EREVs (Li Auto)", "PV modules (100+ countries)", "ESS systems"]},
        "tags": {"Components": 2, "Optical": 1, "Battery": 3, "Automotive": 3, "Precision": 1, "Materials": 1, "Appliances": 0, "Semiconductor": 0},
        "stats": [{"k": "New-energy output", "v": "¥768B (2023, →¥1T)"}, {"k": "EV 2024", "v": "800k+ units"}, {"k": "Trina 2024", "v": "$11.27B"}],
        "note": "Li Auto HQ Beijing (mfg in Changzhou); CALB relocated from Luoyang (2015); CATL HQ Ningde.",
    },
]


def _attach_series():
    """Attach time-series to each headline KPI: real World Bank China series where available, else curated."""
    md = json.loads((WEB / "macro-data.json").read_text(encoding="utf-8"))
    chn = md["worldbank"]["CHN"]["series"]
    def ser(code, scale, nd):
        return [[p["date"], round(p["value"] * scale, nd)] for p in chn[code]["points"] if p.get("value") is not None]
    sid = {
        # GDP shown as REAL growth % (the meaningful signal), not the raw $ level
        "gdp": [[str(y), v] for y, v in zip(range(2016, 2025), [6.8, 6.9, 6.7, 6.0, 2.2, 8.4, 3.0, 5.2, 5.0])],
        "cpi": ser("FP.CPI.TOTL.ZG", 1.0, 1),      # %
        "htx": ser("TX.VAL.TECH.CD", 1e-9, 0),     # $B level -> JS computes YoY%
        # curated (no clean free series): [year, value]
        "pmi": [[str(y), v] for y, v in zip(range(2018, 2027), [50.2, 49.7, 51.2, 50.9, 49.0, 50.8, 50.1, 50.3, 50.4])],
        "auto": [[str(y), v] for y, v in zip(range(2018, 2025), [27.8, 25.7, 25.2, 26.1, 27.0, 30.2, 31.3])],
    }
    for it in CHINA_MACRO["headline"]:
        if it.get("sid") in sid:
            it["series"] = sid[it["sid"]]


def main():
    # Real, dated macro from scripts/fetch_china_macro.py (World Bank + DBnomics + FRED cache).
    cm_path = WEB / "china-macro.json"
    if cm_path.exists():
        cm = json.loads(cm_path.read_text(encoding="utf-8"))
        CHINA_MACRO["headline"] = cm["headline"]
        CHINA_MACRO["more"] = cm["more"]
    else:
        _attach_series()  # fallback to curated if the real pull hasn't run
    # Simplified-Chinese dossier translations (Sonnet) merged onto each city as c["zh"].
    zhf = ROOT / "data" / "china_cities_zh.json"
    if zhf.exists():
        zmap = json.loads(zhf.read_text(encoding="utf-8"))
        for c in CITIES:
            if c["name"] in zmap:
                c["zh"] = zmap[c["name"]]
    # US-restriction flags for anchor companies (Sonnet-researched), keyed by a match substring.
    sf = ROOT / "data" / "sanctions.json"
    sanctions = json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else []
    # Simplified-Chinese display labels for anchor companies (Sonnet-translated), keyed by the exact anchor string.
    cf = ROOT / "data" / "company_zh.json"
    company_zh = json.loads(cf.read_text(encoding="utf-8")).get("map", {}) if cf.exists() else {}
    # HQ origin (China-based vs non-China-based, by headquarters), keyed by the exact anchor string.
    of = ROOT / "data" / "origins.json"
    origins = json.loads(of.read_text(encoding="utf-8")).get("map", {}) if of.exists() else {}
    geo = json.loads((WEB / "vendor" / "china.geo.json").read_text(encoding="utf-8"))
    out = {"as_of": None, "domains": DOMAINS, "taxonomy": TAX, "glossary": GLOSSARY, "glossary_zh": GLOSSARY_ZH,
           "provinces": PROVINCES, "layers": LAYERS, "sanctions": sanctions, "company_zh": company_zh,
           "origins": origins, "macro": CHINA_MACRO, "cities": CITIES, "geo": geo}
    blob = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    (WEB / "china-bundle.js").write_text("window.CHINA = " + blob + ";\n", encoding="utf-8")
    print(f"wrote web/china-bundle.js ({len(blob)/1024:.0f} KB) — {len(CITIES)} cities, {len(geo['features'])} provinces, {len(PROVINCES)} prov-stats, {len(GLOSSARY)} glossary")


if __name__ == "__main__":
    main()
