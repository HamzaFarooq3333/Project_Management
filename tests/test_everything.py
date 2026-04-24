# tests/test_everything.py
# ... existing code ...
import os
import sys
import requests
from typing import Callable, Tuple, List

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
TIMEOUT_SECONDS = 120


def run_no_timeout(fn: Callable[[], Tuple[str, bool, str]]) -> Tuple[str, bool, str]:
    try:
        return fn()
    except Exception as e:
        return (fn.__name__, False, str(e))


def ensure_server() -> bool:
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# Individual feature tests

def test_search() -> Tuple[str, bool, str]:
    r = requests.get(f"{BASE_URL}/api/search?q=risk")
    ok = (r.status_code == 200 and "results" in r.json())
    return ("search", ok, "")


def test_compare() -> Tuple[str, bool, str]:
    r = requests.get(f"{BASE_URL}/api/compare?topic=stakeholder")
    j = r.json() if r.status_code == 200 else {}
    ok = (r.status_code == 200 and "insights" in j)
    return ("compare", ok, "")


def test_analysis() -> Tuple[str, bool, str]:
    r = requests.get(f"{BASE_URL}/api/analysis")
    j = r.json() if r.status_code == 200 else {}
    ok = (r.status_code == 200 and "points" in j)
    return ("analysis", ok, "")


def test_graphs() -> Tuple[str, bool, str]:
    r = requests.get(f"{BASE_URL}/api/graphs?topic=planning")
    ok = (r.status_code == 200)
    return ("graphs", ok, "")


def test_process_ai() -> Tuple[str, bool, str]:
    params = {
        "project_type": "software",
        "project_size": "small",
        "industry": "IT",
        "methodology_preference": "any",
        "use_ai": "true",
    }
    r = requests.get(f"{BASE_URL}/api/process-recommendation", params=params)
    if r.status_code != 200:
        return ("process_ai", False, f"HTTP {r.status_code}")
    j = r.json()
    ok = ("recommendations" in j and (j.get("mode") in ["ai_generated", "template_based"]))
    return ("process_ai", ok, "")


def test_pdf_export() -> Tuple[str, bool, str]:
    payload = {
        "project_type": "software",
        "project_size": "small",
        "industry": "IT",
        "methodology_preference": "any",
        "scenario_description": "Test",
        "process_text": "1. Start\n- Do X",
        "citations_json": "[]",
        "ai_model_answer": "",
        "evidence_base": "{}",
    }
    r = requests.get(f"{BASE_URL}/api/export-pdf", params=payload)
    ok = (r.status_code == 200 and r.headers.get("content-type") == "application/pdf")
    return ("export_pdf", ok, "")


def main():
    if not ensure_server():
        print("Server is not running. Start it before running tests.")
        sys.exit(1)

    tests: List[Callable[[], Tuple[str, bool, str]]] = [
        test_search,
        test_compare,
        test_analysis,
        test_graphs,
        test_process_ai,
        test_pdf_export,
    ]

    results: List[Tuple[str, bool, str]] = []
    for t in tests:
        name, ok, err = run_no_timeout(t)
        results.append((name, ok, err))
        status = "PASSED" if ok else f"FAILED ({err})"
        print(f"{name}: {status}")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\nSummary: {passed}/{total} passed")
    if passed != total:
        print("Failures:")
        for name, ok, err in results:
            if not ok:
                print(f"- {name}: {err}")


if __name__ == "__main__":
    main()
