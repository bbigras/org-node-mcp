# High-Level Design: Org-Node Knowledge Base Server

## 1. Problem Description

The goal is to create a server application that exposes a knowledge base stored in org-mode files (`.org`) located in a `/nodes` directory. This server will be accessed by an LLM client via a defined API. The server needs to provide functionality for discovering the structure of the knowledge base (files, headings with unique IDs), retrieving the content of specific nodes (identified by their unique IDs), creating new nodes, modifying existing nodes, and adding backlinks between nodes.

## 2. User Journeys

*   **Journey 1: Knowledge Discovery**
    1.  The LLM client connects to the server.
    2.  The LLM client requests a list of all available knowledge nodes.
    3.  The server scans the configured directories.
    4.  The server parses the `.org` files, identifies headings with `:ID:` properties, and extracts file structure, heading names, and their unique IDs.
    5.  The server formats this information into a JSON structure.
    6.  The server sends the JSON structure back to the LLM client.

*   **Journey 2: Specific Node Retrieval**
    1.  The LLM client, having previously discovered node IDs (or knowing them beforehand), decides it needs the content of specific nodes.
    2.  The LLM client sends a request to the server, providing a list of unique node IDs.
    3.  The server locates the corresponding files and extracts the cleaned content associated with each requested node ID.
    4.  The server formats the retrieved content into a JSON structure (a dictionary mapping ID to content).
    5.  The server sends the JSON structure back to the LLM client.

*   **Journey 3: Node Modification**
    1.  The LLM client identifies a node to modify.
    2.  The LLM client sends a request to the server with the node's ID and new content.
    3.  The server locates the node's file and updates its content, preserving Org-mode metadata.
    4.  The server reloads its internal cache.
    5.  The server sends a success/failure response.

*   **Journey 4: Node Creation**
    1.  The LLM client determines a new knowledge node is needed.
    2.  The LLM client sends a request to the server with a heading, content, and optionally related node IDs.
    3.  The server generates a unique ID and a filename.
    4.  The server creates a new `.org` file (or appends to an existing one) with the new node's content and properties.
    5.  The server adds backlinks from any specified related nodes to the new node.
    6.  The server reloads its internal cache.
    7.  The server sends a success/failure response with the new node's ID.

*   **Journey 5: Backlink Management**
    1.  The LLM client identifies two nodes that should be linked.
    2.  The LLM client sends a request to the server with source and target node IDs, and an optional description.
    3.  The server adds a forward link (`[[id:target_id]]`) to the source node's content.
    4.  The server adds a backlink entry (`[timestamp] <- [[id:source_id]]`) to the target node's `:BACKLINKS:` section (creating it if necessary).
    5.  The server reloads its internal cache.
    6.  The server sends a success/failure response.

## 3. User Stories

*   **US1:** As an LLM client, I want to request a structured overview of the entire knowledge base, including filenames, headings, and their unique IDs, so that I can understand what information is available.
*   **US2:** As an LLM client, I want to request the content of specific knowledge nodes by providing their unique IDs, so that I can retrieve detailed information relevant to my task.
*   **US3:** As an LLM client, I want to modify the content of an existing knowledge node, so that I can update information.
*   **US4:** As an LLM client, I want to create new knowledge nodes with specified headings and content, and link them to existing nodes, so that I can expand the knowledge base.
*   **US5:** As an LLM client, I want to add bi-directional links between existing nodes, so that relationships within the knowledge base are explicitly maintained.
*   **US6:** As the server application, I want to manage an in-memory cache of parsed Org nodes, reloading it after write operations, to ensure data consistency and efficient retrieval.
*   **US7:** As the server application, I want to restrict file operations to configured directories, to prevent unauthorized file access.

## 4. High-Level Design

### 4.1. Architecture

*   A single server process built using the `FastMCP` framework (`server.py`).
*   The server will manage access to org-mode files located in directories specified via command-line arguments (`--nodes-dirs`).
*   All direct interaction with the org-mode files (reading, parsing, finding IDs, resolving backlinks, writing) is handled by internal functions within `server.py`.
*   The server will expose its functionalities as `FastMCP` tools.

### 4.2. Components

1.  **FastMCP Server (`server.py`):**
    *   Initializes the `FastMCP` application.
    *   Defines API endpoints (tools) corresponding to the user stories.
    *   Handles incoming requests from the LLM client.
    *   Calls appropriate internal functions to fulfill requests.
    *   Formats data into JSON responses.
    *   Manages server lifecycle and configuration, including `NODES_DIRECTORIES` via `argparse`.
    *   Manages an in-memory cache (`_cache`) of parsed Org node data, with a refresh mechanism and explicit reload on write operations.
    *   Includes helper functions for file validation (`_validate_filepath`), filename sanitization (`_sanitize_filename`), content cleaning (`_clean_node_content`), and node content retrieval (`_get_node_content`).
    *   Includes parsing logic (`_parse_org_file_content`) to extract node data (ID, heading, properties, line numbers) from Org files.

2.  **Org Files (`/nodes/*.org`):**
    *   The raw knowledge base data stored in org-mode format.
    *   Expected to contain headings with unique `:ID:` properties.
    *   May contain links between nodes (e.g., `[[id:UUID]]`).

### 4.3. API Design (FastMCP Tools)

The server exposes the following tools:

1.  **`list_knowledge_nodes`**:
    *   **Description:** "Scans the configured knowledge base directories and returns a structured list of all Org files and the headings within them that have unique IDs. Use this to discover the available information and find specific node IDs to query further for relevant context to incorporate into your answers."
    *   **Input:** None.
    *   **Output:** `ListNodeIndexResponse` (Pydantic Model) - A JSON object representing the structure. Example:
        ```json
        {
          "files": [
            {
              "filename": "file1.org",
              "nodes": [
                {"heading": "Heading 1.1", "id": "uuid-11"},
                {"heading": "Heading 1.2", "id": "uuid-12"}
              ]
            },
            {
              "filename": "file2.org",
              "nodes": [
                {"heading": "Heading 2.1", "id": "uuid-21"}
              ]
            }
          ]
        }
        ```

2.  **`get_knowledge_nodes`**:
    *   **Description:** "Fetches the cleaned textual content from the configured knowledge base directories for one or more specific node IDs. Provide a list of IDs obtained from 'list_knowledge_nodes'. Returns a dictionary mapping each found ID to its content. Use this to get detailed information about specific topics to incorporate directly into your answers."
    *   **Input:** `node_ids: Annotated[list[str], Field(description="A list of unique node IDs to retrieve.")]`
    *   **Output:** `dict[str, str]` - A JSON object mapping each requested node ID to its *cleaned* content string (without Org metadata like properties blocks). Example:
        ```json
        {
          "uuid-11": "Node content here...",
          "uuid-21": "More content..."
        }
        ```

3.  **`modify_node_content`**:
    *   **Description:** "Modifies the content of an existing node by replacing its current content with new content."
    *   **Input:**
        *   `node_id: Annotated[str, Field(description="The ID of the node to modify")]`
        *   `new_content: Annotated[str, Field(description="The new content to replace the existing content")]`
    *   **Output:** `dict` - `{"success": True, "node_id": "..."}` or `{"success": False, "error": "..."}`.

4.  **`create_new_node`**:
    *   **Description:** """Creates a new factual Org Mode knowledge node with explicit backlinks to related nodes.
    - PROHIBITED: Do NOT include speculative data or unverified claims
    - FORMAT: Heading (*), :PROPERTIES: block, Org Markup body
    - RELATIONS: Must include EXPLICIT backlink IDs from existing nodes in the knowledge base
    - CONTENT: Must be evidence-based using ONLY data from existing nodes

    Auto-generates ID, filename, and validates against fictional entries."""
    *   **Input:** `request: CreateNodeRequest` (Pydantic Model)
        *   `heading: str`
        *   `content: str`
        *   `related_node_ids: List[str] = []`
    *   **Output:** `dict` - `{"success": True, "new_node_id": "..."}` or `{"success": False, "error": "..."}`.

5.  **`add_backlink`**:
    *   **Description:** "Adds a bi-directional link between two nodes, updating both the source and target nodes' backlink sections."
    *   **Input:**
        *   `source_node_id: Annotated[str, Field(description="The ID of the source node that will contain the link")]`
        *   `target_node_id: Annotated[str, Field(description="The ID of the target node to link to")]`
        *   `link_description: Annotated[str, Field(description="Text describing the connection")] = ""`
    *   **Output:** `dict` - `{"success": True, "source_id": "...", "target_id": "..."}` or `{"success": False, "error": "..."}`.

### 4.4. Data Flow

*   **List Nodes:** Client -> `server.py:list_knowledge_nodes` -> `server.py:load_org_nodes` & `_format_node_index` -> Filesystem Scan/Parse -> `server.py` -> Client (JSON Index)
*   **Get Nodes:** Client -> `server.py:get_knowledge_nodes` (with IDs) -> `server.py:load_org_nodes` & `_get_node_content` (which calls `_clean_node_content`) -> Filesystem Read/Extract -> `server.py` -> Client (JSON Content Map)
*   **Modify Node:** Client -> `server.py:modify_node_content` -> Filesystem Read/Write -> `server.py:reload_org_cache` -> `server.py` -> Client (Success/Failure)
*   **Create Node:** Client -> `server.py:create_new_node` -> Filesystem Write -> `server.py:reload_org_cache` -> `server.py` -> Client (Success/Failure)
*   **Add Backlink:** Client -> `server.py:add_backlink` -> Filesystem Read/Write (source) -> Filesystem Read/Write (target) -> `server.py:reload_org_cache` -> `server.py` -> Client (Success/Failure)

### 4.5. Assumptions/Dependencies

*   The server's internal functions handle interaction with org files.
*   Org files are located in directories specified by the `--nodes-dirs` command-line argument.
*   Org files use `:ID:` properties in headings for unique identification.
*   The `FastMCP` framework is used for defining and serving these tools.
*   `aiofiles` is used for asynchronous file operations where appropriate (though current implementation uses synchronous `open` for simplicity in some places).
*   `Pydantic` models are used for structured tool inputs and outputs.
