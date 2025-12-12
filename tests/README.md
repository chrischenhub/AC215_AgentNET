# Missing Test Coverage

This document outlines the current state of test coverage for the AgentNET project. It highlights modules and functions that are not currently covered by automated tests.

## completely Uncovered Modules

The following directories are currently excluded from the test suite:

-   `src/datapipeline/`: All data ingestion and processing scripts.
-   `src/deployment/`: All deployment scripts (Kubernetes, Docker, etc.).

## Partially Covered Modules (`src/models`)

The `src/models` directory has approximately **70%** test coverage. Below is a breakdown of specific functions and logic that lack coverage.

### `src/models/RAG.py`
**Coverage: ~62%**

-   **Catalog Management**:
    -   `clear_persist_dir`: Totally uncovered.
    -   `index_chunks`: Totally uncovered.
    -   `try_load_vectordb`: Totally uncovered.
    -   `is_persist_dir_empty`: Partially uncovered.
    -   `ensure_vectordb`: Partial coverage of re-indexing logic.
-   **CLI & Entry Point**:
    -   `parse_args`: Totally uncovered.
    -   `main`: Totally uncovered.
-   **Search Logic**:
    -   `score_and_rank_servers`: Some edge cases in scoring/ranking.
    -   `search_servers`: Some optional parameter branches.

### `src/models/main.py`
**Coverage: ~63%**

-   **User Interaction**:
    -   `prompt_for_selection`: Error handling for invalid inputs is not fully tested.
-   **Workflow Execution**:
    -   `run_workflow`: Partial coverage. Missing strict error handling branches and some direct mode paths.
-   **CLI & Entry Point**:
    -   `parse_args`: Totally uncovered.
    -   `main`: Totally uncovered.

### `src/models/notion_agent.py`
**Coverage: ~61%**

-   **Utilities**:
    -   `sanitize_url_for_logs`: Totally uncovered.
    -   `serialize_agent_result`: Partial coverage of complex object serialization.
-   **Agent Execution**:
    -   `run_smithery_task`: Partial coverage. Several branches for optional parameters and error handling are missing.
    -   `resolve_instruction`: Some logical branches for instruction refinement.
-   **CLI & Entry Point**:
    -   `parse_args`: Totally uncovered.
    -   `main_async`: Totally uncovered.
    -   `main`: Totally uncovered.

### `src/models/app.py`
**Coverage: ~91%**

-   **Configuration**:
    -   `_parse_origins`: Edge case for empty string not fully hit.
    -   `create_app`: Simple factory not explicitly tested (trivial).
-   **Entry Point**:
    -   `if __name__ == "__main__":` block is excluded.
-   **Error Handling**:
    -   `api_search` & `api_execute`: Exception handlers that surface 500/400 errors are marked `pragma: no cover` but technically untrained.

### `src/models/workflow.py`
**Coverage: ~90%**

-   **Error Handling**:
    -   `derive_mcp_url`: Error case for invalid child links.
    -   `extract_server_slug`: Error case for malformed strings.
    -   `execute_mcp_workflow`: Error case for missing instructions.
    -   `_complete_direct_answer`: Error handling branches.
