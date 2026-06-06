r"""Verify the LLM-output JSON parser handles fenced / prose-wrapped responses."""
from emi.ingest.guidance_llm import _parse

samples = [
    '```json\n{"period":"Q2 FY2027","currency":"USD","revenue":{"mid":91000000000,"low":89180000000,"high":92820000000},"gross_margin":{"mid":0.749}}\n```',
    'Here is the guidance: {"period":null,"currency":"USD","revenue":{"mid":5200000000,"low":5000000000,"high":5400000000},"gross_margin":{"mid":null}} (from the release).',
    'No numeric guidance was provided.',
]
for s in samples:
    print(_parse(s))
