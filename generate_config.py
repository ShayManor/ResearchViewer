#!/usr/bin/env python3
"""
Generate config.cfg from environment variables.

This script creates the Flask-MonitoringDashboard configuration file
from environment variables, allowing secrets to be injected at runtime
instead of being committed to the repository.

Environment Variables:
    DASHBOARD_USERNAME: Dashboard login username (default: admin)
    DASHBOARD_PASSWORD: Dashboard login password (REQUIRED in production)
    DASHBOARD_MONITOR_LEVEL: Monitoring level 0-3 (default: 3)
    DASHBOARD_DB_PATH: Database path (default: sqlite:///monitoring/monitoring.db)
"""

import os
import sys

def generate_config():
    """Generate config.cfg from environment variables."""

    # Get configuration from environment
    username = os.getenv('DASHBOARD_USERNAME', 'admin')
    password = os.getenv('DASHBOARD_PASSWORD')
    monitor_level = os.getenv('DASHBOARD_MONITOR_LEVEL', '3')
    db_path = os.getenv('DASHBOARD_DB_PATH', 'sqlite:///monitoring/monitoring.db')
    timezone = os.getenv('DASHBOARD_TIMEZONE', 'America/Los_Angeles')

    # Fail fast: never seed a predictable password. A missing secret must crash
    # the container rather than quietly enabling login with a known default.
    if not password:
        print("❌ DASHBOARD_PASSWORD not set — refusing to generate config.", file=sys.stderr)
        print("   Set the DASHBOARD_PASSWORD environment variable (production: GitHub secret via deploy.sh).", file=sys.stderr)
        sys.exit(1)

    # Generate config content
    config_content = f"""[dashboard]
MONITOR_LEVEL = {monitor_level}
OUTLIER_DETECTION = True
SAMPLING_PERIOD = 20
CUSTOM_LINK = dashboard

[database]
TABLE_PREFIX = fmd
DATABASE = {db_path}

[authentication]
USERNAME = {username}
PASSWORD = {password}

[visualization]
TIMEZONE = {timezone}
COLORS = {{'main': '#3498db', 'static': '#95a5a6'}}
"""

    # Write config file
    config_path = 'config.cfg'
    with open(config_path, 'w') as f:
        f.write(config_content)

    print(f"✅ Generated {config_path}")
    print(f"   Username: {username}")
    print(f"   Password: {'*' * len(password)}")
    print(f"   Monitor Level: {monitor_level}")
    print(f"   Database: {db_path}")

    return config_path

if __name__ == '__main__':
    try:
        generate_config()
    except Exception as e:
        print(f"❌ Error generating config: {e}", file=sys.stderr)
        sys.exit(1)
