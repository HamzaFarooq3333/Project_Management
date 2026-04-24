import re
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app


def main():
    base = Path(__file__).resolve().parents[1]
    no_emb_file = base / 'no_data' / 'no_embedding.txt'
    resp_emb_dir = base / 'information' / 'response_with_embeddings'

    codes_no = []
    if no_emb_file.exists():
        txt = no_emb_file.read_text(encoding='utf-8', errors='ignore')
        codes_no = re.findall(r"\[(\d{5})\]", txt)
        # dedupe, keep order
        seen = set()
        codes_no = [c for c in codes_no if not (c in seen or seen.add(c))][:10]

    codes_yes = []
    if resp_emb_dir.exists():
        for p in sorted(resp_emb_dir.glob('*.txt')):
            code = p.stem
            if re.fullmatch(r"\d{5}", code):
                codes_yes.append(code)
            if len(codes_yes) >= 3:
                break

    client = TestClient(app)

    results = []
    for code in codes_no:
        r = client.get(f"/api/process-by-id?code={code}")
        data = r.json()
        ok = r.status_code == 200 and 'text' in data and data.get('source') == 'response'
        results.append((code, ok, data.get('source'), len(data.get('text',''))))

    for code in codes_yes:
        r = client.get(f"/api/process-by-id?code={code}")
        data = r.json()
        ok = r.status_code == 200 and 'text' in data and data.get('source') == 'response_with_embeddings'
        has_refs = data.get('references') is not None
        results.append((code, ok and has_refs, data.get('source'), len(data.get('text',''))))

    for code, ok, src, n in results:
        print(f"{code}: {'OK' if ok else 'FAIL'} [{src}] ({n} chars)")


if __name__ == '__main__':
    main()


