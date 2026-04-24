from fastapi.testclient import TestClient
from app.main import app


def main():
    client = TestClient(app)
    r = client.get('/')
    assert r.status_code == 200, 'Root page failed to load'
    html = r.text
    ok_btn = 'id="fetchProcessByCodeBtn"' in html
    ok_proc = 'id="processResults"' in html and 'id="processRecommendations"' in html
    print(f"Root contains fetch button: {'OK' if ok_btn else 'FAIL'}")
    print(f"Root contains process containers: {'OK' if ok_proc else 'FAIL'}")

    # Sanity check: API responds
    r2 = client.get('/api/process-by-id?code=11111')
    ok_api = (r2.status_code == 200) and ('text' in r2.json())
    print(f"API /api/process-by-id (11111): {'OK' if ok_api else 'FAIL'}")


if __name__ == '__main__':
    main()


