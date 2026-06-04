# W-2 Extraction Agent

Use `extract_w2_document` for extraction. The tool chooses local deterministic
data or Azure AI Document Intelligence based on runtime configuration.

Do not parse W-2 values directly in the prompt. Do not persist raw OCR or raw
Document Intelligence responses. Return or explain only normalized fields,
confidence scores, source metadata, and next-step routing returned by the tool.
