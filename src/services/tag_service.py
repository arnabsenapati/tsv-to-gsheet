"""
Tag management service.

This module handles all operations related to question group tagging:
- Loading tags from configuration file
- Saving tags to configuration file
- Color assignment for tags
- Tag filtering and selection
"""

import json
from pathlib import Path
from typing import Optional

from config.constants import TAG_COLORS
from services.db_service import DatabaseService


class TagService:
    """
    Service for managing question group tags.
    
    Features:
    - Persistent storage in tags.cfg JSON file
    - Automatic color assignment from palette
    - Per-group tag management
    - Color consistency across sessions
    
    File Format (tags.cfg):
        {
            "group_tags": {
                "Electrostatics": ["JEE", "NEET"],
                "Magnetism": ["JEE", "CUET"]
            },
            "tag_colors": {
                "JEE": "#2563eb",
                "NEET": "#10b981",
                "CUET": "#f59e0b"
            }
        }
    """
    
    def __init__(self, config_file: Path | None = None, available_colors: list[str] = None, db_service: DatabaseService | None = None):
        """
        Initialize the tag service.
        
        Args:
            config_file: Path to tags configuration file (default: tags.cfg)
            available_colors: List of hex color codes for tag palette (default: TAG_COLORS)
        """
        self.config_file = config_file
        self.db_service = db_service
        self.available_colors = available_colors or TAG_COLORS
        
        # Storage for tags and colors
        self.group_tags: dict[str, list[str]] = {}  # group_name -> [tag1, tag2, ...]
        self.tag_colors: dict[str, str] = {}  # tag_name -> "#hexcolor"
        
        # Load existing tags from file
        self.load_tags()
    
    def load_tags(self) -> None:
        """
        Load group tags and colors from configuration file.
        
        If file doesn't exist or is invalid JSON, initializes empty storage.
        Silently handles errors to prevent crashes on startup.
        """
        data = {}
        if self.db_service:
            data = self.db_service.load_config("TagsConfig")
        self.group_tags = data.get("group_tags", {})
        self.tag_colors = data.get("tag_colors", {})
    
    def save_tags(self) -> None:
        """
        Save group tags and colors to configuration file.
        
        Writes JSON with 2-space indentation for readability.
        Creates parent directories if needed.
        """
        payload = {
            "group_tags": self.group_tags,
            "tag_colors": self.tag_colors,
        }
        if self.db_service:
            self.db_service.save_config("TagsConfig", payload)
    
    def get_group_tags(self, group_name: str) -> list[str]:
        """
        Get tags for a specific group.
        
        Args:
            group_name: Name of the question group
            
        Returns:
            List of tag names (empty list if group has no tags)
        """
        return self.group_tags.get(group_name, [])
    
    def set_group_tags(self, group_name: str, tags: list[str]) -> None:
        """
        Set tags for a specific group.
        
        Args:
            group_name: Name of the question group
            tags: List of tag names to assign
        """
        if tags:
            self.group_tags[group_name] = tags
        else:
            # Remove group from dict if no tags
            self.group_tags.pop(group_name, None)
        
        self.save_tags()
    
    def add_tag_to_group(self, group_name: str, tag: str) -> None:
        """
        Add a single tag to a group (if not already present).
        
        Args:
            group_name: Name of the question group
            tag: Tag name to add
        """
        if group_name not in self.group_tags:
            self.group_tags[group_name] = []
        
        if tag not in self.group_tags[group_name]:
            self.group_tags[group_name].append(tag)
            self.save_tags()
    
    def remove_tag_from_group(self, group_name: str, tag: str) -> None:
        """
        Remove a single tag from a group.
        
        Args:
            group_name: Name of the question group
            tag: Tag name to remove
        """
        if group_name in self.group_tags:
            if tag in self.group_tags[group_name]:
                self.group_tags[group_name].remove(tag)
                
                # Clean up empty groups
                if not self.group_tags[group_name]:
                    del self.group_tags[group_name]
                
                self.save_tags()
    
    def get_or_assign_tag_color(self, tag: str) -> str:
        """
        Get existing color for a tag or assign a new one.
        
        Colors are assigned from available_colors palette in a cycling manner.
        Once assigned, colors are persistent across sessions.
        
        Args:
            tag: Tag name
            
        Returns:
            Hex color code (e.g., "#2563eb")
        """
        if tag not in self.tag_colors:
            # Assign next color from palette (cycling through)
            color_index = len(self.tag_colors) % len(self.available_colors)
            self.tag_colors[tag] = self.available_colors[color_index]
            self.save_tags()
        
        return self.tag_colors[tag]
    
    def get_all_tags(self) -> list[str]:
        """
        Get list of all unique tags across all groups.
        
        Returns:
            Sorted list of tag names
        """
        all_tags = set()
        for tags in self.group_tags.values():
            all_tags.update(tags)
        return sorted(all_tags)
    
    def get_groups_with_tag(self, tag: str) -> list[str]:
        """
        Find all groups that have a specific tag.
        
        Args:
            tag: Tag name to search for
            
        Returns:
            List of group names that have this tag
        """
        matching_groups = []
        for group_name, tags in self.group_tags.items():
            if tag in tags:
                matching_groups.append(group_name)
        return matching_groups
    
    def get_groups_with_any_tag(self, tags: list[str]) -> list[str]:
        """
        Find all groups that have ANY of the specified tags.
        
        Args:
            tags: List of tag names to search for
            
        Returns:
            List of group names that have at least one of the tags
        """
        if not tags:
            return []
        
        matching_groups = []
        tag_set = set(tags)
        
        for group_name, group_tags in self.group_tags.items():
            if any(tag in tag_set for tag in group_tags):
                matching_groups.append(group_name)
        
        return matching_groups
    
    def get_groups_with_all_tags(self, tags: list[str]) -> list[str]:
        """
        Find all groups that have ALL of the specified tags.
        
        Args:
            tags: List of tag names to search for
            
        Returns:
            List of group names that have all of the tags
        """
        if not tags:
            return []
        
        matching_groups = []
        tag_set = set(tags)
        
        for group_name, group_tags in self.group_tags.items():
            if tag_set.issubset(set(group_tags)):
                matching_groups.append(group_name)
        
        return matching_groups
    
    def rename_tag(self, old_name: str, new_name: str) -> None:
        """
        Rename a tag across all groups.
        
        Args:
            old_name: Current tag name
            new_name: New tag name
        """
        # Update all groups
        for group_name, tags in self.group_tags.items():
            if old_name in tags:
                tags[tags.index(old_name)] = new_name
        
        # Update color mapping
        if old_name in self.tag_colors:
            self.tag_colors[new_name] = self.tag_colors.pop(old_name)
        
        self.save_tags()
    
    def delete_tag(self, tag: str) -> None:
        """
        Delete a tag from all groups and color mapping.
        
        Args:
            tag: Tag name to delete
        """
        # Remove from all groups
        for group_name, tags in list(self.group_tags.items()):
            if tag in tags:
                tags.remove(tag)
                # Clean up empty groups
                if not tags:
                    del self.group_tags[group_name]
        
        # Remove color mapping
        self.tag_colors.pop(tag, None)
        
        self.save_tags()
    
    def clear_all_tags(self) -> None:
        """Clear all tags and colors (useful for testing or reset)."""
        self.group_tags = {}
        self.tag_colors = {}
        self.save_tags()


# Singleton instance for easy access throughout application
_tag_service_instance: Optional[TagService] = None


def get_tag_service() -> TagService:
    """
    Get the singleton TagService instance.
    
    Returns:
        Shared TagService instance
    """
    global _tag_service_instance
    if _tag_service_instance is None:
        _tag_service_instance = TagService()
    return _tag_service_instance
