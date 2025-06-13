# Org-Node Knowledge Base Server

A server application that exposes a knowledge base stored in Emacs Org-mode files through an API. The server allows clients to discover the structure of the knowledge base, retrieve specific nodes by ID, create new nodes, modify existing nodes, and add backlinks between nodes.

## Features

- **Knowledge Discovery**: List all available Org files and their headings with unique IDs
- **Node Retrieval**: Retrieve content of specific nodes by their unique IDs
- **Node Creation**: Create new knowledge nodes in Org files
- **Content Modification**: Modify content of existing nodes
- **Backlink Management**: Add bi-directional links between nodes
- **Org-mode Support**: Works with standard Org-mode files while preserving their format

## Architecture

The server is built using:
- FastMCP framework for the API
- Python for the server logic
- Org-mode files for storing knowledge
- Standard directory structure for organizing knowledge files

## Available Tools

### `list_knowledge_nodes`
Lists all available knowledge nodes (files and headings with their unique IDs).

### `get_knowledge_nodes`
Retrieves the content of specific knowledge nodes based on their unique IDs.

### `modify_node_content`
Modifies the content of an existing node.

### `create_new_node`
Creates a new knowledge node in a specified Org file.

### `add_backlink`
Adds a bi-directional link between two nodes.

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/org-node-mcp.git
cd org-node-mcp

# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv add pytest pytest-asyncio aiofiles

# Install the package in development mode
pip install -e .
```

## Usage

1. Place your Org-mode files in the `nodes/` directory (or specify alternative directories with `--nodes-dirs`)
2. Start the server:
```bash
python server.py
```

### Setting up `mcp.json` for FastMCP Client

For seamless integration with a FastMCP client, you can configure an `mcp.json` file in your client's working directory. This allows the client to automatically discover and connect to the `org-node` server.

Create a file named `mcp.json` with the following content:

```json
{
    "org-node": {
        "command": "/path/to/your/org-node-mcp/.venv/bin/python3",
        "args": [
            "/path/to/your/org-node-mcp/server.py",
            "--nodes-dir",
            "/path/to/your/org-nodes-directory/"
        ]
    }
}
```

**Replace the example paths:**
*   `/path/to/your/org-node-mcp/` should be the absolute path to your cloned `org-node-mcp` repository.
*   `/path/to/your/org-nodes-directory/` should be the absolute path to the directory containing your Org-mode files (e.g., `nodes/` inside the repository, or any other directory you use).

3. Use a FastMCP client to connect to the server and use the available tools.

## Directory Structure

- `nodes/`: Directory containing Org-mode files with knowledge
- `server.py`: Main server implementation
- `test/`: Test suite
- `README.md`: This file
- `CONVENTIONS.md`: Development conventions
- `hld.md`: High-level design documentation

## Development

```bash
# Run tests
uv run python -m pytest test/test.py

# Run the server
python server.py
```

## Requirements

- Python 3.12+
- FastMCP framework
- Org-mode files in the `nodes/` directory
- aiofiles for async file operations
- pytest for running tests
