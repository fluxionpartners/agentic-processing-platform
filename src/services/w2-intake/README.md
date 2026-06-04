# W-2 Intake Service

This service builds the foundational Azure environment and the secure W-2 intake pipeline.

## Objective
Deploy a minimal secure W-2 intake service that supports:
- authenticated W-2 upload
- raw document storage
- ingestion event emission

## Scope
- Azure Storage
- API Management
- Azure Functions (intake)
- Event Grid / Service Bus
- Key Vault
- Basic monitoring
- Foundation for future extraction and analytics workflows

## Tasks
1. Define environment naming and tagging standards.
2. Create Bicep templates for core resources.
3. Build a Python Azure Function for secure W-2 upload.
4. Store uploaded documents in Azure Storage.
5. Emit ingestion events to Service Bus.
6. Build the secure upload service and event emission pipeline.
7. Validate end-to-end flow with a sample W-2.

## Deployment Instructions
- Deploy infrastructure: `scripts/services/w2-intake/deploy.ps1`
- Deploy function code: `scripts/services/w2-intake/deploy-function.ps1`

## Next Steps
After this intake deployment is validated, move to the next extraction and storage workflow.
