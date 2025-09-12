#!/usr/bin/env python3
"""Create new database with updated schema"""
from database_v2.models_v2 import DatabaseManager

# This will create the database with all tables
db = DatabaseManager("clipping.db")
print("Database created successfully with all tables including extra_data column")