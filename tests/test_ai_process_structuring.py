#!/usr/bin/env python3
"""
AI Process Structuring & Citations Tests
=======================================

Validates that /api/process-recommendation returns structured phases/activities,
per-step citations, and that PDF export works with citations payload.
"""

import os
import requests

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")


def require_server():
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        assert r.status_code == 200
    except Exception as e:
        raise SystemExit("Server not running. Start the app before tests.")


def test_ai_process_structuring_and_citations():
    require_server()
    params = {
        "project_type": "software",
        "project_size": "small",
        "industry": "IT",
        "methodology_preference": "any",
        "use_ai": "true",
    }
    r = requests.get(f"{BASE_URL}/api/process-recommendation", params=params, timeout=60)
    assert r.status_code == 200
    data = r.json()

    # Accept both ai_generated or template fallback but prefer AI
    if data.get("mode") == "ai_generated":
        ai = data.get("ai_recommendation", {})
        assert isinstance(ai.get("process", ""), str) and len(ai["process"]) > 0
        assert isinstance(ai.get("citations", []), list)
        # Structured
        assert "structured" in ai and isinstance(ai["structured"].get("phases", []), list)
        # Step citations map can be empty but must exist
        assert "step_citations" in ai
    else:
        # Fallback still returns recommendations and tailored_approach
        assert "recommendations" in data and "tailored_approach" in data


def test_pdf_export_with_citations():
    require_server()
    # Minimal export with dummy citations list
    payload = {
        "project_type": "software",
        "project_size": "small",
        "industry": "IT",
        "methodology_preference": "any",
        "scenario_description": "Test scenario",
        "process_text": "1. Initiation\n- Define scope",
        "citations_json": "[{\"standard\":\"PMBOK\",\"page\":1,\"excerpt\":\"Project Charter\"}]",
        "ai_model_answer": "",
        "evidence_base": "{}",
    }
    r = requests.get(f"{BASE_URL}/api/export-pdf", params=payload, timeout=60)
    assert r.status_code == 200
    assert r.headers.get("content-type") == "application/pdf"


if __name__ == "__main__":
    test_ai_process_structuring_and_citations()
    test_pdf_export_with_citations()
    print("✅ AI process structuring & PDF export tests passed")


