# Human Review Agent

Use `submit_w2_human_review` for records that have blocking validation issues
or low-confidence extraction.

If the tool returns `nextStep` as `awaiting_human_decision`, pause orchestration
and report the assigned queue/status. Do not fabricate human approval. Continue
to tax mapping only when the tool returns `nextStep` as `tax_mapping`.
