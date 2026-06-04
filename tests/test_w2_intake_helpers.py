import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "services" / "w2-intake" / "w2_intake_app.py"
)
spec = importlib.util.spec_from_file_location("w2_intake_app", MODULE_PATH)
w2_intake_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w2_intake_app)


class W2IntakeHelperTests(unittest.TestCase):
    def test_validate_payload_reports_missing_fields(self):
        error = w2_intake_app.validate_payload({"tenantId": "tenant-001"})

        self.assertEqual(error, "Missing required fields: taxpayerId, documentName, documentBase64")

    def test_build_blob_name_sanitizes_document_name(self):
        blob_name = w2_intake_app.build_blob_name(
            {
                "tenantId": "tenant-001",
                "taxpayerId": "taxpayer-123",
                "taxYear": 2024,
                "documentName": "folder\\W2 sample.pdf",
            }
        )

        self.assertTrue(blob_name.startswith("tenant-001/taxpayer-123/2024/"))
        self.assertTrue(blob_name.endswith("_folder_W2_sample.pdf"))


if __name__ == "__main__":
    unittest.main()
