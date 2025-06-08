#!/bin/bash

cd /home/anthony/projects/mcp/org-node-mcp/

source ./.venv/bin/activate
python3 server.py --nodes-dir /home/anthony/projects/personal/org-nodes/
