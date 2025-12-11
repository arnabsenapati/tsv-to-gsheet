"""
Data management service for questions and chapters.

This module handles all operations related to question and chapter data:
- Loading and parsing chapter groupings from JSON files
- Managing question data from Excel workbooks
- Chapter-to-group assignment and lookup
- Grouping similar question sets
"""

import json
import re
from pathlib import Path
from typing import Optional

import pandas as pd

from config.constants import MAGAZINE_GROUPING_MAP
from services.db_service import DatabaseService


class DataService:
    """
    Service for managing question and chapter data.
    
    Features:
    - Load canonical chapter lists from JSON
    - Manage chapter groupings (groups -> chapters mapping)
    - Build reverse lookup (chapter -> group mapping)
    - Auto-assign chapters to appropriate groups
    - Extract group keys from question set names
    
    Chapter Grouping File Format:
        {
            "canonical_order": ["Electrostatics", "Magnetism", ...],
            "groups": {
                "Electrostatics": ["Electric Charge", "Coulomb's Law", ...],
                "Magnetism": ["Magnetic Field", "Ampere's Law", ...]
            }
        }
    """
    
    def __init__(self, current_magazine: str = "", db_service: DatabaseService | None = None):
        """
        Initialize the data service.
        
        Args:
            current_magazine: Current magazine name (for loading appropriate grouping file)
        """
        self.db_service = db_service
        self.current_magazine = current_magazine
        self.canonical_chapters: list[str] = []
        self.chapter_groups: dict[str, list[str]] = {}  # group -> [chapters]
        self.chapter_lookup: dict[str, str] = {}  # chapter -> group
        
        # Load grouping for current magazine
        if current_magazine:
            self.load_grouping_for_magazine(current_magazine)
    
    def load_canonical_chapters(self, key: str) -> list[str]:
        """Load canonical chapter list from DB config."""
        if self.db_service:
            data = self.db_service.load_config(key)
            if data:
                return data.get("canonical_order", [])
        return []
    
    def load_chapter_grouping(self, key: str) -> dict[str, list[str]]:
        """
        Load chapter grouping from DB config.
        
        Creates default structure if empty:
        - Adds canonical chapters as empty groups
        - Adds "Others" group for unmatched chapters
        - Removes duplicates while preserving order
        """
        data = {}
        if self.db_service:
            data = self.db_service.load_config(key)
        groups = data.get("groups", {}) if data else {}
        
        # Ensure all canonical chapters have entries
        for group in self.canonical_chapters:
            groups.setdefault(group, [])
        
        # Ensure "Others" group exists
        groups.setdefault("Others", [])
        
        # Remove duplicates while preserving order
        for key, values in list(groups.items()):
            seen = set()
            unique = []
            for value in values:
                if value not in seen:
                    unique.append(value)
                    seen.add(value)
            groups[key] = unique
        
        # Rebuild chapter lookup
        self.rebuild_chapter_lookup(groups)
        
        return groups
    
    def load_grouping_for_magazine(self, magazine_name: str) -> None:
        """
        Load chapter grouping based on magazine name.
        
        Updates canonical_chapters, chapter_groups, and chapter_lookup.
        
        Args:
            magazine_name: Magazine name (e.g., "physics for you", "chemistry today")
        """
        # Get appropriate grouping file for magazine
        key = ""
        norm = magazine_name.lower()
        if "physics" in norm:
            key = "PhysicsChapterGrouping"
        elif "chemistry" in norm:
            key = "ChemistryChapterGrouping"
        elif "mathematics" in norm:
            key = "MathematicsChapterGrouping"
        else:
            key = "PhysicsChapterGrouping"
        
        self.current_magazine = magazine_name
        self.canonical_chapters = self.load_canonical_chapters(key)
        self.chapter_groups = self.load_chapter_grouping(key)
    
    def save_chapter_grouping(self, key: str) -> None:
        """Save current chapter grouping to DB config."""
        payload = {
            "canonical_order": self.canonical_chapters,
            "groups": self.chapter_groups,
        }
        if self.db_service:
            self.db_service.save_config(key, payload)
    
    def get_ordered_groups(self) -> list[str]:
        """
        Get group names in canonical order.
        
        Returns canonical chapters first, then "Others", then remaining groups.
        
        Returns:
            Ordered list of group names
        """
        ordered = []
        
        # Add canonical chapters that exist in groups
        for chapter in self.canonical_chapters:
            if chapter in self.chapter_groups:
                ordered.append(chapter)
        
        # Add "Others" if exists
        if "Others" in self.chapter_groups and "Others" not in ordered:
            ordered.append("Others")
        
        # Add remaining groups
        for group in sorted(self.chapter_groups.keys()):
            if group not in ordered:
                ordered.append(group)
        
        return ordered
    
    def rebuild_chapter_lookup(self, groups: dict[str, list[str]]) -> None:
        """
        Rebuild reverse lookup from chapter name to group name.
        
        Args:
            groups: Dict mapping group names to chapter lists
        """
        self.chapter_lookup = {}
        for group_name, chapters in groups.items():
            for chapter in chapters:
                self.chapter_lookup[chapter] = group_name
    
    def match_chapter_group(self, chapter: str) -> str:
        """
        Match a chapter name to its group.
        
        Uses exact match from chapter_lookup. If not found, returns the
        original chapter name (which will be placed in "Others").
        
        Args:
            chapter: Raw chapter name from data
            
        Returns:
            Group name that this chapter belongs to
        """
        return self.chapter_lookup.get(chapter, chapter)
    
    def auto_assign_chapters(self, chapters: list[str]) -> None:
        """
        Auto-assign new chapters to appropriate groups.
        
        Uses fuzzy matching against canonical chapters to find best fit.
        Unmatched chapters are added to "Others" group.
        
        Args:
            chapters: List of chapter names to assign
        """
        for chapter in chapters:
            if chapter in self.chapter_lookup:
                continue  # Already assigned
            
            # Try to find matching canonical chapter
            normalized_chapter = self._normalize_label(chapter)
            best_match = None
            best_score = 0
            
            for canonical in self.canonical_chapters:
                normalized_canonical = self._normalize_label(canonical)
                
                # Simple word overlap scoring
                chapter_words = set(normalized_chapter.split())
                canonical_words = set(normalized_canonical.split())
                overlap = len(chapter_words & canonical_words)
                
                if overlap > best_score:
                    best_score = overlap
                    best_match = canonical
            
            # Assign to best match if score is good enough, otherwise to "Others"
            if best_match and best_score >= 1:
                target_group = best_match
            else:
                target_group = "Others"
            
            # Add chapter to group
            if target_group not in self.chapter_groups:
                self.chapter_groups[target_group] = []
            
            if chapter not in self.chapter_groups[target_group]:
                self.chapter_groups[target_group].append(chapter)
                self.chapter_lookup[chapter] = target_group
    
    def move_chapter_to_group(
        self, 
        chapter_name: str, 
        target_group: str
    ) -> None:
        """
        Move a chapter from its current group to a target group.
        
        Args:
            chapter_name: Name of the chapter to move
            target_group: Name of the target group
        """
        # Remove from current group
        current_group = self.chapter_lookup.get(chapter_name)
        if current_group and current_group in self.chapter_groups:
            if chapter_name in self.chapter_groups[current_group]:
                self.chapter_groups[current_group].remove(chapter_name)
        
        # Add to target group
        if target_group not in self.chapter_groups:
            self.chapter_groups[target_group] = []
        
        if chapter_name not in self.chapter_groups[target_group]:
            self.chapter_groups[target_group].append(chapter_name)
        
        # Update lookup
        self.chapter_lookup[chapter_name] = target_group
    
    def extract_group_key(self, question_set_name: str) -> str:
        """
        Extract a group key from question set name for similarity grouping.
        
        Methodology:
        1. Normalize the name (lowercase, remove extra spaces)
        2. Extract significant tokens (ignore common words, years, numbers)
        3. Return first 2-3 significant words as group key
        
        Examples:
            - 'JEE Main 2023 Paper 1' -> 'jee main'
            - 'NEET-2024' -> 'neet'
            - 'Physics Olympiad 2023' -> 'physics olympiad'
        
        Args:
            question_set_name: Raw question set name from data
            
        Returns:
            Normalized group key for grouping similar sets
        """
        if not question_set_name:
            return "ungrouped"
        
        # Normalize
        normalized = self._normalize_label(question_set_name)
        
        # Split into tokens
        tokens = normalized.split()
        
        # Remove common suffix patterns (years, paper numbers, etc.)
        significant_tokens = []
        for token in tokens:
            # Skip years (4 digits), paper numbers, common words
            if re.match(r'^(\d{4}|\d+|paper|set|part|section|test|exam)$', token):
                continue
            significant_tokens.append(token)
        
        # Take first 2-3 significant tokens
        if not significant_tokens:
            return "ungrouped"
        
        return " ".join(significant_tokens[:3])
    
    def _normalize_label(self, label: str) -> str:
        """
        Normalize a label for comparison.
        
        Args:
            label: Raw label text
            
        Returns:
            Normalized lowercase label with single spaces
        """
        return re.sub(r"\s+", " ", label.strip().lower())


# Singleton instance
_data_service_instance: Optional[DataService] = None


def get_data_service() -> DataService:
    """
    Get the singleton DataService instance.
    
    Returns:
        Shared DataService instance
    """
    global _data_service_instance
    if _data_service_instance is None:
        _data_service_instance = DataService()
    return _data_service_instance


def set_data_service(service: DataService) -> None:
    """
    Set the singleton DataService instance.
    
    Args:
        service: DataService instance to use
    """
    global _data_service_instance
    _data_service_instance = service
