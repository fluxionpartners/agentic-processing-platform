# Solution Overview

This repository implements the enterprise-grade Microsoft Foundry Tax Intelligence Platform as a modular service pipeline.

## Pipeline services

- `src/services/w2-intake` - Secure W-2 upload intake service.
- `src/services/document-extraction` - Document extraction service for parsed W-2 data.
- `src/services/data-validation` - Validation service for extracted tax data and compliance rules.
- `src/services/tax-mapping` - Tax mapping and 1040 payload generation service.
- `src/services/audit-monitoring` - Audit, monitoring, and governance service.

## Architecture

Each service has:
- a service implementation folder under `src/services`
- Azure infrastructure templates under `infrastructure/services/<service>/bicep`
- deployment scripts under `scripts/services/<service>`

The platform is designed for:
- secure intake and storage
- decoupled processing with event-driven workflows
- validation and review
- downstream tax intelligence and compliance

## Next steps

1. Confirm the service layout and deployment scaffolding.
2. Implement the intake service end to end.
3. Add extraction and validation workflows.
4. Wire tax mapping and governance services.
