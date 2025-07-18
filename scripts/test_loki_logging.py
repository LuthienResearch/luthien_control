#!/usr/bin/env python3
"""Test script to verify Loki logging is working properly."""

import asyncio
import os
import sys
import time
from datetime import datetime

import httpx
import pytest

# Add the parent directory to the path so we can import luthien_control
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from luthien_control.core.logging import setup_logging

pytestmark = pytest.mark.integration


async def test_proxy_request():
    """Send a test request through the proxy to generate logs."""
    # Ensure we have proper logging setup
    os.environ["LOKI_URL"] = "http://localhost:3100"
    os.environ["LOG_LEVEL"] = "DEBUG"
    setup_logging()

    print("Testing proxy request logging...")

    # Create a test request
    async with httpx.AsyncClient() as client:
        try:
            # Make a simple request to the proxy
            response = await client.post(
                "http://localhost:8000/api/chat/completions",
                headers={
                    "Authorization": "Bearer test-key",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Say 'test successful' if you receive this"}],
                    "max_tokens": 10,
                },
            )
            print(f"Proxy response status: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
        except Exception as e:
            print(f"Error making proxy request: {e}")


async def check_loki_logs():
    """Query Loki to verify logs are being received."""
    print("\nChecking Loki for logs...")

    async with httpx.AsyncClient() as client:
        # Query Loki for recent logs
        query_url = "http://localhost:3100/loki/api/v1/query"

        # Query for logs from the last 5 minutes
        now = int(time.time() * 1e9)  # nanoseconds
        five_minutes_ago = now - (5 * 60 * 1e9)

        queries = [
            '{application="luthien_control"}',
            '{application="luthien_control"} |= "Proxy request"',
            '{application="luthien_control"} |= "transaction_id"',
        ]

        for query in queries:
            try:
                response = await client.get(
                    query_url,
                    params={
                        "query": query,
                        "start": str(int(five_minutes_ago)),
                        "end": str(int(now)),
                        "limit": 10,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    result_count = sum(len(stream["values"]) for stream in data.get("data", {}).get("result", []))
                    print(f"\nQuery: {query}")
                    print(f"Found {result_count} log entries")

                    # Print sample logs
                    for stream in data.get("data", {}).get("result", [])[:2]:
                        print(f"Stream labels: {stream['stream']}")
                        for timestamp, log_line in stream["values"][:3]:
                            print(f"  {log_line[:150]}...")
                else:
                    print(f"Error querying Loki: {response.status_code}")
                    print(response.text)
            except Exception as e:
                print(f"Error connecting to Loki: {e}")


async def test_grafana_datasource():
    """Test if Grafana can connect to Loki."""
    print("\nChecking Grafana datasource...")

    async with httpx.AsyncClient() as client:
        try:
            # Check Grafana datasources
            response = await client.get("http://localhost:3000/api/datasources", headers={"Accept": "application/json"})

            if response.status_code == 200:
                datasources = response.json()
                loki_ds = [ds for ds in datasources if ds.get("type") == "loki"]
                if loki_ds:
                    print(f"Found Loki datasource: {loki_ds[0]['name']}")
                    print(f"URL: {loki_ds[0].get('url', 'N/A')}")
                else:
                    print("No Loki datasource found in Grafana")
            else:
                print(f"Could not query Grafana datasources: {response.status_code}")
        except Exception as e:
            print(f"Error connecting to Grafana: {e}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Luthien Control Loki Logging Test")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Test 1: Send a proxy request
    await test_proxy_request()

    # Wait a bit for logs to be processed
    print("\nWaiting 2 seconds for logs to be processed...")
    await asyncio.sleep(2)

    # Test 2: Check Loki logs
    await check_loki_logs()

    # Test 3: Check Grafana datasource
    await test_grafana_datasource()

    print("\n" + "=" * 60)
    print("Test complete!")
    print("\nTo view logs in Grafana:")
    print("1. Open http://localhost:3000")
    print("2. Go to Explore (compass icon)")
    print("3. Select 'Loki' as the datasource")
    print('4. Use query: {application="luthien_control"}')
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
