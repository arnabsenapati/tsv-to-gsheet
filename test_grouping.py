#!/usr/bin/env python3
"""Test script for GroupItemWidget initialization."""

from src.ui.question_set_grouping_view import GroupItemWidget
from PySide6.QtWidgets import QApplication
import sys

# Create app
app = QApplication(sys.argv)

# Create widget
print("[TEST] Creating GroupItemWidget...")
widget = GroupItemWidget("Test Group", 5, "#3b82f6", None)
print("[TEST] Widget created successfully")
print(f"[TEST] Widget size hint: {widget.sizeHint()}")
print(f"[TEST] Button visible: {widget.rename_btn.isVisible()}")
print("[TEST] Simulating hover...")
from PySide6.QtGui import QEnterEvent
from PySide6.QtCore import QPoint
event = QEnterEvent(QPoint(10, 10), QPoint(10, 10), QPoint(10, 10))
widget.enterEvent(event)
print(f"[TEST] After hover - Button visible: {widget.rename_btn.isVisible()}")
print("[TEST] Done!")
