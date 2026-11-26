from __future__ import annotations

from app import run_test_suite


for target in ("python", "javascript"):
    result = run_test_suite(target)
    print(f"{target}: {result['passed']}/{result['total']} casos correctos")
    if result["failed"]:
        for case in result["cases"]:
            if not case["passed"]:
                print(f"  - Programa {case['program']} caso {case['case']}: {case['detail']}")
