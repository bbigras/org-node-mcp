# Plan: Implement `list_knowledge_nodes` Tool

**Current State:** Working on GREEN/REFACTOR for `test_list_knowledge_nodes_tool_exists_and_callable`.

- [X] **Step 1: Define the Tool Skeleton (GREEN Phase)**
    - [X] In `server.py`, define `list_knowledge_nodes` with `@mcp.tool()`.
    - [X] Use the correct name (`"list_knowledge_nodes"`) and description from `hld.md`.
    - [X] Initial implementation: call `load_org_nodes("nodes")` and return the result directly. (Now calls formatter).

- [X] **Step 2: Refine Parser for Heading/Title (GREEN Phase)**
    - [X] Modify `_parse_org_file_content` in `server.py` to find *all* nodes (sections with `:ID:` properties) within a file.
    - [X] Return `List[OrgNodeData]` instead of `Optional[OrgNodeData]`.
    - [X] Logic implemented: Find `:PROPERTIES:` block with `:ID:`, associate with nearest preceding `* Heading`, fallback to `#+title:` or filename.
    - [X] Modify `load_org_nodes` to handle the list of nodes returned by the parser.
    - [X] `heading: Optional[str]` already exists in `OrgNodeData`.
    - [X] Store the captured heading/title/filename in the `heading` field for each node.

- [X] **Step 3: Implement Output Formatting (GREEN Phase)**
    - [X] Create `_format_node_index(cache: OrgKnowledgeCache) -> dict` in `server.py`.
    - [X] Input: Result from `load_org_nodes`.
    - [X] Logic: Group nodes by `filepath`, extract `heading` and `id`.
    - [X] Output: Dictionary matching the structure in `hld.md` (using `os.path.basename(filepath)` for filename).
    - [X] Modify `list_knowledge_nodes` tool to call `_format_node_index` and return its result.

- [X] **Step 4: Refine the Test (Refactor/Test Phase)**
    - [X] Modify `test/test.py`.
    - [X] Remove the `try...except Exception` block. (Done in next step)
    - [X] Call `await client.call_tool("list_knowledge_nodes", {})` directly. (Done in next step)
    - [X] Add assertions to check the structure and content against `nodes/*.org` data and HLD format.
        - [X] Check overall structure (`{"files": [...]}`).
        - [X] Check number of files matches files in `nodes/` with IDs.
        - [X] Check specific file entries (`vpns.org`, `gardening.org`, `test-node.org`, `trackpad-palm-rejection.org`) for correct filename, heading(s), and ID(s) based on multi-node parser logic (Step 2) and actual file content. Assertions check for *all* expected nodes within a file.

- [X] **Step 5: Execute and Iterate**
    - [X] Run `uv run pytest test/test.py`. (Passed after refining parser logic)
    - [X] Debug and refine `server.py` code (Steps 1-3) and `test/test.py` assertions (Step 4) until tests pass (GREEN). (Refactored parser heading logic to search backwards, tests passed).
    - [X] Review code for clarity, correctness (heading logic), and efficiency (REFACTOR). (Added comments, renamed var, removed dead code/comments).

---

# Plan: Implement `get_knowledge_nodes` Tool

**Goal:** Implement the `get_knowledge_nodes` tool as defined in `hld.md`, including refining the parser to extract full node content.

- [X] **Step 1: Define the Test Case (RED Phase)**
    - [X] In `test/test.py`, create a new async test function `test_get_knowledge_nodes_tool`.
    - [X] Call `await client.call_tool("get_knowledge_nodes", {"node_ids": ["ID1", "ID2", ...]})` with a list of known, valid node IDs from different files (e.g., `7e301f45-ce0e-4fc0-be26-b052f141d91e` from `vpns.org`, `adc568f9-dd96-479e-8c12-5e0622c96e7e` from `gardening.org`).
    - [X] Assert that the test initially fails (tool not found or incorrect response).
    - [X] Add assertions to check the response structure:
        - [X] Response is `List[TextContent]`.
        - [X] The `text` attribute of the `TextContent` block is valid JSON.
        - [X] The parsed JSON is a dictionary (`dict[str, str]`).
    - [X] Add assertions to check the response content:
        - [X] The dictionary keys match the requested node IDs.
        - [X] The dictionary values (strings) contain the *expected full content* of the corresponding nodes (heading line, properties block, body text). This requires manually defining the expected content string for the test IDs based on the `.org` files.

- [X] **Step 2: Implement the Tool Skeleton (GREEN Phase)**
    - [X] In `server.py`, define `get_knowledge_nodes` with `@mcp.tool()`.
    - [X] Use the correct name (`"get_knowledge_nodes"`) and description from `hld.md`.
    - [X] Define the input parameter `node_ids: Annotated[list[str], Field(description="...")]`.
    - [X] Initial implementation:
        - [X] Load the node cache using `load_org_nodes("nodes")`.
        - [X] Create an empty dictionary `results = {}`.
        - [X] Loop through the requested `node_ids`.
        - [X] If an ID exists in the cache (`cache['nodes_by_id']`), add it to `results` with a placeholder value (e.g., `"Content for {node_id} not implemented yet."`). (Actual content extraction implemented directly).
        - [X] Return the `results` dictionary.
    - [X] Run the test - it should now fail on the content assertion, not the tool call itself. (Test now passes with full implementation).

- [X] **Step 3: Implement Full Node Content Extraction (GREEN Phase)**
    - [X] Modify `_parse_org_file_content` in `server.py`:
        - [X] When a node ID is found, determine the start line (the heading line associated with the node).
        - [X] Determine the end line: This is the line *before* the next heading of the *same or lesser level*, or the end of the file if no such heading exists.
        - [X] Extract the lines between the start and end line (inclusive) as the node's full content string. (Done via start/end lines).
        - [X] Store this full content string in the `OrgNodeData` dictionary (e.g., add a `full_content: str` field). *Alternatively*, store start/end line numbers and re-read the file section in `get_knowledge_nodes` to avoid storing large strings in the cache. Let's try storing start/end lines first. Add `start_line: int` and `end_line: int` to `OrgNodeData`. (Stored start/end lines).
    - [X] Modify `get_knowledge_nodes`:
        - [X] When a requested node ID is found in the cache:
            - [X] Get the `filepath`, `start_line`, and `end_line` from the cached `OrgNodeData`.
            - [X] Read the content of the `filepath`.
            - [X] Extract the relevant lines (`lines[start_line:end_line]`).
            - [X] Join these lines into a single string (`'\n'.join(...)`).
            - [X] Store this string as the value for the node ID in the `results` dictionary.
    - [X] Run the test - it should now pass.

- [X] **Step 4: Refactor and Finalize**
    - [X] Review the code in `_parse_org_file_content` and `get_knowledge_nodes` for clarity, efficiency, and error handling (e.g., file not found during content retrieval). (Added boundary checks, comments).
    - [X] Ensure the heading level logic for determining the end line is correct. (Verified during review).
    - [X] Add comments explaining the node boundary detection logic. (Added).
    - [X] Run tests again to ensure they still pass after refactoring. (Passed).
    - [X] Update this plan, marking steps as complete. (Done).

---

## Enhancements (Future Work)

- [X] **Clean Node Content:** Modify the content retrieval logic (likely in `_get_node_content` or a new helper) to strip Org mode metadata (heading line, properties block, `:END:`, potentially `:BACKLINKS:`) from the node content returned by `get_knowledge_nodes` and `get_knowledge_nodes_with_backlinks`. The goal is to provide cleaner text content focused on the node's body for the LLM client. This will require updating the corresponding tests to expect the cleaned content.
    - [X] RED: Updated `test_get_knowledge_nodes_tool` to expect cleaned content.
    - [X] GREEN: Implemented `_clean_node_content` and called it from `_get_node_content`.
    - [X] REFACTOR: Debugging why cleaning isn't fully working / Refining implementation. Added debug logging to `_clean_node_content`.
- [X] **Refine Tool Metadata:** Improve tool descriptions to guide the LLM on querying the knowledge base and incorporating results. Add Pydantic output models for clearer API contracts (e.g., for `list_knowledge_nodes`).

---

## Write Operations

- [X] **Modify Node Content:** Implement a tool (`modify_node_content`) to replace the body content of an existing node identified by its ID. (Test passing)
- [X] **Create New Node:** Implement a tool (`create_new_node`) to add a new node (with heading, content, and a generated ID) to a specified Org file, potentially positioning it relative to a parent node. (Test passing)
- [X] **Add Backlink:** Implement a tool (`add_backlink`) to insert a forward link (`[[id:target_id]]`) into the body of a source node, pointing to a target node. Also automatically adds/updates the corresponding backlink entry (`[timestamp] <- [[id:source_id]]`) within the `:BACKLINKS:` metadata section of the target node. (Test passing after recent fixes)
- [X] **Cache Invalidation/Reloading:** Ensure the knowledge cache (`OrgKnowledgeCache`) is reloaded after any successful write operation (modify, create, add link).
- [X] **Security Considerations:** Implement checks to ensure all file write operations are restricted to the configured `NODES_DIRECTORIES` (via `_validate_filepath`).
