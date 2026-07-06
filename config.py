"""
Dola Auto Account Creator - Configuration
"""
import os

# ===== TIGER SMS CONFIG =====
TIGER_API_KEY = "6BvOu9rJzpdyiFygmVUZtyhnn5YUuZcq"

# Netherlands = country code 48, Service = other (Any Other)
TIGER_COUNTRY = 48
TIGER_SERVICE = "other"

# ===== DOLA CONFIG =====
DOLA_BASE_URL = "https://www.dola.com"
DOLA_LOGIN_URL = "https://www.dola.com/chat/?from_logout=1"

# ===== ACCOUNT SETTINGS =====
ACCOUNTS_TO_CREATE = 1
OUTPUT_FILE = "accounts.json"

# How long to wait for SMS (seconds)
SMS_TIMEOUT = 120

# Delay between accounts (seconds)
DELAY_BETWEEN_ACCOUNTS = 10

# User Agent for API calls
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
             "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
