#!/usr/bin/env python3
"""
Utility script to list all policies in the database, especially focusing on e2e_db_test_policy.

This script shows all policies with the target name and their active status,
to help debug which policy is actually being loaded.

Usage:
    poetry run python scripts/list_all_policies.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add the project root to the path so we can import luthien_control modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from luthien_control.db.database_async import close_db_engine, create_db_engine, get_db_session
from luthien_control.db.sqlmodel_models import ControlPolicy
from sqlalchemy import select

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

E2E_DB_POLICY_NAME = "e2e_db_test_policy"


async def list_all_policies():
    """List all policies in the database, focusing on the E2E policy."""
    engine_created = False
    logger.info("Listing all policies in database...")

    try:
        # Create the database engine
        engine = await create_db_engine()
        if not engine:
            raise RuntimeError("Failed to create database engine.")
        engine_created = True
        logger.info("Database engine created successfully.")

        async with get_db_session() as session:
            # Get ALL policies with the target name (both active and inactive)
            stmt_all = select(ControlPolicy).where(ControlPolicy.name.like(f"%{E2E_DB_POLICY_NAME}%"))
            result_all = await session.execute(stmt_all)
            all_matching_policies = result_all.scalars().all()

            logger.info("=" * 80)
            logger.info(f"🔍 All policies matching '{E2E_DB_POLICY_NAME}':")
            logger.info("=" * 80)

            if not all_matching_policies:
                logger.warning(f"❌ No policies found matching '{E2E_DB_POLICY_NAME}'")
            else:
                for i, policy in enumerate(all_matching_policies):
                    status = "✅ ACTIVE" if policy.is_active else "❌ INACTIVE"
                    logger.info(f"[{i+1}] {status}")
                    logger.info(f"    ID: {policy.id}")
                    logger.info(f"    Name: {policy.name}")
                    logger.info(f"    Type: {policy.type}")
                    logger.info(f"    Active: {policy.is_active}")
                    logger.info(f"    Description: {policy.description}")
                    logger.info(f"    Created: {policy.created_at}")
                    logger.info(f"    Updated: {policy.updated_at}")
                    
                    # Check for legacy content
                    if isinstance(policy.config, dict) and "policies" in policy.config:
                        has_legacy = False
                        for sub_policy in policy.config["policies"]:
                            policy_type = sub_policy.get("type", "")
                            if policy_type == "TxLoggingPolicy":
                                has_legacy = True
                                break
                        
                        if has_legacy:
                            logger.info(f"    🚨 LEGACY: Contains TxLoggingPolicy")
                        else:
                            logger.info(f"    ✅ MODERN: No legacy policy types detected")
                    
                    logger.info(f"    Config preview: {str(policy.config)[:100]}...")
                    logger.info("-" * 60)

            # Now get only the ACTIVE policy (what the app would actually load)
            stmt_active = select(ControlPolicy).where(
                ControlPolicy.name == E2E_DB_POLICY_NAME,
                ControlPolicy.is_active
            )
            result_active = await session.execute(stmt_active)
            active_policy = result_active.scalar_one_or_none()

            logger.info("=" * 80)
            logger.info(f"🎯 ACTIVE policy that would be loaded by the app:")
            logger.info("=" * 80)

            if not active_policy:
                logger.warning(f"❌ No ACTIVE policy found with exact name '{E2E_DB_POLICY_NAME}'")
                logger.warning("This is why the app can't load the policy!")
            else:
                logger.info(f"✅ Found ACTIVE policy: {active_policy.name} (ID: {active_policy.id})")
                logger.info(f"Type: {active_policy.type}")
                logger.info(f"Description: {active_policy.description}")
                
                # Show full config
                logger.info("Full configuration:")
                logger.info(json.dumps(active_policy.config, indent=2))

                # Check for legacy content in active policy
                if isinstance(active_policy.config, dict) and "policies" in active_policy.config:
                    logger.info("Sub-policies in active policy:")
                    for i, sub_policy in enumerate(active_policy.config["policies"]):
                        policy_type = sub_policy.get("type", "unknown")
                        policy_name = sub_policy.get("config", {}).get("name", "unknown")
                        logger.info(f"  [{i}] Type: {policy_type}, Name: {policy_name}")
                        
                        if policy_type == "TxLoggingPolicy":
                            logger.warning(f"  🚨 PROBLEM: Legacy TxLoggingPolicy found at index {i}")

            return True

    except Exception as e:
        logger.exception(f"❌ Error listing policies: {e}")
        return False
    finally:
        if engine_created:
            await close_db_engine()
            logger.info("Database engine closed.")


async def main():
    """Main function."""
    logger.info("E2E DB Policy Lister")
    logger.info("=" * 50)

    success = await list_all_policies()

    if success:
        logger.info("✅ Policy listing completed!")
    else:
        logger.error("❌ Policy listing failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())