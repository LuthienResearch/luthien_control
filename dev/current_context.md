# Current Task
## Implement Compression Handling in Proxy

- **Goal:** Modify the proxy server to correctly handle compressed (`gzip`, `deflate`, `br`) request and response bodies.
- **Details:**
    - Decompress request bodies if needed for logging/policy checks, forwarding the original compressed request to the backend.
    - Decompress response bodies if needed for logging, forwarding the original compressed response to the client.
    - Identify relevant code sections for request/response body processing.
    - Add necessary decompression logic using standard libraries (and potentially `brotli`).
    - Implement unit tests covering various compression scenarios (requests and responses).
- **Status:** Complete
- **Major changes made:**
    - Added `brotli` dependency.
    - Created `luthien_control/proxy/utils.py` with decompression functions.
    - Created `tests/proxy/test_utils.py` with corresponding unit tests.
    - Followed TDD: Skeletons -> Tests -> Fail -> Implement -> Pass.
    - Updated `luthien_control/proxy/server.py` to import utils and add comments for future use, preserving streaming.
- **Next Steps:**
    - Integrate decompression into logging/policy checks (requires handling streaming implications, potentially referencing `dev/ToDo.md` item).
