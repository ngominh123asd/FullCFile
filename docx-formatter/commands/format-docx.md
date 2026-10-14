---
description: Bidirectionally convert and sync files between DOCX and Markdown
---

## Context
You have access to a script `docx_smart_converter.py` that handles two-way conversion between Markdown and Word documents with smart conflict resolution.

## Your task
The user wants to convert or synchronize files using the `/format-docx` command.
1. Check the user's request and attached files:
   - If the user attached multiple files, did not specify a single file name, or wants to process the workspace: you MUST run the script with **no arguments** (or passing `.`) so it scans and converts all files in bulk!
   - If the user explicitly specified a single file path or tag name: run the script passing that specific file/tag.
2. Check if `python-docx` is installed in the current environment. If not, install it via `pip install python-docx` first.
3. Execute the python script located at `.claude/plugins/docx-formatter/docx_smart_converter.py`:
   - Bulk scan/convert mode: `python .claude/plugins/docx-formatter/docx_smart_converter.py`
   - Single file/tag mode: `python .claude/plugins/docx-formatter/docx_smart_converter.py <file_or_tag>`
4. The script is extremely smart:
   - MD files are converted to DOCX and placed in the `docx/` folder.
   - DOCX files are converted to MD and placed in the `markdown/` folder.
   - If both formats exist, it compares their last modified timestamps (`mtime`), selects the newer one as the source of truth, and performs the correct conversion.
5. Provide a summary of all conversions that occurred, listing the files generated in their respective `docx/` and `markdown/` folders.
