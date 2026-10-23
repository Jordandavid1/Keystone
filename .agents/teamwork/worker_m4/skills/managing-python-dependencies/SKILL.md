# Managing Python Dependencies Skill Dump
Source: C:\Users\Lesia Eden\.gemini\config\skills\managing-python-dependencies\SKILL.md

Core Methodology:
- BEFORE any pip install, detect existing dependency manager in priority order: uv, poetry, pipenv, conda, venv+pip.
- Default to venv + pip + requirements.txt when no other manager is detected.
- Never run pip install globally. Always use explicit venv path (.venv/bin/pip or .venv/Scripts/pip).
- Reactive checks only: do not probe environment proactively unless installing or troubleshooting. Bundle probes into composite command.
