"""
Caching configuration for the application.
Separated to avoid circular imports.
"""
from flask_caching import Cache

# Initialize cache instance (will be configured by app)
cache = Cache()