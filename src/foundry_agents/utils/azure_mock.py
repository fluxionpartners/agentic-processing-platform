"""Mock Azure AI Projects SDK classes for offline testing and local simulation."""

from uuid import uuid4


class MockRun:
    def __init__(self, run_id: str, thread_id: str, assistant_id: str):
        self.id = run_id
        self.thread_id = thread_id
        self.assistant_id = assistant_id
        self.status = "completed"

class MockThread:
    def __init__(self, thread_id: str):
        self.id = thread_id

class MockText:
    def __init__(self, value: str):
        self.value = value

class MockContent:
    def __init__(self, text_val: str):
        self.text = MockText(text_val)

class MockMessage:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = [MockContent(content)]

class MockAgent:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name

class MockAgentList:
    def __init__(self, data: list):
        self.data = data

class MockMessageList:
    def __init__(self, data: list):
        self.data = data

class MockAgentsOperations:
    # Class-level stores shared across all instances to simulate
    # real Azure service persistence across client instantiations.
    _shared_threads = {}
    _shared_runs = {}

    def __init__(self):
        self._runs = MockAgentsOperations._shared_runs
        self._threads = MockAgentsOperations._shared_threads

    def create_thread(self, *args, **kwargs) -> MockThread:
        thread_id = f"mock-thread-{uuid4()}"
        MockAgentsOperations._shared_threads[thread_id] = []
        return MockThread(thread_id)

    def create_message(self, thread_id: str, role: str, content: str, *args, **kwargs) -> MockMessage:
        if thread_id not in MockAgentsOperations._shared_threads:
            MockAgentsOperations._shared_threads[thread_id] = []
        msg = MockMessage(role, content)
        MockAgentsOperations._shared_threads[thread_id].append(msg)
        return msg

    def list_messages(self, thread_id: str, *args, **kwargs) -> MockMessageList:
        msgs = MockAgentsOperations._shared_threads.get(thread_id, [])
        return MockMessageList(list(reversed(msgs)))

    def create_run(self, thread_id: str, assistant_id: str, *args, **kwargs) -> MockRun:
        run_id = f"mock-run-{uuid4()}"
        run = MockRun(run_id, thread_id, assistant_id)
        MockAgentsOperations._shared_runs[run_id] = run
        return run

    def get_run(self, thread_id: str, run_id: str, *args, **kwargs) -> MockRun:
        return MockAgentsOperations._shared_runs.get(run_id)

    def list_agents(self, *args, **kwargs) -> MockAgentList:
        return MockAgentList([
            MockAgent("asst_intake", "IntakeAgent"),
            MockAgent("asst_extraction", "ExtractionAgent"),
            MockAgent("asst_validation", "ValidationAgent"),
            MockAgent("asst_tax_mapping", "TaxMappingAgent"),
            MockAgent("asst_form_generation", "Form1040GenerationAgent"),
            MockAgent("asst_compliance", "ComplianceAgent"),
            MockAgent("foundry-w2-tax-orchestrator", "foundry-w2-tax-orchestrator"),
        ])

    @classmethod
    def reset(cls):
        """Clear all shared state. Use in test tearDown to isolate tests."""
        cls._shared_threads.clear()
        cls._shared_runs.clear()

class MockAIProjectClient:
    def __init__(self):
        self.agents = MockAgentsOperations()

    @classmethod
    def from_connection_string(cls, conn_str: str, credential) -> "MockAIProjectClient":
        return cls()

