"""
Question Set Group management service.

This module handles all operations related to question set grouping:
- Loading groups from QuestionSetGroup.json
- Saving groups to QuestionSetGroup.json
- Managing question set assignments to groups
- Auto-generating "Others" group for ungrouped question sets
"""

import json
from pathlib import Path
from typing import Optional

from config.constants import QUESTION_SET_GROUP_FILE


class QuestionSetGroupService:
    """
    Service for managing question set groups.
    
    Features:
    - Persistent storage in QuestionSetGroup.json
    - Automatic "Others" group for ungrouped question sets
    - Per-group question set management
    - Group CRUD operations
    
    File Format (QuestionSetGroup.json):
        {
            "groups": {
                "JEE Main Practice": {
                    "display_name": "JEE Main Practice",
                    "question_sets": ["Are You Ready", "Brush Up Series"],
                    "color": "#3b82f6"
                },
                "JEE Advanced Practice": {...},
                "Monthly Test Drives": {...}
            }
        }
    """
    
    # Default groups to initialize with
    DEFAULT_GROUPS = [
        "JEE Main Practice",
        "JEE Advanced Practice",
        "Monthly Test Drives",
    ]
    
    # Default colors for groups (cycle through as needed)
    GROUP_COLORS = [
        "#3b82f6",  # Blue
        "#8b5cf6",  # Purple
        "#ec4899",  # Pink
        "#f59e0b",  # Amber
        "#10b981",  # Emerald
        "#06b6d4",  # Cyan
        "#6366f1",  # Indigo
        "#ef4444",  # Red
    ]
    
    def __init__(self, config_file: Path = QUESTION_SET_GROUP_FILE):
        """
        Initialize the question set group service.
        
        Args:
            config_file: Path to question set group configuration file
        """
        self.config_file = config_file
        self.groups: dict[str, dict] = {}  # group_name -> {display_name, question_sets, color}
        
        # Load existing groups from file
        self.load_groups()
    
    def load_groups(self) -> None:
        """
        Load groups from configuration file.
        
        If file doesn't exist, initialize with default groups.
        If file is invalid, start fresh with defaults.
        """
        if not self.config_file.exists():
            self._initialize_default_groups()
            self.save_groups()
            return
        
        try:
            data = json.loads(self.config_file.read_text(encoding="utf-8"))
            self.groups = data.get("groups", {})
            # If file exists but is empty or missing groups, initialize defaults once
            if not self.groups:
                self._initialize_default_groups()
                self.save_groups()
        
        except json.JSONDecodeError:
            # Corrupted file - start fresh
            self._initialize_default_groups()
            self.save_groups()
        except Exception:
            # Any other error - start fresh
            self._initialize_default_groups()
            self.save_groups()
    
    def _initialize_default_groups(self) -> None:
        """Initialize with default groups."""
        self.groups = {}
        for i, group_name in enumerate(self.DEFAULT_GROUPS):
            self.groups[group_name] = {
                "display_name": group_name,
                "question_sets": [],
                "color": self.GROUP_COLORS[i % len(self.GROUP_COLORS)],
            }
    
    def _get_saved_groups_from_file(self) -> dict:
        """Get groups currently saved in file (without defaults)."""
        if not self.config_file.exists():
            return {}
        try:
            data = json.loads(self.config_file.read_text(encoding="utf-8"))
            return data.get("groups", {})
        except:
            return {}
    
    def save_groups(self) -> None:
        """
        Save groups to configuration file.
        
        Creates parent directories if needed.
        """
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        payload = {"groups": self.groups}
        
        self.config_file.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
    
    def get_all_groups(self) -> dict[str, dict]:
        """
        Get all groups.
        
        Returns:
            Dict mapping group names to group data
        """
        return self.groups.copy()
    
    def get_group(self, group_name: str) -> Optional[dict]:
        """
        Get specific group data.
        
        Args:
            group_name: Name of the group
            
        Returns:
            Group data dict or None if not found
        """
        return self.groups.get(group_name)
    
    def get_question_sets_in_group(self, group_name: str) -> list[str]:
        """
        Get all question sets in a group.
        
        Args:
            group_name: Name of the group
            
        Returns:
            List of question set names
        """
        group = self.groups.get(group_name)
        if group:
            return group.get("question_sets", [])
        return []
    
    def get_others_group(self, all_question_sets: list[str]) -> dict:
        """
        Generate "Others" group from question sets not in any group.
        
        Args:
            all_question_sets: All question sets in the workbook
            
        Returns:
            Dict with "display_name", "question_sets", "color" keys
        """
        # Collect all question sets in groups
        grouped_sets = set()
        for group_data in self.groups.values():
            grouped_sets.update(group_data.get("question_sets", []))
        
        # Find ungrouped question sets
        others = [qs for qs in all_question_sets if qs not in grouped_sets]
        
        return {
            "display_name": "Others",
            "question_sets": others,
            "color": "#94a3b8",  # Gray for Others
        }
    
    def add_question_set_to_group(self, group_name: str, question_set_name: str) -> bool:
        """
        Add a question set to a group.
        
        Args:
            group_name: Name of the group
            question_set_name: Name of the question set to add
            
        Returns:
            True if successful, False if group doesn't exist
        """
        if group_name not in self.groups:
            return False
        
        # Skip "Others" group
        if group_name == "Others":
            return False
        
        question_sets = self.groups[group_name].get("question_sets", [])
        if question_set_name not in question_sets:
            question_sets.append(question_set_name)
            self.groups[group_name]["question_sets"] = question_sets
            self.save_groups()
        
        return True
    
    def remove_question_set_from_group(self, group_name: str, question_set_name: str) -> bool:
        """
        Remove a question set from a group.
        
        Args:
            group_name: Name of the group
            question_set_name: Name of the question set to remove
            
        Returns:
            True if successful, False if group doesn't exist
        """
        if group_name not in self.groups:
            return False
        
        # Skip "Others" group
        if group_name == "Others":
            return False
        
        question_sets = self.groups[group_name].get("question_sets", [])
        if question_set_name in question_sets:
            question_sets.remove(question_set_name)
            self.groups[group_name]["question_sets"] = question_sets
            self.save_groups()
        
        return True
    
    def move_question_set(self, question_set_name: str, from_group: str, to_group: str) -> bool:
        """
        Move a question set from one group to another.
        
        Args:
            question_set_name: Name of the question set to move
            from_group: Name of the source group
            to_group: Name of the destination group
            
        Returns:
            True if successful, False otherwise
        """
        # Can remove from Others (it's auto-generated)
        if from_group != "Others":
            if not self.remove_question_set_from_group(from_group, question_set_name):
                return False
        
        # Can't add to Others
        if to_group == "Others":
            return False
        
        return self.add_question_set_to_group(to_group, question_set_name)
    
    def create_group(self, group_name: str) -> bool:
        """
        Create a new group.
        
        Args:
            group_name: Name for the new group
            
        Returns:
            True if successful, False if group already exists
        """
        if group_name in self.groups or group_name == "Others":
            return False
        
        color_index = len(self.groups) % len(self.GROUP_COLORS)
        self.groups[group_name] = {
            "display_name": group_name,
            "question_sets": [],
            "color": self.GROUP_COLORS[color_index],
        }
        self.save_groups()
        return True
    
    def delete_group(self, group_name: str) -> bool:
        """
        Delete a group and move its question sets to Others.
        
        Args:
            group_name: Name of the group to delete
            
        Returns:
            True if successful, False if group doesn't exist or is "Others"
        """
        if group_name not in self.groups or group_name == "Others":
            return False
        
        del self.groups[group_name]
        self.save_groups()
        return True
    
    def rename_group(self, old_name: str, new_name: str) -> bool:
        """
        Rename a group.
        
        Args:
            old_name: Current group name
            new_name: New group name
            
        Returns:
            True if successful, False if old group doesn't exist or new name is taken
        """
        if old_name not in self.groups or old_name == "Others":
            return False
        
        if new_name in self.groups or new_name == "Others":
            return False
        
        group_data = self.groups.pop(old_name)
        group_data["display_name"] = new_name
        self.groups[new_name] = group_data
        self.save_groups()
        return True
