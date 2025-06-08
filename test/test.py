import pytest
import json  # Import json for parsing
import os
import sys
import shutil # For copying test files
import uuid # For generating IDs if needed
import aiofiles # For async file operations in tests
from pathlib import Path # For easier path handling
import datetime # For checking backlink timestamps

import pytest
import re
from fastmcp.client import Client
from mcp.types import TextContent  # Correct import path from example

# Add the parent directory to the path to find the server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the server instance
# Ensure server.py defines the 'mcp' object globally
try:
    import server # Import the server module itself to access globals
    from server import mcp
except ImportError:
    pytest.fail("Could not import 'mcp' or 'server' from server.py. Make sure it's defined globally.")


# --- Fixtures for Test Files ---

@pytest.fixture(scope="function")
def test_org_file(tmp_path: Path) -> Path:
    """Fixture to provide a temporary copy of test-node.org for modification tests."""
    source_file = Path("nodes/test-node.org")
    if not source_file.exists():
        pytest.fail(f"Source test file not found: {source_file}")

    dest_file = tmp_path / source_file.name
    shutil.copy(source_file, dest_file)
    # Make sure the server uses this temp dir for the duration of the test
    # This requires modifying the global NODES_DIRECTORIES temporarily
    original_dirs = server.NODES_DIRECTORIES
    server.NODES_DIRECTORIES = [str(tmp_path)]
    server.reload_org_cache() # Ensure cache uses the new temp directory
    yield dest_file # Provide the path to the test function
    # Restore original directories after test
    server.NODES_DIRECTORIES = original_dirs
    server.reload_org_cache() # Restore cache to original directories
    # Cleanup of file happens automatically with tmp_path fixture


@pytest.fixture(scope="function")
def multi_node_test_org_file(tmp_path: Path) -> Path:
    """Fixture to provide a temporary copy of multi_node_test.org for link tests."""
    # Ensure the assets directory exists
    assets_dir = Path("test/assets")
    assets_dir.mkdir(exist_ok=True)
    source_file = assets_dir / "multi_node_test.org"
    if not source_file.exists():
        # Attempt to create it if missing (useful for initial setup)
        try:
            source_file.write_text("""#+title: Multi Node Test File

* Node A
:PROPERTIES:
:ID:       node-a-id
:END:

This is the content of Node A.

* Node B
:PROPERTIES:
:ID:       node-b-id
:END:

This is the content of Node B. It might mention [[id:node-a-id][Node A]].

* Node C (Child of B)
:PROPERTIES:
:ID:       node-c-id
:END:

Content for Node C.
""", encoding='utf-8')
            print(f"\nCreated missing test asset: {source_file}")
        except Exception as e:
             pytest.fail(f"Failed to create/find source multi-node test file: {source_file}. Error: {e}")


    dest_file = tmp_path / source_file.name
    shutil.copy(source_file, dest_file)
    # Make sure the server uses this temp dir for the duration of the test
    original_dirs = server.NODES_DIRECTORIES
    server.NODES_DIRECTORIES = [str(tmp_path)]
    server.reload_org_cache() # Ensure cache uses the new temp directory
    yield dest_file
    # Restore original directories after test
    server.NODES_DIRECTORIES = original_dirs
    server.reload_org_cache() # Restore cache to original directories


# --- Test Functions ---

@pytest.mark.asyncio
async def test_list_knowledge_nodes_tool_returns_correct_structure():
    """
    Test that the 'list_knowledge_nodes' tool returns the expected structure
    based on the HLD and the current content of the 'nodes/' directory.
    """
    async with Client(mcp) as client:
        # Call the tool
        response_content = await client.call_tool("list_knowledge_nodes", {})

        # --- Check Response Structure ---
        assert isinstance(response_content, list), "Response should be a list of content blocks."
        assert len(response_content) > 0, "Response list should not be empty."
        assert isinstance(response_content[0], TextContent), "First content block should be TextContent."

        # --- Parse JSON and Assert on Dictionary Structure ---
        try:
            result_dict = json.loads(response_content[0].text)
        except json.JSONDecodeError:
            pytest.fail(f"Failed to parse JSON from tool response: {response_content[0].text}")

        assert isinstance(result_dict, dict), "Parsed result should be a dictionary."
        assert "files" in result_dict, "Result dictionary should have a 'files' key."
        assert isinstance(result_dict["files"], list), "'files' key should contain a list."

        # --- Content Assertions (Based on current nodes/ and parser logic) ---
        # Count files in nodes/ with :ID: properties
        # vpns, kdenlive, backups, courses, video-enhancing, bert-kinister,
        # yi-jin-jing, knowledge-graph-memory-server, kdenlive-documentation,
        # openweb-ui-setup, gardening, computer-setup, trackpad-palm-rejection,
        # mcp-server, test-node, appimage-fix, upgrade-emacs
        expected_file_count = 17 # Update if files in nodes/ change
        assert len(result_dict["files"]) == expected_file_count, \
            f"Expected {expected_file_count} files with IDs, but found {len(result_dict['files'])}."

        # Find specific file entries and check their content
        files_data = {item['filename']: item['nodes'] for item in result_dict['files']}

        # Check vpns.org (uses #+title: for heading currently)
        assert "vpns.org" in files_data, "vpns.org entry missing."
        vpns_nodes = files_data["vpns.org"]
        assert isinstance(vpns_nodes, list), "vpns.org nodes should be a list."
        assert len(vpns_nodes) >= 1, "vpns.org should have at least one node."
        # Check the first node found (parser currently finds only one per file)
        assert vpns_nodes[0] == {"heading": "vpns", "id": "7e301f45-ce0e-4fc0-be26-b052f141d91e"}, \
            f"vpns.org node data mismatch: {vpns_nodes[0]}"

        # Check gardening.org (should now find multiple nodes)
        assert "gardening.org" in files_data, "gardening.org entry missing."
        gardening_nodes = files_data["gardening.org"]
        assert isinstance(gardening_nodes, list), "gardening.org nodes should be a list."
        # Expected nodes: File title ID, * Cannabis ID, *** Cannabis soil ID, *** Cannabis Decarboxylating ID
        # Define expected nodes for gardening.org (order might vary depending on implementation)
        expected_gardening_nodes = [
            {"heading": "gardening", "id": "66e3e864-0118-4440-b234-da092a9083c3"}, # File-level ID, uses #+title:
            {"heading": "Cannabis", "id": "7642de1a-6b92-4cca-bdd3-dcabc473c216"}, # Heading * Cannabis
            {"heading": "Cannabis soil", "id": "adc568f9-dd96-479e-8c12-5e0622c96e7e"}, # Heading *** Cannabis soil
            {"heading": "Cannabis Decarboxylating", "id": "a6a84e7f-9bb7-44c6-9590-4007c5bb9be3"} # Heading *** Cannabis Decarboxylating
        ]
        expected_gardening_count = len(expected_gardening_nodes)

        assert len(gardening_nodes) == expected_gardening_count, \
            f"gardening.org: Expected {expected_gardening_count} nodes, found {len(gardening_nodes)}. Nodes: {gardening_nodes}"

        # Check if all expected nodes are present, regardless of order
        # Convert list of dicts to set of tuples (where each tuple contains sorted key-value pairs from a dict)
        # This allows comparing the content without depending on the list order.
        actual_gardening_set = set(tuple(sorted(d.items())) for d in gardening_nodes)
        expected_gardening_set = set(tuple(sorted(d.items())) for d in expected_gardening_nodes)

        assert actual_gardening_set == expected_gardening_set, \
            f"gardening.org node data mismatch.\nExpected: {expected_gardening_set}\nActual: {actual_gardening_set}"


        # Check test-node.org (should still have one node)
        assert "test-node.org" in files_data, "test-node.org entry missing."
        test_node_nodes = files_data["test-node.org"]
        assert isinstance(test_node_nodes, list), "test-node.org nodes should be a list."
        assert len(test_node_nodes) >= 1, "test-node.org should have at least one node."
        assert len(test_node_nodes) == 1, f"test-node.org: Expected 1 node, found {len(test_node_nodes)}"
        assert test_node_nodes[0] == {"heading": "Test Node", "id": "1"}, \
             f"test-node.org node data mismatch: {test_node_nodes[0]}" # Fixed heading expected

        # Check trackpad-palm-rejection.org (should have only one node)
        assert "trackpad-palm-rejection.org" in files_data, "trackpad-palm-rejection.org entry missing."
        trackpad_nodes = files_data["trackpad-palm-rejection.org"]
        # This file only has one :ID: property block at the top level (associated with #+title:).
        # The :CUSTOM_ID: properties are not parsed as separate nodes by our current logic.
        expected_trackpad_nodes = [
            {"heading": "Trackpad palm rejection", "id": "5efb6496-f277-4323-a2bb-2be57794ff4d"}, # File-level ID, uses #+title:
        ]
        expected_trackpad_count = 1 # Only the main file ID
        assert len(trackpad_nodes) == expected_trackpad_count, \
             f"trackpad-palm-rejection.org: Expected {expected_trackpad_count} node, found {len(trackpad_nodes)}. Nodes: {trackpad_nodes}"
        assert trackpad_nodes[0] == expected_trackpad_nodes[0], \
             f"trackpad-palm-rejection.org node data mismatch: {trackpad_nodes[0]}"

        # You can add more checks for other files here following the same pattern.


@pytest.mark.asyncio
async def test_get_knowledge_nodes_tool():
    """
    Test the 'get_knowledge_nodes' tool.
    1. Checks if the tool exists and is callable (initially expects failure - RED).
    2. Verifies the response structure (List[TextContent] containing JSON dict).
    3. Verifies the content of specific nodes retrieved by ID.
    """
    async with Client(mcp) as client:
        node_ids_to_request = [
            "7e301f45-ce0e-4fc0-be26-b052f141d91e", # vpns.org (file-level ID)
            "adc568f9-dd96-479e-8c12-5e0622c96e7e", # gardening.org (sub-heading ID)
            "non-existent-id" # Test case for an ID that doesn't exist
        ]

        # --- Define Expected Content ---
        # Note: Exact whitespace/newlines matter here. Extracted from files.
        # Using triple quotes preserves newlines exactly as they appear in the source files.
        # --- Define Expected *Cleaned* Content ---
        # Remove properties, :END:, :BACKLINKS:, and #+ lines (but keep heading/title)
        # Includes the blank line present in the source file after metadata.
        expected_vpns_content = """#+title: vpns

- Canadian (from Hylands): https://tailscale.com
- https://nordvpn.com""" # Includes #+title: line AND the subsequent blank line now

        # Remove properties, :END: (but keep heading)
        expected_soil_content = """*** Cannabis soil

| Ingredient    | Volume (gal) | Volume (ft^3) | Percent |
|---------------+--------------+---------------+---------|
| Happy Frog    |          8.4 |           1.1 |      70 |
| Coco          |          1.2 |           0.2 |      10 |
| Perlite       |          1.2 |           0.2 |      10 |
| Biochar       |         0.06 |           0.0 |    0.05 |
| Worm Castings |          0.4 |             0 |       3 |
| Compost       |          0.8 |           0.1 |     6.5 |
|---------------+--------------+---------------+---------|
| *TOTAL*         |         *12.0* |           *1.6* |     *100* |"""

        # --- Call the tool ---
        response_content = await client.call_tool("get_knowledge_nodes", {"node_ids": node_ids_to_request})

        # --- Assertions for the tool response ---
        assert isinstance(response_content, list) and len(response_content) > 0, "Response should be a list of content blocks."
        assert isinstance(response_content[0], TextContent), "First content block should be TextContent."

        try:
            result_dict = json.loads(response_content[0].text)
        except json.JSONDecodeError:
            pytest.fail(f"Failed to parse JSON from tool response: {response_content[0].text}")

        assert isinstance(result_dict, dict), "Parsed result should be a dictionary."

        # Check that requested IDs that exist are present as keys
        assert "7e301f45-ce0e-4fc0-be26-b052f141d91e" in result_dict
        assert "adc568f9-dd96-479e-8c12-5e0622c96e7e" in result_dict
        # Check that non-existent ID is NOT present (or handle as None if implementation chooses)
        assert "non-existent-id" not in result_dict, "Non-existent ID should not be in the result keys"

        # Check content for existing nodes
        # These assertions will fail initially because the tool returns placeholder text.
        assert result_dict["7e301f45-ce0e-4fc0-be26-b052f141d91e"] == expected_vpns_content, "vpns.org content mismatch"
        assert result_dict["adc568f9-dd96-479e-8c12-5e0622c96e7e"] == expected_soil_content, "gardening.org soil content mismatch"


# --- Tests for Write Operations ---

@pytest.mark.asyncio
async def test_modify_node_content_tool(test_org_file: Path):
    """
    Test the 'modify_node_content' tool (RED phase).
    Expects failure until the tool is implemented.
    """
    node_id_to_modify = "1" # ID from test-node.org
    new_content = "This is the new, updated content for the test node.\nIt has multiple lines."
    # The modify_node_content tool should preserve the properties block
    # and replace the content that was originally after it.
    # For test-node.org, the original content after properties was:
    # #+title: Test Node
    # #+filetags: :org:api:
    # These lines will be replaced by new_content.
    expected_file_content_after = f""":PROPERTIES:
:ID:       {node_id_to_modify}
:CREATED:  [2025-04-20 Sun 01:45]
:END:
{new_content}"""

    async with Client(mcp) as client:
        # Now that the tool exists, make the actual call
        response = await client.call_tool(
            "modify_node_content",
            {"node_id": node_id_to_modify, "new_content": new_content}
        )
        
        # These assertions will fail until the tool is properly implemented
        assert isinstance(response, list) and len(response) > 0
        assert isinstance(response[0], TextContent)
        try:
            result = json.loads(response[0].text)
            assert result.get("success") is True
            assert result.get("node_id") == node_id_to_modify
        except (json.JSONDecodeError, AssertionError) as e:
            pytest.fail(f"Tool response validation failed: {e} - Response: {response[0].text}")

        # Verify file content was modified
        async with aiofiles.open(test_org_file, mode='r', encoding='utf-8') as f:
            actual_content = await f.read()
            # Normalize line endings for comparison if needed
            actual_content = actual_content.replace('\r\n', '\n')
            expected_file_content_after = expected_file_content_after.replace('\r\n', '\n')
            assert actual_content.strip() == expected_file_content_after.strip()


@pytest.mark.asyncio
async def test_create_new_node_tool(tmp_path: Path):
    """Test new node creation with automated filename generation"""
    # Setup test directory as first nodes directory
    server.NODES_DIRECTORIES = [str(tmp_path)]
    server.reload_org_cache()
    
    test_heading = "Test Node with Cool Stuff!"
    test_content = "This is some test content\nwith multiple lines."
    
    async with Client(mcp) as client:
        response = await client.call_tool(
            "create_new_node",
            {
                "request": {
                    "heading": test_heading,
                    "content": test_content
                }
            }
        )

        # Verify response structure
        assert isinstance(response, list) and len(response) > 0
        assert isinstance(response[0], TextContent)
        
        result = json.loads(response[0].text)
        assert result.get("success") is True
        new_node_id = result.get("new_node_id")
        assert uuid.UUID(new_node_id), "Invalid UUID format"

        # Verify file was created with expected pattern
        created_files = list(tmp_path.glob("*.org"))
        assert len(created_files) == 1, "Should create exactly one file"
        
        filename = created_files[0].name
        assert re.match(r"test-node-with-cool-stuff-[a-f0-9]{6}\.org", filename), \
            "Filename not sanitized properly"

        # Verify file contents
        with open(created_files[0], "r", encoding="utf-8") as f:
            content = f.read()
            assert f"* {test_heading}" in content
            assert f":ID:       {new_node_id}" in content
            assert test_content in content
        
        # These assertions will fail until the tool is properly implemented
        assert isinstance(response, list) and len(response) > 0
        assert isinstance(response[0], TextContent)
        new_node_id = None
        try:
            result = json.loads(response[0].text)
            assert result.get("success") is True
            assert "new_node_id" in result
            new_node_id = result["new_node_id"]
            # Basic UUID format check
            assert isinstance(uuid.UUID(new_node_id), uuid.UUID)
        except (json.JSONDecodeError, AssertionError, ValueError) as e:
            pytest.fail(f"Tool response validation failed: {e} - Response: {response[0].text}")

        # Verify file content was modified - this was a duplicate of the earlier check
        # and references undefined variables (new_heading, new_content)
        # Removed duplicate assertions


@pytest.mark.asyncio
async def test_add_backlink_tool(multi_node_test_org_file: Path):
    """
    Test the 'add_backlink' tool (RED phase).
    Expects failure until the tool is implemented.
    """
    source_node_id = "node-a-id" # From multi_node_test.org
    target_node_id = "node-b-id" # From multi_node_test.org
    link_description = "Link from A to B"

    async with Client(mcp) as client:
        # Now that the tool exists, make the actual call
        response = await client.call_tool(
            "add_backlink",
            {
                "source_node_id": source_node_id,
                "target_node_id": target_node_id,
                "link_description": link_description
            }
        )
        
        # These assertions will fail until the tool is properly implemented
        assert isinstance(response, list) and len(response) > 0
        assert isinstance(response[0], TextContent)
        try:
            result = json.loads(response[0].text)
            assert result.get("success") is True
        except (json.JSONDecodeError, AssertionError) as e:
            pytest.fail(f"Tool response validation failed: {e} - Response: {response[0].text}")

        # Verify file content was modified
        async with aiofiles.open(multi_node_test_org_file, mode='r', encoding='utf-8') as f:
            actual_content = await f.read()
            # Check for forward link in Node A's content
            node_a_pattern = re.compile(r"\* Node A.*?END:(.*?)(\* Node B|# EOF)", re.DOTALL)
            node_a_match = node_a_pattern.search(actual_content)
            assert node_a_match, "Could not find Node A content block"
            assert f"[[id:{target_node_id}][{link_description}]]" in node_a_match.group(1)

            # Check for backlink in Node B's metadata
            node_b_pattern = re.compile(r"\* Node B.*?(:BACKLINKS:.*?):END:", re.DOTALL)
            node_b_match = node_b_pattern.search(actual_content)
            assert node_b_match, "Could not find Node B backlinks block"
            # Check for timestamp and link ID
            assert f"[[id:{source_node_id}]]" in node_b_match.group(1)
