# Current Development Context

**Goal:** Migrate core proxy logic to `/api` endpoint, remove old system.

**Status:** COMPLETED
- Proxy logic successfully migrated to `/api/{full_path:path}`.
- Old catch-all endpoint and `/beta` endpoint removed.
- Old policy system (`Policy`, `get_policy`, `policy_loader.py`, `POLICY_MODULE`) removed.
- Policy loading logic integrated into `dependencies.py`.
- All unit tests updated and passing.
- Obsolete files and tests deleted.

**Next Steps:** Review changes and commit.
