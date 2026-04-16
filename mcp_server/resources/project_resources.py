from __future__ import annotations

# resource://project/{project_id}/prd
# resource://project/{project_id}/adr
# resource://project/{project_id}/memory
# Full resource handlers wired in Session 02 when PostgreSQL memory layer ships.

PROJECT_RESOURCE_TEMPLATE = "project://{project_id}/{artifact}"