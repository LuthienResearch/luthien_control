# To Do List

Items discovered during development that are out of scope for the current task but should be addressed later.

- [ ] ...

## Config Management Strategy
- **Decision Needed:** The `config_and_secrets.mdc` rule mandates using `pydantic-settings`, which is already used in `luthien_control/config/settings.py`. However, the rule was added after the initial implementation. 
- **Action:** Either formally decide to stick with `pydantic-settings` everywhere and ensure full compliance OR update/remove the `config_and_secrets.mdc` rule to reflect the chosen strategy.
- **Context:** Discrepancy identified during database test fixture setup (Task ID based on commit hash or date).
