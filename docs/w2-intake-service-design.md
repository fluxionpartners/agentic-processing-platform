# W-2 Intake Service Design

This document captures the current secure upload service design for the W-2 intake flow.

## Objective
Provide a clean, enterprise-grade intake service that accepts W-2 documents, stores them securely, and emits ingestion events for downstream processing.

## Design
- The intake service is a standard web/API service, not an autonomous agent.
- It receives validated file uploads, stores documents in Azure Blob Storage, and publishes events to Service Bus.
- Downstream processing can later be implemented as separate services or orchestrated workflows.

## Current Scope
- Secure W-2 upload endpoint
- Blob storage of raw content
- Event emission for document ingestion
- Monitoring and telemetry

## Notes
- This service is intentionally simple and service-oriented.
- Future enhancements can include document extraction, validation, and AI orchestration, but those are separate capabilities.
