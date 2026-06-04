"""Document Extraction service placeholder."""

from typing import Any, Dict


def extract_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structured tax data from a W-2 document payload."""
    return {
        "status": "not_implemented",
        "message": "Document extraction logic will be implemented here.",
        "input": payload,
    }


if __name__ == "__main__":
    print("Document Extraction Service placeholder. Implement extraction logic here.")
