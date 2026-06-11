"""Debug script to identify circular reference and test failures."""
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from foundry_agents.pipeline import AgentPipeline

pipeline = AgentPipeline()
trigger = {
    "correlationId": "debug-001",
    "tenantId": "tenant-001",
    "taxpayerId": "taxpayer-12345",
    "documentName": "W2_2024_sample.pdf",
    "blobUri": "https://example/w2.pdf",
    "taxYear": 2024,
}

result = pipeline.run(trigger)

print("=== TOP LEVEL ===")
print("status:", result.get("status"))
print("keys:", sorted(result.keys()))

payload = result.get("payload", {})
print("\n=== PAYLOAD ===")
print("payload.status:", payload.get("status"))
print("payload keys:", sorted(payload.keys()))
print("Has execution_log:", "execution_log" in payload)

el = payload.get("execution_log", [])
print("\n=== EXECUTION LOG ===")
for i, entry in enumerate(el):
    stage = entry.get("stage", "?")
    r = entry.get("result", {})
    has_payload = "payload" in r
    print(f"  [{i}] {stage}: result has 'payload'={has_payload}")
    if has_payload:
        p2 = r["payload"]
        print(f"       payload has 'execution_log': {'execution_log' in p2}")

# Check if the finalize entry creates the circle
if el:
    last = el[-1]
    if "payload" in last.get("result", {}):
        finalize_payload = last["result"]["payload"]
        finalize_el = finalize_payload.get("execution_log", [])
        print(f"\n  CIRCULAR: finalize->result->payload->execution_log is same object as outer: {finalize_el is el}")
