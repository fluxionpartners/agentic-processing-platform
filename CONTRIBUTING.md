# Contributing to the Microsoft Foundry Tax Intelligence Platform

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check the issue list as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

```markdown
## Description
Brief description of the bug

## Steps to Reproduce
1. Step 1
2. Step 2
3. ...

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: (Windows, macOS, Linux)
- Python: 3.11+
- Azure CLI: (version)

## Logs or Screenshots
If applicable, attach logs or screenshots
```

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub Issues. When creating an enhancement suggestion, please include:

- **Use case**: Why would this be useful?
- **Current behavior**: How do you currently work around this?
- **Proposed solution**: How should this work?
- **Examples**: Show examples of how the feature might be used

### Pull Requests

1. **Fork the repository** and create a new branch
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code style guidelines

3. **Write tests** for new functionality
   ```bash
   python -m unittest discover -s tests
   ```

4. **Update documentation** if your changes affect documentation

5. **Commit your changes** with clear commit messages
   ```bash
   git commit -m "feat: add new feature"
   git commit -m "fix: resolve issue #123"
   git commit -m "docs: update deployment guide"
   ```

6. **Push to your fork** and submit a pull request
   ```bash
   git push origin feature/your-feature-name
   ```

## Development Workflow

### Setting Up Development Environment

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/agentic-processing-platform.git
cd agentic-processing-platform

# Create virtual environment
python -m venv venv
source venv/Scripts/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r src/foundry_agents/requirements.txt
pip install -r src/services/w2-intake/requirements.txt
pip install pytest pytest-cov  # Optional development dependencies
```

### Running Tests

```bash
# Run all tests
python -m unittest discover -s tests

# Run with pytest if installed
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

### Code Style

We follow PEP 8 conventions:

- **Line length**: 100 characters max
- **Indentation**: 4 spaces
- **Naming**: 
  - Functions/variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
- **Docstrings**: Google-style

Example:

```python
def extract_tax_fields(document: bytes) -> Dict[str, str]:
    """Extract tax fields from a W-2 document.
    
    Args:
        document: Base64-encoded document bytes
        
    Returns:
        Dictionary mapping field names to extracted values
        
    Raises:
        ValueError: If document cannot be parsed
    """
    # Implementation
    pass
```

### Commit Message Conventions

Use semantic commit messages:

```
feat: add new feature
fix: fix a bug
docs: update documentation
style: code style changes (formatting, etc.)
refactor: refactor code without changing functionality
test: add tests
perf: performance improvements
chore: maintenance tasks
```

Examples:
- `feat: implement extraction agent`
- `fix: handle missing EIN in validation`
- `docs: add deployment guide`
- `test: add integration tests for intake service`

### Branching Strategy

- `main` — Production-ready code
- `develop` — Development branch
- `feature/feature-name` — Feature branches
- `fix/issue-name` — Bugfix branches
- `docs/documentation-name` — Documentation branches

## Project Structure

Key directories for contribution:

```
src/services/               # Service implementations
├── w2-intake/             # Production service
├── document-extraction/   # Under development
├── data-validation/       # Under development
├── tax-mapping/           # Under development
└── audit-monitoring/      # Under development

src/foundry_agents/        # Agent orchestration
├── supervisor/            # Orchestrator
├── intake/                # Intake agent
├── extraction/            # Extraction agent
├── validation/            # Validation agent
├── tax-mapping/           # Tax mapping agent
├── compliance/            # Compliance agent
└── human-review/          # Human review agent

infrastructure/services/   # Bicep IaC templates
├── w2-intake/
├── document-extraction/
├── data-validation/
├── tax-mapping/
└── audit-monitoring/

docs/                      # Documentation
scripts/services/          # Deployment scripts
tests/                     # Tests (unit, integration)
```

## Areas Needing Contributions

### High Priority

- [ ] Unit tests for all agents
- [ ] Integration tests for end-to-end pipeline
- [ ] Extraction agent implementation (Azure Document Intelligence)
- [ ] Validation rules engine
- [ ] API documentation

### Medium Priority

- [ ] Tax mapping service implementation
- [ ] Compliance service implementation
- [ ] Performance optimization
- [ ] Security hardening

### Low Priority

- [ ] Additional documentation
- [ ] Code examples
- [ ] Blog posts or case studies

## Documentation Style

### Markdown Files

- Use clear headings with `#`, `##`, `###`
- Include code examples with language specifiers
- Add tables for structured information
- Include links to related documentation

### Python Docstrings

```python
def function_name(param1: str, param2: int) -> bool:
    """Brief one-line summary.
    
    Extended description if needed. Explain the why and how.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When something is invalid
        
    Example:
        >>> function_name("test", 42)
        True
    """
    pass
```

## Review Process

1. **Code review** — At least one maintainer review required
2. **Tests** — All tests must pass
3. **Documentation** — Updated if needed
4. **Merge** — Approved PRs are merged to develop/main

## Release Process

Releases follow semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

Release process:
1. Update version in `setup.py` or `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create release tag: `git tag v1.0.0`
4. Push tag: `git push origin v1.0.0`

## Questions or Need Help?

- **Documentation**: See [docs/](docs/) for comprehensive guides
- **GitHub Discussions**: Ask architecture or design questions
- **GitHub Issues**: Report bugs or request features
- **Email**: (Contact info if provided)

## Acknowledgments

Thank you for contributing to making this platform better! 🙏

---

**By contributing, you agree that your contributions will be licensed under the same Apache 2.0 license that covers the project.**

