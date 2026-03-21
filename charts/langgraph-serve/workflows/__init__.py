"""Workflow registry with auto-discovery.

Scans this package for subpackages that export a `workflow` attribute
(an instance of utils.Workflow). No manual registration needed.

To add a new workflow:
  1. Create a new package (e.g. workflows/my_workflow/)
  2. Add prompt .txt files in workflows/my_workflow/prompts/
  3. Write a graph.py with your graph builder
  4. In __init__.py, subclass Workflow, implement build(), and export:
       workflow = MyWorkflow()
"""

import importlib
import logging
import pkgutil

from workflow import Workflow

logger = logging.getLogger(__name__)

WORKFLOWS: dict[str, Workflow] = {}

for _finder, _name, _is_pkg in pkgutil.iter_modules(__path__):
    if not _is_pkg:
        continue
    try:
        _mod = importlib.import_module(f"workflows.{_name}")
    except Exception:
        logger.exception("Failed to import workflow package '%s'", _name)
        continue
    _wf = getattr(_mod, "workflow", None)
    if isinstance(_wf, Workflow):
        WORKFLOWS[_wf.name] = _wf
    else:
        logger.warning(
            "Package 'workflows.%s' has no 'workflow' attribute (expected Workflow instance)", _name,
        )
