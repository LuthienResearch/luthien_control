# Changelog

## [TBD]
 - Improved error handling
 - Tighten up typing
 - Increased test coverage
 - Fixed Postgresql issues with tz-aware datetimes (NaiveDatetime)
 - Logging UX
 - Event hooks on context tracking
 - DeepEventedModel for eventing on all state changes
 - OpenAI Chat Completions API request/response objects

## [0.2.5] - 2025-05-28
 - 98% test coverage
 - nits

## [0.2.4] - 2025-05-28
- **Transaction Logging System:**
  - Added `TxLoggingPolicy` for configurable transaction logging to database. (7ef9dcf)
  - Added new `luthien_log` database table via Alembic migration to store transaction logs with JSON data. (50deccdf11ab)
  - Added modular logging specification system with built-in specs:
    - `FullTransactionContextSpec` - Logs complete transaction context
    - `OpenAIRequestSpec` - Logs OpenAI API request data with sensitive data redaction
    - `OpenAIResponseSpec` - Logs OpenAI API response data with content size limits
    - `RequestHeadersSpec` - Logs HTTP request headers with sensitive header filtering
    - `ResponseHeadersSpec` - Logs HTTP response headers with sensitive header filtering
  - Added logging utilities with configurable content size limits and sensitive data redaction (API keys, authentication headers). 
  - Added test coverage for all logging components.
  - Updated control policy registry and serialization to support the new logging policy type.
  - Added `LuthienLog` SQLModel with indexing and JSON support.
- **Code Quality:**
  - Applied ruff formatting and fixes across the codebase. (3af80a4)
  - Added development tracking rules and test guidelines in Cursor rules.
  - pytest GH
  - codecov support
- **Fixes**
  - Fixed default POLICY_FILEPATH value breaking deployments
- **Meta**
  - Various improvements in cursorrules/claude.md
  - Better description in pyproject.toml

## [0.2.3] - 2025-05-19
- **Enhanced Code Quality & Type Safety:**
  - Integrated Pyright for comprehensive static type checking across the project, significantly improving code reliability and maintainability. (Addresses work in #19, #20, #21)
  - Corrected widespread incorrect typing logic, particularly for `Response` objects, ensuring better data integrity. (Primarily #20)
- **Refactoring & CI Improvements:**
  - Refactored `ControlPolicy.from_serialized` to remove unused `**kwargs`, streamlining policy loading. (#20)
  - Improved test coverage, which included some related code refactoring for clarity and robustness. (#19)
  - Consolidated GitHub Actions for code quality checks into a more unified workflow. (#20)
- **Security:**
  - Addressed a potential information exposure vulnerability related to exception handling. (#20)
- **Documentation:**
  - Made minor updates to the `README.md`. (#20)

## [0.2.2]
- GH action for docs deployment (e11e50c)
- README tweaks, including donation, Luthien site, DeepWiki links (16129f0)
- Added short Contribution guidelines to README (dcc252a)
- Add `dev_mode` to skip auth for local development (8c42868)
- Update README with easy Railway deployment and better env var docs (f9ea038)
- Add Ruff linting GitHub Action (10a43d2)
- Apply Ruff formatting (a98acc2, e7943bd)
- New CHANGELOG.md w/ GH Action enforced updates on PRs to main

## [0.2.1] - 2025-05-14
- Merged PR #16: 0.2.1 (Released version 0.2.1)
- Merged PR #15: Added control policy and tests that check for leaked API keys
- Implemented `BlockLeakedApiKeyPolicy` to prevent API key leakage in requests/responses. (33497ff)
- Implemented conditional policy execution logic (Branching Condition) (9915cdc, b062825)
  - Added Comparators for condition evaluation (2bb7c28, 58d5e56)
  - Implemented `get_tx_value` for retrieving values from transaction context (08d4837)
- Fixed dependency tests (ef0c25a)

## [0.2.0] - 2025-05-12
- Load policy from file (f97818d)
- Merged PR #14: Dev (Various development updates)
- Link to developer docs in README (944d4f1)
- Merged PR #10: Minor fixes to readme
- Merged PR #13: 0.2 (Released version 0.2.0) (000e37d)
- Merged PR #12: Mkdocs (Documentation improvements)
  - Documented documentation generation process (d712a49)
  - Improved MkDocs setup and content (6805d78, 01cc20c)
  - Replaced pdoc with MkDocs (ca3bbd9, 05d0e91)
- Added docstrings to `control_policy` module (e3a3f6c)
- Standardized on Google-style docstrings (b15a0ee)
- Added pdoc for documentation generation (b53ecf8)
- Support GET requests in OPTIONS handler (c0205dd)
- More permissive `Allow` headers for CORS (398a7cb)
- Implemented `OPTIONS` request handling for CORS (0dabd6e)
- Added `dev_tracking` rule (fc4f022)
- Improved test coverage for policy CRUD operations (3a52a56, fa40024, 63e43de)
- Renamed `CompoundPolicy` to `SerialPolicy` (8e8ff49)
- Add backend API key from environment variable (b57a486)
- Merged PR #9: Nits (Minor refactors and rule updates)
  - Minor refactors (ba3552f)
  - Renamed `logging_config` to `logging` (3c2bae3)
- Merged PR #8: Fly cleanup (Removed references to Fly.io, preferring Railway) (845857f)
- Added CodeQL GitHub Action for security scanning (8fb843d)
- Merged PR #5: Bump h11 from 0.14.0 to 0.16.0 (Dependabot)
- Merged PR #7: Dev updates (Development setup improvements, Ruff formatting)
  - Cleanup and dev setup updates (7e8b67e, cd6deab, 53d9f0b)
  - Ruff formatting (4fbb2e4)
  - Corrected DB_NAME env var usage (4ddc401)
- Merged PR #6: Improve onboarding documentation (README and .env.example updates) (30d7ebd)
- Merged PR #4: License and tests (Added Apache License 2.0) (348c507)

## [Unreleased] - 2025-04-28 and earlier
- Merged PR #3: April Progress (Various features and fixes from April)
- **2025-04-25:**
    - Enhanced exception handling and improved error feedback in policy loader. (fc2ffd0, `dev/development_log.md`)
        - Added check `if policy_class is None:` after registry lookup to raise `PolicyLoadError` immediately for unknown types in `luthien_control/control_policy/loader.py`. (`dev/development_log.md`)
        - Removed `@pytest.mark.skip` from `test_load_policy_unknown_type` in `tests/control_policy/test_loader.py`. (`dev/development_log.md`)
    - Test improvements and additions. (ac43b12)
    - Added defaults for Swagger UI. (e41c266)
    - Simplified response builder logic. (0b864cb, `dev/development_log.md`)
        - Modified `luthien_control/proxy/orchestration.py` (`run_policy_flow`) to *always* call the `ResponseBuilder` after successful policy execution. (`dev/development_log.md`)
    - Swagger UI improvements, including `create_custom_openapi` in `luthien_control/utils.py`. (1bd1319, `dev/development_log.md`)
    - Fixes for Alembic migrations. (84cfdb4)
    - Fix exception initializers in `luthien_control/control_policy/exceptions.py` for `ClientAuthenticationError` and `ClientAuthenticationNotFoundError`. (`dev/development_log.md`)
- **2025-04-24:**
    - Merged PR #2: Dependency container (Refactored dependency injection)
    - Removed unused functions. (ded376f)
    - Added Swagger UI API Key Support (`HTTPBearer`) & Test No-Auth Passthrough. (a9c9613, `dev/development_log.md`)
        - Added `test_api_proxy_no_auth_policy_no_key_success` to `tests/proxy/test_server.py`. (`dev/development_log.md`)
    - Major dependency refactoring (Dependency Container implementation). (773f6fc)
    - Policy loader no longer needs explicit dependencies passed during `from_serialized`. (8d3d844)
    - Simplified policy loading, removed `REQUIRED_DEPENDENCIES`. (`dev/log_archive/development_log_20250424_175637.md`)
    - Refactored `AddApiKeyHeaderPolicy` for specific OpenAI key usage and updated tests. (`dev/log_archive/development_log_20250424_175637.md`)
    - Refactored `ClientApiKeyAuthPolicy` to use `get_api_key_by_value` directly. (`dev/log_archive/development_log_20250424_175637.md`)
    - Removed `get_response_builder` dependency, instantiating `DefaultResponseBuilder` directly. (`dev/log_archive/development_log_20250424_175637.md`)
    - Simplified orchestration error handling for `ControlPolicyError`. (`dev/log_archive/development_log_20250424_175637.md`)
    - Fixed test failures related to dependency injection refactor. (`dev/log_archive/development_log_20250424_175637.md`)
    - Fixed `test_api_proxy_no_auth_policy_no_key_success` after editor glitch. (`dev/development_log.md`)
- **2025-04-23:**
    - Dockerfile instruction update: SEND EVERYTHING (0827dc7)
    - Refactored policy loading to use a simpler loader (`control_policy/loader.py`) and resolved circular imports. (`dev/log_archive/development_log_20250423_110617.md`)
        - Moved `get_api_key_by_value` to `db/api_key_crud.py`.
        - Moved `PolicyLoadError` to `control_policy/exceptions.py`.
        - Moved `POLICY_NAME_TO_CLASS` registry to `control_policy/registry.py`.
    - Centralized `ApiKeyLookupFunc` type alias to `luthien_control/types.py`. (743a27a, `dev/log_archive/development_log_20250424_175637.md`)
    - Replaced `datetime.utcnow()` with `datetime.now(timezone.utc)` to fix deprecation warnings. (50a066d, `dev/log_archive/development_log_20250424_175637.md`)
    - Fixed `test_load_policy_from_db_success` assertion and `load_policy_from_db` argument passing. (`dev/log_archive/development_log_20250424_175637.md`)
    - Made `from_serialized` methods async for several policies to fix E2E test failures. (`dev/log_archive/development_log_20250424_175637.md`)
    - Refactored policy serialization key from 'name' to 'type'. (0107ff9, df929e9, `dev/log_archive/development_log_20250424_175637.md`)
    - Made `load_policy` in `control_policy/loader.py` asynchronous and updated `CompoundPolicy.from_serialized` and tests. (c0eeaa0, `dev/log_archive/development_log_20250424_175637.md`)
    - Refactored policy CRUD operations in `sqlmodel_crud.py`, removing redundant functions and improving error handling. (0e78429, `dev/log_archive/development_log_20250424_175637.md`)
    - Consolidated `client_api_key_crud` operations into `luthien_control/db/api_key_crud.py`. (a45afc5, `dev/log_archive/development_log_20250423_110617.md`)
- **2025-04-22:**
    - Refactored test mocking for `ClientApiKeyAuthPolicy` using `mock_db_session_cm`