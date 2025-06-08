import datetime
import time
import uuid
from typing import Any
# import aiofiles # No longer used after removing edit_file
from typing import Annotated
from pydantic import Field, BaseModel
from fastmcp import FastMCP, Context
import glob
# import itertools # No longer used after removing complex cleaning logic
import logging
import os
import re
import argparse # Import argparse
from typing import Dict, List, Optional, TypedDict


# --- Global Configuration ---
# List of directories to scan for Org node files. Updated by command-line args.
NODES_DIRECTORIES: List[str] = ["nodes"]


mcp = FastMCP(
    name="org-node-mcp",
    instructions="This server allows to fetch and update documents related to Org-Node."
)

@mcp.resource(
    uri="data://application-information",
    name="ApplicationInfo",
    description="Provides general runtime-information about the application",
    mime_type="application/json",
    tags={"status", "observability"}
)
async def get_application_status() -> dict:
    """Provides general runtime-information about the application"""
    # In a real app, fetch this data dynamically
    return {
          "app_id": "doc-assistant-v1",
          "status": "running",
          "started_at": datetime.datetime.now().isoformat()
     }

@mcp.resource(
    uri="data://user-profile/{user_id}",
    name="UserProfile",
    description="Gets the user profile information for a specific user_id",
    mime_type="application/json",
    tags={"user", "profile"}
)
async def get_user_profile(user_id: str) -> dict:
    """Gets the user profile information for the given user_id"""
    print(f"Fetching profile for user_id: {user_id}")
    # In a real app, fetch user data from a database or API
    # Example data:
    users = {
        "123": {"user_id": "123", "user_name": "Alice", "email": "alice@example.com"},
        "456": {"user_id": "456", "user_name": "Bob", "email": "bob@example.com"},
    }
    return users.get(user_id, {"error": "User not found", "user_id": user_id})


def _validate_filepath(filepath: str) -> None:
    """Verify a filepath is within configured NODES_DIRECTORIES"""
    abs_path = os.path.abspath(filepath)
    resolved_dirs = [os.path.abspath(d) for d in NODES_DIRECTORIES]
    if not any(abs_path.startswith(d) for d in resolved_dirs):
        raise ValueError(f"File access denied: {filepath} not in NODES_DIRECTORIES")

def _sanitize_filename(heading: str) -> str:
    """Convert heading to a safe filename"""
    sanitized = re.sub(r'[^a-zA-Z0-9\-_ ]', '', heading)
    sanitized = sanitized.lower().replace(' ', '-')
    return f"{sanitized[:50]}.org"

# --- Helper function to clean node content ---

def _clean_node_content(raw_content: str) -> str:
    """
    Removes Org mode metadata (heading, properties, backlinks, #+ lines)
    from the raw node content string.
    """
    logging.debug(f"--- Cleaning Node Content ---\nRaw content:\n{raw_content}\n---")
    lines = raw_content.splitlines()
    if not lines:
        return ""

    cleaned_lines = []
    in_metadata_block = False # State for PROPERTIES or BACKLINKS blocks

    # Iterate through all lines (no longer skipping the first based on heading/title)
    for line in lines:
        stripped_line_lower = line.strip().lower()

        # Check for metadata block boundaries
        if stripped_line_lower in (':properties:', ':backlinks:'):
            logging.debug(f"Entering metadata block: {line}")
            in_metadata_block = True
            continue # Skip the block start line itself
        elif stripped_line_lower == ':end:':
            if in_metadata_block:
                logging.debug(f"Exiting metadata block: {line}")
                in_metadata_block = False
                continue # Skip the :END: line
            # else: # Handle potential stray :END: lines? For now, keep them if not in a block.
            #     pass

        # Skip lines if inside a metadata block
        if in_metadata_block:
            logging.debug(f"Skipping line inside metadata block: {line}")
            continue

        # Check for #+title: line specifically and keep it
        if re.match(r'^\s*#\+title:', line, re.IGNORECASE):
            logging.debug(f"Keeping #+title: line: {line}")
            # Keep this line, proceed to append it below
            pass # Explicitly do nothing here, just fall through to append
        # Skip other lines starting with #+ (ignoring leading whitespace and case)
        elif re.match(r'^\s*#\+', line, re.IGNORECASE):
            logging.debug(f"Skipping other #+ line: {line}")
            continue

        # If not skipped, keep the line
        cleaned_lines.append(line)

    # Join the cleaned lines and remove leading/trailing whitespace from the final result
    cleaned_content = '\n'.join(cleaned_lines).strip()
    logging.debug(f"Cleaned content result:\n{cleaned_content}\n---")
    return cleaned_content


# --- Helper function to retrieve node content ---

def _get_node_content(node_data: "OrgNodeData") -> Optional[str]: # Use quotes for forward reference
    """
    Retrieves the full, raw content of a node using its cached filepath, start, and end lines,
    and then cleans it by removing Org metadata.
    Returns the content as a string or None if an error occurs.
    """
    filepath = node_data['filepath']
    start_line = node_data['start_line']
    end_line = node_data['end_line']

    try:
        # Using sync read here for simplicity, consider async if performance critical
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
        except UnicodeDecodeError as ude:
            logging.error(f"Failed to read {filepath} - invalid UTF-8: {ude}")
            return None

        # --- Boundary Check ---
        num_lines = len(lines)
        if not (0 <= start_line < num_lines and start_line < end_line <= num_lines):
             logging.error(f"Invalid line range ({start_line}-{end_line}) for node ID {node_data.get('id', 'N/A')} in file {filepath} (total lines: {num_lines}). File might have changed since caching.")
             return None # Indicate error

        # Extract the relevant lines (inclusive start, exclusive end)
        content_lines = lines[start_line:end_line]
        raw_content = '\n'.join(content_lines)

        # Clean the extracted content
        cleaned_content = _clean_node_content(raw_content)
        return cleaned_content

    except FileNotFoundError:
        logging.error(f"File not found for node ID {node_data.get('id', 'N/A')}: {filepath}")
        return None
    except Exception as e:
        logging.error(f"Error reading file {filepath} for node ID {node_data.get('id', 'N/A')}: {e}", exc_info=True)
        return None


# --- Data Structures for Parsed Nodes ---

class OrgNodeData(TypedDict):
    """Represents the essential data extracted from an Org node file."""
    id: str
    heading: Optional[str] # The determined heading/title/filename
    properties: Dict[str, str]
    # body: str # Removed, we will extract content on demand using start/end lines
    filepath: str # Store the path for content retrieval
    start_line: int # Line index (0-based) where the node content starts (usually heading line)
    end_line: int # Line index (0-based) where the node content ends (exclusive)
    property_block_start_line_index: int # Line index of the :PROPERTIES: line of this node
    property_block_end_line_index: int # Line index of the :END: of this node's properties

class OrgKnowledgeCache(TypedDict):
    """Structure for the in-memory cache using our custom data structure."""
    nodes_by_id: Dict[str, OrgNodeData]
    all_nodes: List[OrgNodeData]


# --- Helper function to format the node index ---

def _format_node_index(cache: OrgKnowledgeCache) -> dict:
    """
    Formats the raw knowledge cache into the structure specified by the HLD.
    Groups nodes by filename.
    """
    files_dict: Dict[str, List[Dict[str, str]]] = {}

    for node_data in cache['all_nodes']:
        filepath = node_data['filepath']
        filename = os.path.basename(filepath)
        heading = node_data.get('heading', 'Unknown Heading') # Use fallback if heading is somehow None
        node_id = node_data['id']

        if filename not in files_dict:
            files_dict[filename] = []

        files_dict[filename].append({"heading": heading, "id": node_id})

    # Convert the dictionary into the final list format
    output_list = []
    for filename, nodes in files_dict.items():
        output_list.append({
            "filename": filename,
            "nodes": nodes
        })

    return {"files": output_list}


# --- Pydantic Models for Tool Outputs and Inputs ---

class ModifyNodeRequest(BaseModel):
    node_id: str
    new_content: str

class CreateNodeRequest(BaseModel):
    heading: str
    content: str
    related_node_ids: List[str] = []

@mcp.tool(
    name="add_backlink",
    description="Adds a bi-directional link between two nodes, updating both the source and target nodes' backlink sections."
)
async def add_backlink(
    source_node_id: Annotated[str, Field(description="The ID of the source node that will contain the link")],
    target_node_id: Annotated[str, Field(description="The ID of the target node to link to")],
    link_description: Annotated[str, Field(description="Text describing the connection")] = ""
) -> dict:
    """Adds a bi-directional link between two nodes"""
    try:
        # Verify both nodes exist
        knowledge_cache = get_org_cache()
        if source_node_id not in knowledge_cache["nodes_by_id"]:
            return {"success": False, "error": f"Source node {source_node_id} not found"}
        if target_node_id not in knowledge_cache["nodes_by_id"]:
            return {"success": False, "error": f"Target node {target_node_id} not found"}

        source_node = knowledge_cache["nodes_by_id"][source_node_id]
        target_node = knowledge_cache["nodes_by_id"][target_node_id]

        _validate_filepath(source_node["filepath"])
        _validate_filepath(target_node["filepath"])

        # --- Add forward link to source node's content body ---
        forward_link_text = f"[[id:{target_node_id}][{link_description or target_node.get('heading', target_node_id)}]]\n"
        source_filepath = source_node["filepath"]
        
        # Read current lines
        with open(source_filepath, "r", encoding="utf-8") as f_read:
            source_lines = f_read.readlines()
        
        # Insert the new link text
        # source_node["end_line"] is the index of the line where the next node starts,
        # or EOF. Inserting here places the link at the very end of the current node's content.
        source_lines.insert(source_node["end_line"], forward_link_text)
        
        # Write the modified lines back, overwriting the file
        with open(source_filepath, "w", encoding="utf-8") as f_write:
            f_write.writelines(source_lines)

        # --- Add backlink to target node's properties ---
        now_timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %a %H:%M]")
        backlink_entry_text = f"{now_timestamp} <- [[id:{source_node_id}]]\n"
        target_filepath = target_node["filepath"]

        # Read current lines for target
        with open(target_filepath, "r", encoding="utf-8") as f_read_target:
            target_lines = f_read_target.readlines()
            
            # This logic needs to be inside the 'with' block where target_lines is defined
            prop_start_idx = target_node["property_block_start_line_index"]
            prop_end_idx = target_node["property_block_end_line_index"]
            
            backlinks_header_found_at = -1
            # Search for existing :BACKLINKS: within this node's properties
            for k in range(prop_start_idx + 1, prop_end_idx):
                # Case-insensitive check for existing backlinks section
                if re.match(r'^\s*:backlinks:\s*$', target_lines[k], re.IGNORECASE):
                    backlinks_header_found_at = k
                    break
            
            if backlinks_header_found_at != -1:
                # :BACKLINKS: section exists, insert new entry after the header
                target_lines.insert(backlinks_header_found_at + 1, backlink_entry_text)
            else:
                # :BACKLINKS: section does not exist, create it before :END:
                target_lines.insert(prop_end_idx, ":BACKLINKS:\n")
                target_lines.insert(prop_end_idx + 1, backlink_entry_text)
            
            # (The existing logic for modifying target_lines based on prop_start_idx, prop_end_idx, etc. remains the same)
            # ...
            
        # Write the modified lines back to target, overwriting the file
        with open(target_filepath, "w", encoding="utf-8") as f_write_target:
            f_write_target.writelines(target_lines)
        
        reload_org_cache() # Reload cache after modifications
        return {"success": True, "source_id": source_node_id, "target_id": target_node_id}
    except Exception as e:
        logging.error(f"Failed to add backlink: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

class BacklinkRequest(BaseModel): 
    source_node_id: str
    target_node_id: str
    link_description: str

# --- Global Cache Management ---
_last_cache_time: float = 0.0
_cache: Optional[OrgKnowledgeCache] = None

class NodeInfo(BaseModel):
    """Information about a single knowledge node within a file."""
    heading: str
    id: str

class FileInfo(BaseModel):
    """Information about nodes within a single file in the knowledge base."""
    filename: str
    nodes: List[NodeInfo]

class ListNodeIndexResponse(BaseModel):
    """Structured response for listing all knowledge nodes in the knowledge base."""
    files: List[FileInfo]


@mcp.tool(
    name="list_knowledge_nodes",
    description="Scans the configured knowledge base directories and returns a structured list of all Org files and the headings within them that have unique IDs. Use this to discover the available information and find specific node IDs to query further for relevant context to incorporate into your answers."
)
async def list_knowledge_nodes() -> ListNodeIndexResponse:
    """
    Retrieves and returns a structured list of all knowledge nodes
    from the directories specified in NODES_DIRECTORIES.
    """
    # Load nodes using the configured directories
    knowledge_cache = load_org_nodes(NODES_DIRECTORIES)
    # Format the output
    formatted_index_data = _format_node_index(knowledge_cache)
    # Validate and return using the Pydantic model
    return ListNodeIndexResponse(**formatted_index_data)


@mcp.tool(
    name="modify_node_content",
    description="Modifies the content of an existing node by replacing its current content with new content."
)
async def modify_node_content(
    node_id: Annotated[str, Field(description="The ID of the node to modify")],
    new_content: Annotated[str, Field(description="The new content to replace the existing content")]
) -> dict:
    """Modifies the content of an existing node"""
    try:
        knowledge_cache = get_org_cache()
        if node_id not in knowledge_cache["nodes_by_id"]:
            return {"success": False, "error": f"Node {node_id} not found"}

        node = knowledge_cache["nodes_by_id"][node_id]
        _validate_filepath(node["filepath"])

        with open(node["filepath"], "r+", encoding="utf-8") as f:
            lines = f.readlines()
            
            # Determine the slice for the node's body content
            # This is from the line after its :PROPERTIES: :END:
            # up to the node's original end_line (exclusive).
            prop_end_idx = node["property_block_end_line_index"]
            body_replace_start_line = prop_end_idx + 1
            body_replace_end_line = node["end_line"]

            # Prepare new content lines
            if not new_content: # Handle empty string case
                new_body_lines = []
            else:
                # Ensure each line of new content ends with a newline for writelines
                new_body_lines = [line + '\n' for line in new_content.splitlines()]
            
            # Replace the old body content lines with the new ones
            lines[body_replace_start_line : body_replace_end_line] = new_body_lines
            
            f.seek(0)
            f.writelines(lines)
            f.truncate()

        reload_org_cache()
        return {"success": True, "node_id": node_id}
    except Exception as e:
        logging.error(f"Failed to modify node content: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool(
    name="create_new_node",
    description="""Creates a new factual Org Mode knowledge node with explicit backlinks to related nodes.
    - PROHIBITED: Do NOT include speculative data or unverified claims
    - FORMAT: Heading (*), :PROPERTIES: block, Org Markup body
    - RELATIONS: Must include EXPLICIT backlink IDs from existing nodes in the knowledge base
    - CONTENT: Must be evidence-based using ONLY data from existing nodes
    
    Auto-generates ID, filename, and validates against fictional entries."""
)
async def create_new_node(request: CreateNodeRequest) -> dict:
    """Create a new node in the knowledge base"""
    try:
        if not NODES_DIRECTORIES:
            return {"success": False, "error": "No nodes directories configured"}

        # Get absolute path of first nodes directory
        base_dir = os.path.abspath(NODES_DIRECTORIES[0])
        filename = _sanitize_filename(request.heading)
        target_filepath = os.path.join(base_dir, filename)
        os.makedirs(base_dir, exist_ok=True)
        
        # Validate generated path explicitly
        _validate_filepath(target_filepath)

        # Validate all related node IDs exist
        knowledge_cache = get_org_cache()
        for related_id in request.related_node_ids:
            if related_id not in knowledge_cache["nodes_by_id"]:
                return {"success": False, "error": f"Related node {related_id} does not exist"}

        # Generate UUID for new node
        new_node_id = str(uuid.uuid4())
        
        # Get current timestamp in Org mode format (e.g., [2025-05-03 Sat 11:33]
        # Standardized timestamp format (same as backlinks)
        created_timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %a %H:%M]") 
        
        # Build "See Also" section
        see_also_links = []
        for node_id in request.related_node_ids:
            node_data = knowledge_cache["nodes_by_id"][node_id]
            heading = node_data.get('heading', node_id)
            see_also_links.append(f"[[id:{node_id}][{heading}]]")
        
        see_also_section = ""
        if see_also_links:
            see_also_section = "\nSee Also:\n" + ", ".join(see_also_links) + "\n"

        # Generate title from filename (without extension)
        title = os.path.splitext(filename)[0].replace('-', ' ').title()
        
        # Build node content with Org-mode syntax
        new_node_content = f"""* {request.heading}
:PROPERTIES:
:ID:       {new_node_id}
:CREATED:  {created_timestamp}
:END:
#+title: {title}

{request.content}{see_also_section}
"""
        # Write to file with proper newline handling
        with open(target_filepath, 'a+', encoding='utf-8') as f:
            # Ensure we start on a new line if file isn't empty
            f.seek(0, 2)  # Move to end of file
            if f.tell() > 0:  # File not empty
                f.write('\n')
            f.write(new_node_content)
            
        # Reload cache to include new node
        reload_org_cache()
        
        # Add backlinks from related nodes to the new node
        for related_id in request.related_node_ids:
            # Refresh cache for fresh line numbers
            current_cache = get_org_cache()
            if related_id not in current_cache["nodes_by_id"]:
                continue  # Skip if node was removed
            related_node = current_cache["nodes_by_id"][related_id]
            
            # Add backlink to new node in related node's file
            _validate_filepath(related_node["filepath"])
            
            with open(related_node["filepath"], "r+", encoding="utf-8") as f:
                lines = f.readlines()
                
                # Find where to insert the backlink
                prop_start_idx = related_node["property_block_start_line_index"]
                prop_end_idx = related_node["property_block_end_line_index"]
                
                backlinks_header_found_at = -1
                # Search for existing :BACKLINKS: within this node's properties
                for k in range(prop_start_idx + 1, prop_end_idx):
                    if lines[k].strip() == ":BACKLINKS:":
                        backlinks_header_found_at = k
                        break
                
                # Add backlink to new node
                now_timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %a %H:%M]")
                backlink_text = f"{now_timestamp} <- [[id:{new_node_id}]]\n"
                
                if backlinks_header_found_at != -1:
                    # :BACKLINKS: section exists, insert new entry after the header
                    lines.insert(backlinks_header_found_at + 1, backlink_text)
                else:
                    # :BACKLINKS: section does not exist, create it before :END:
                    lines.insert(prop_end_idx, ":BACKLINKS:\n")
                    lines.insert(prop_end_idx + 1, backlink_text)
                
                # Write the modified lines back
                f.seek(0)
                f.writelines(lines)
                f.truncate()
        
        return {"success": True, "new_node_id": new_node_id}
        
    except Exception as e:
        logging.error(f"Failed to create new node: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool(
    name="get_knowledge_nodes",
    description="Fetches the cleaned textual content from the configured knowledge base directories for one or more specific node IDs. Provide a list of IDs obtained from 'list_knowledge_nodes'. Returns a dictionary mapping each found ID to its content. Use this to get detailed information about specific topics to incorporate directly into your answers."
)
async def get_knowledge_nodes(
    node_ids: Annotated[list[str], Field(description="A list of unique node IDs to retrieve.")]
) -> dict[str, str]:
    """
    Retrieves the full content for the specified node IDs using cached start/end lines,
    searching across all configured NODES_DIRECTORIES.
    """
    # Load nodes using the configured directories
    # Consider caching this more effectively later if performance is an issue
    knowledge_cache = load_org_nodes(NODES_DIRECTORIES)
    results: Dict[str, str] = {}

    for node_id in node_ids:
        if node_id in knowledge_cache['nodes_by_id']:
            node_data = knowledge_cache['nodes_by_id'][node_id]
            # Use the helper function to get content
            full_content = _get_node_content(node_data)
            if full_content is not None:
                results[node_id] = full_content
            # Errors are logged within _get_node_content
        else:
            # Log IDs requested but not found in cache
            logging.warning(f"Requested node ID not found in cache: {node_id}") # Changed to warning

    # The HLD specifies the output should be dict[str, str]
    # FastMCP will automatically wrap this in List[TextContent] with JSON encoding.
    return results


# Configure basic logging
# Set level to DEBUG to see the cleaning steps
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')


# --- Custom Parsing Logic ---

def _parse_org_file_content(content: str, filepath: str) -> List[OrgNodeData]:
    """
    Parses the content of an Org file to extract all nodes (ID, heading, properties, start/end lines).
    A node is defined by a :PROPERTIES: block containing an :ID:.
    The heading is the nearest preceding '* ' line (or #+title: or filename).
    The node boundaries are determined by headings.
    Returns a list of OrgNodeData objects found.
    """
    nodes_found: List[OrgNodeData] = []
    lines = content.splitlines()
    file_title: Optional[str] = None
    title_line_index: int = -1

    # First pass to find the #+title: and its line index
    for idx, line in enumerate(lines):
        title_match = re.match(r"#\+title:\s*(.*)", line, re.IGNORECASE)
        if title_match:
            file_title = title_match.group(1).strip()
            title_line_index = idx
            # Don't break, continue scanning in case properties appear before title
            # break # Assume only one title per file - Reverted this assumption

    # Second pass to find nodes (ID blocks and associate headings/boundaries)
    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Detect start of a properties block
        if line_stripped == ":PROPERTIES:":
            properties: Dict[str, str] = {}
            node_id: Optional[str] = None
            # prop_block_content: List[str] = [] # Not needed anymore
            prop_end_line_index = -1

            # Find the end of the block and extract properties
            for j in range(i + 1, len(lines)):
                prop_line_stripped = lines[j].strip()
                if prop_line_stripped == ":END:":
                    prop_end_line_index = j
                    break
                # prop_block_content.append(lines[j]) # Not needed
                match = re.match(r":([A-Za-z0-9_]+):\s*(.*)", prop_line_stripped)
                if match:
                    key, value = match.groups()
                    properties[key.upper()] = value.strip()
                    if key.upper() == "ID":
                        node_id = value.strip()
            # else: # Handle case where :END: is missing?
            #     logging.warning(f"Property block starting at line {i+1} in {filepath} seems incomplete.")
            #     continue # Skip this potential node

            if node_id and prop_end_line_index != -1:
                # Determine the heading, start line, and level for this node
                node_heading: Optional[str] = None
                node_start_line: int = 0 # Default to start of file
                node_heading_level: int = 0 # Default level (file level)

                # --- Determine Heading ---
                # Search backwards from the line *before* the :PROPERTIES: block
                # to find the nearest preceding Org heading (*, **, etc.).
                # This heading is considered the "owner" of the properties block.
                found_heading = False
                for k in range(i - 1, -1, -1):
                    potential_heading_line = lines[k].strip()
                    heading_match = re.match(r"^(\*+)\s+(.*)", potential_heading_line) # Capture stars for level
                    if heading_match:
                        stars, heading_text = heading_match.groups()
                        node_heading = heading_text.strip()
                        node_start_line = k
                        node_heading_level = len(stars)
                        found_heading = True
                        break # Found the nearest preceding heading

                # If no '*' heading found before properties, associate with file title or filename
                if not found_heading:
                    # Check if #+title: exists AND is BEFORE the properties block
                    if file_title is not None and title_line_index != -1 and title_line_index < i:
                        node_heading = file_title
                        node_start_line = title_line_index # Start from the title line
                        node_heading_level = 0
                    else:
                        # No preceding heading or title found before the properties block.
                        # Use file_title for heading text if available, otherwise filename.
                        if file_title is not None:
                            node_heading = file_title
                        else:
                            node_heading = os.path.splitext(os.path.basename(filepath))[0]

                        # Start the node content from the :PROPERTIES: line itself.
                        node_start_line = i
                        node_heading_level = 0 # File level

                # Determine end line: line before the next heading of same or lesser level, or EOF
                node_end_line = len(lines) # Default to end of file
                for k in range(prop_end_line_index + 1, len(lines)):
                    line_k_stripped = lines[k].strip()
                    next_heading_match = re.match(r"^(\*+)\s+", line_k_stripped)
                    if next_heading_match:
                        next_heading_level = len(next_heading_match.group(1))
                        # If the next heading is same or higher level (smaller or equal number of stars)
                        if next_heading_level <= node_heading_level:
                            node_end_line = k
                            break # Found the boundary

                # Append the found node data
                nodes_found.append(OrgNodeData(
                    id=node_id,
                    heading=node_heading,
                    properties=properties,
                    filepath=filepath,
                    start_line=node_start_line,
                    end_line=node_end_line,
                    property_block_start_line_index=i, # i is the line index of :PROPERTIES:
                    property_block_end_line_index=prop_end_line_index
                ))

    if not nodes_found:
         logging.warning(f"No nodes with ':ID:' property found in {filepath}")

    return nodes_found


def get_org_cache() -> OrgKnowledgeCache:
    global _last_cache_time, _cache
    current_time = time.time()
    
    if not _cache or current_time - _last_cache_time > 300:  # 5 min cache
        _cache = load_org_nodes(NODES_DIRECTORIES)
        _last_cache_time = current_time
    return _cache

def reload_org_cache() -> None:
    global _cache, _last_cache_time
    _cache = load_org_nodes(NODES_DIRECTORIES)
    _last_cache_time = time.time() # Reset cache timer on explicit reload

def load_org_nodes(nodes_dirs: List[str]) -> OrgKnowledgeCache:
    """
    Scans one or more directories for .org files, parses them using custom logic,
    and stores the extracted data in dictionaries, handling duplicates across directories.
    """
    nodes_by_id: Dict[str, OrgNodeData] = {}
    all_nodes: List[OrgNodeData] = []
    total_files_found = 0

    for nodes_dir in nodes_dirs:
        if not os.path.isdir(nodes_dir):
            logging.warning(f"Specified nodes directory not found, skipping: {nodes_dir}")
            continue

        org_files = glob.glob(os.path.join(nodes_dir, "*.org"))
        logging.info(f"Found {len(org_files)} .org files in directory: {nodes_dir}")
        total_files_found += len(org_files)

        for filepath in org_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parser now returns a list of nodes found in the file
                parsed_nodes_in_file = _parse_org_file_content(content, filepath)

                if not parsed_nodes_in_file:
                    # Warning logged in _parse_org_file_content if no IDs found
                    continue

                # Process each node found in the current file
                for node_data in parsed_nodes_in_file:
                    node_id = node_data['id'] # ID is guaranteed by parser logic finding a node

                    if node_id in nodes_by_id:
                        # Handle duplicate IDs across different files
                        logging.warning(f"Duplicate ID '{node_id}' found in {filepath}. It was already loaded from {nodes_by_id[node_id]['filepath']}. Skipping node from {filepath}.")
                        continue # Skip this specific node, keep the first one encountered

                    # Add the valid, unique node to our caches
                    nodes_by_id[node_id] = node_data
                    all_nodes.append(node_data)

            except Exception as e:
                # Log errors related to file reading or unexpected parsing issues
                logging.error(f"Failed to process file {filepath}: {e}", exc_info=True)

    logging.info(f"Finished loading. Total unique nodes found: {len(nodes_by_id)} from {total_files_found} files across specified directories.")
    return {"nodes_by_id": nodes_by_id, "all_nodes": all_nodes}




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Org-Node Knowledge Base MCP Server")
    parser.add_argument(
        '--nodes-dirs',
        metavar='DIR',
        type=str,
        nargs='+',  # Accept one or more directory paths
        default=["nodes"], # Default list if argument is not provided
        help="One or more paths to directories containing the Org-mode knowledge base files (default: ['nodes'])"
    )
    # Add arguments for transport, host, port if needed later
    # parser.add_argument('--transport', default='stdio', choices=['stdio', 'sse'], help='MCP transport type')
    # parser.add_argument('--host', default='0.0.0.0', help='Host for SSE transport')
    # parser.add_argument('--port', type=int, default=8000, help='Port for SSE transport')

    args = parser.parse_args()

    # Update the global configuration variable with the parsed directories
    # This needs to happen BEFORE any tool relying on it might be called
    NODES_DIRECTORIES = args.nodes_dirs
    abs_dirs = [os.path.abspath(d) for d in NODES_DIRECTORIES]
    print(f"INFO: Using nodes directories: {abs_dirs}")
    logging.info(f"Configured nodes directories: {abs_dirs}")


    # Default run mode is STDIO transport
    # TODO: Add logic to select transport based on args if needed
    mcp.run()

    # Example for SSE transport based on args (if added)
    # if args.transport == 'sse':
    #     print(f"Starting server with SSE transport on http://{args.host}:{args.port}/sse")
    #     mcp.run(transport="sse", host=args.host, port=args.port)
    # else: # Default to stdio
    #     print("Starting server with STDIO transport")
