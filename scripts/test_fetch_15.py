import re
import random
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app


def collect_codes(base: Path, want_no: int = 12, want_yes: int = 3):
    no_file = base / 'no_data' / 'no_embedding.txt'
    emb_dir = base / 'information' / 'response_with_embeddings'

    no_codes = []
    if no_file.exists():
        txt = no_file.read_text(encoding='utf-8', errors='ignore')
        no_codes = re.findall(r"\[(\d{5})\]", txt)
        # dedupe keep order
        seen = set()
        no_codes = [c for c in no_codes if not (c in seen or seen.add(c))]

    yes_codes = []
    if emb_dir.exists():
        for p in sorted(emb_dir.glob('*.txt')):
            code = p.stem
            if re.fullmatch(r"\d{5}", code):
                yes_codes.append(code)

    # sample desired counts (fallback if not enough)
    no_pick = no_codes[:want_no] if len(no_codes) >= want_no else no_codes
    yes_pick = yes_codes[:want_yes] if len(yes_codes) >= want_yes else yes_codes
    return no_pick, yes_pick


def main():
    base = Path(__file__).resolve().parents[1]
    no_pick, yes_pick = collect_codes(base)
    client = TestClient(app)

    tests = []
    # interleave to simulate mixed requests
    for i in range(max(len(no_pick), len(yes_pick))):
        if i < len(no_pick):
            tests.append(no_pick[i])
        if i < len(yes_pick):
            tests.append(yes_pick[i])

    # limit to 15
    tests = tests[:15]
    if not tests:
        print('No test codes found.')
        return

    successes = 0
    for idx, code in enumerate(tests, 1):
        r = client.get(f"/api/process-by-id?code={code}")
        ok = (r.status_code == 200) and ('text' in r.json())
        src = r.json().get('source') if r.status_code == 200 else 'error'
        n = len(r.json().get('text', '')) if r.status_code == 200 else 0
        print(f"{idx:02d}. {code}: {'OK' if ok else 'FAIL'} [{src}] ({n} chars)")
        if ok:
            successes += 1

    print(f"\nSummary: {successes}/{len(tests)} passed")


if __name__ == '__main__':
    main()


