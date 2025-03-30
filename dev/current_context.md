# Current Task
## Investigate Configuration Management Consistency
 - Status: In Progress
 - Goal: Identify all methods used for configuration management across the project to ensure consistency, comparing findings against the `config_and_secrets.mdc` rule.
 - Plan:
    1. Search codebase for configuration-related patterns (e.g., `getenv`, `environ`, config file loading).
    2. Analyze findings to understand current practices.
    3. Discuss with user whether to consolidate on `pydantic-settings` or revise the rule.
