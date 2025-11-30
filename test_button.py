#!/usr/bin/env python3
"""Test script for button visibility issue."""

from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt
import sys

# Create app
app = QApplication(sys.argv)

# Create a simple container widget with a button
container = QWidget()
layout = QHBoxLayout(container)

label = QLabel("Test Label")
layout.addWidget(label)

button = QPushButton("🔘")
button.hide()
layout.addWidget(button)

print(f"[TEST] Before show: button visible = {button.isVisible()}")
button.show()
print(f"[TEST] After show: button visible = {button.isVisible()}")

container.show()
print(f"[TEST] After container show: button visible = {button.isVisible()}")

# Check parent
print(f"[TEST] Button parent: {button.parent()}")
print(f"[TEST] Container visible: {container.isVisible()}")
