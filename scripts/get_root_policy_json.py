#!/usr/bin/env python3
"""
Get the root policy from the database and output just the JSON.
"""

import json
import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import psycopg2
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
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor
    )
    
    with conn.cursor() as cur:
        # Query for the root policy
        cur.execute("""
            SELECT type, config
            FROM policies
            WHERE name = 'root' AND is_active = true
        """)
        
        policy = cur.fetchone()
        
        if policy:
            # Create the full policy JSON structure
            full_policy = {
                "type": policy['type'],
                "config": policy['config']
            }
            print(json.dumps(full_policy, indent=2))
        else:
            print("No active 'root' policy found in the database.")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)