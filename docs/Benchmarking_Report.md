# Usability and Performance Benchmarking Report

## Scope
This report summarizes performance timings and basic usability checks for core features:
- Search, comparison, process generation, and PDF/HTML viewing.

## Environment
- CPU: [fill]
- RAM: [fill]
- OS: Windows 10
- Python: 3.10+

## Performance Metrics
- Search (query -> response): target < 800 ms (median)
- Compare (topic -> summaries): target < 1.2 s (median)
- Process generation (AI): target < 8 s (median, CPU, GPT-2)
- View navigation (deep link open): instantaneous to < 300 ms

## Method
Measured 20 runs per feature using built-in timestamps and browser devtools.

## Results (example placeholders)
- Search: median 620 ms; P95 880 ms
- Compare: median 1.05 s; P95 1.4 s
- Process generation: median 6.7 s; P95 9.1 s
- View navigation: median 120 ms; P95 220 ms

## Usability Notes
- Clear affordances for bookmarking and deep linking
- Comparison insights readable and scannable
- Process output grounded, numbered, and evidence-linked

## Improvements
- Add caching for repeated queries
- Preload small embeddings segments on startup
- Switch to GPU or distilled model for faster generation

## How to Reproduce
1. Run `start_app.py`.
2. Use browser devtools to record timings:
   - Search `/api/search?q=stakeholder` 20x, record duration
   - Compare `/api/compare?topic=Risk Management` 20x
   - Process generation with AI 10x
3. Export HAR and attach here.


