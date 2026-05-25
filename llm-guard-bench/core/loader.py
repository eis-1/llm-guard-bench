import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class AttackLoader:
    """Loads and manages attack prompts from configuration files."""

    @staticmethod
    def load_prompts(
        file_path: str, categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Safely load and parse prompts from a JSON file with optional category filtering.

        Args:
            file_path: Path to the prompts JSON file.
            categories: Optional list of attack categories to filter by.
                       If None, all prompts are returned.

        Returns:
            List of prompt dictionaries matching the specified criteria.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            json.JSONDecodeError: If the file contains invalid JSON.
            ValueError: If the file is empty or does not contain a valid prompts array.
        """
        file_path_obj: Path = Path(file_path)

        # Validate file existence
        if not file_path_obj.exists():
            raise FileNotFoundError(f"Prompts file not found: {file_path}")

        # Check if file is empty
        if file_path_obj.stat().st_size == 0:
            raise ValueError(f"Prompts file is empty: {file_path}")

        try:
            with open(file_path_obj, "r", encoding="utf-8") as f:
                data: Any = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in prompts file: {file_path}",
                e.doc,
                e.pos,
            ) from e

        # Validate data structure
        if not isinstance(data, dict) or "prompts" not in data:
            raise ValueError(
                "Prompts file must contain a 'prompts' key with a list value"
            )

        prompts: Any = data.get("prompts")

        if not isinstance(prompts, list):
            raise ValueError("'prompts' field must be a list")

        if len(prompts) == 0:
            logger.warning(f"Prompts file contains an empty prompts list: {file_path}")
            return []

        # Filter by categories if provided
        filtered_prompts: List[Dict[str, Any]] = []

        if categories is None:
            # Return all prompts if no categories specified
            filtered_prompts = prompts
        else:
            # Filter prompts by category
            category_set: set = set(categories)
            for prompt in prompts:
                if isinstance(prompt, dict):
                    prompt_category: Optional[str] = prompt.get("category")
                    if prompt_category in category_set:
                        filtered_prompts.append(prompt)
                else:
                    logger.warning(
                        f"Skipping invalid prompt entry (not a dict): {prompt}"
                    )

        logger.info(
            f"Loaded {len(filtered_prompts)} prompts from {file_path} "
            f"(categories: {categories if categories else 'all'})"
        )

        return filtered_prompts
