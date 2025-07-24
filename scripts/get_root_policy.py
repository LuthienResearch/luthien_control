#!/usr/bin/env python3
"""
Get the root policy from the database using psycopg2 directly.
"""

import json
import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv()

# Get database credentials
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "luthien_sqlmodel")
DB_USER = os.getenv("DB_USER", "luthien_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "luthien_pass")

try:
    # Connect to the database
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, cursor_factory=RealDictCursor
    )

    with conn.cursor() as cur:
        # Query for the root policy
        cur.execute("""
            SELECT id, name, type, config, is_active, description, created_at, updated_at
            FROM policies
            WHERE name = 'root' AND is_active = true
        """)

        policy = cur.fetchone()

        if policy:
            print("Found active 'root' policy:")
            print(f"ID: {policy['id']}")
            print(f"Type: {policy['type']}")
            print(f"Description: {policy['description']}")
            print(f"Created: {policy['created_at']}")
            print(f"Updated: {policy['updated_at']}")
            print("\nFull Configuration:")
            print("-" * 60)
            print(json.dumps(policy["config"], indent=2))
        else:
            print("No active 'root' policy found in the database.")

            # Check if there are any inactive root policies
            cur.execute("""
                SELECT id, name, is_active
                FROM policies
                WHERE name = 'root'
            """)
            inactive = cur.fetchall()
            if inactive:
                print("\nFound inactive root policies:")
                for p in inactive:
                    print(f"  - ID: {p['id']}, Active: {p['is_active']}")

    conn.close()

except Exception as e:
    print(f"Error connecting to database: {e}")
    sys.exit(1)
