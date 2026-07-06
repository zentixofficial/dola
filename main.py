#!/usr/bin/env python3
"""
Dola Auto Account Creator — Main Orchestrator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tiger SMS → Get Phone → Puppeteer → Dola → Save Cookies
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import subprocess
import json
import time
import os
import sys
from datetime import datetime

from config import (
    TIGER_API_KEY, TIGER_COUNTRY, TIGER_SERVICE,
    ACCOUNTS_TO_CREATE, OUTPUT_FILE,
    DELAY_BETWEEN_ACCOUNTS
)
from tiger_sms import TigerSMS


class DolaAccountCreator:
    """Orchestrates the full account creation process."""
    
    def __init__(self, tiger_api_key=None):
        self.tiger = TigerSMS(tiger_api_key or TIGER_API_KEY)
        self.accounts = []
        self._load_existing()
    
    def _load_existing(self):
        """Load previously created accounts."""
        if os.path.exists(OUTPUT_FILE):
            try:
                with open(OUTPUT_FILE, 'r') as f:
                    self.accounts = json.load(f)
                print(f"[*] Loaded {len(self.accounts)} existing accounts")
            except:
                self.accounts = []
    
    def _save(self):
        """Save all accounts to JSON file."""
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(self.accounts, f, indent=2, default=str)
        print(f"[✓] Saved to {OUTPUT_FILE}")
    
    def _run_puppeteer(self, phone, otp_code=None):
        """
        Run Puppeteer script and capture output.
        Returns: parsed JSON result from puppeteer
        """
        cmd = ["node", "dola_puppeteer.js", phone]
        if otp_code:
            cmd.append(otp_code)
        
        print(f"    ╰─ Running: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        stdout, stderr = process.communicate(timeout=180)
        
        if stderr:
            for line in stderr.split('\n'):
                if line.strip():
                    print(f"    ╰─ [Puppeteer] {line.strip()}")
        
        # Parse the JSON data from stdout
        data_start = stdout.find("===DATA_START===")
        data_end = stdout.find("===DATA_END===")
        
        if data_start != -1 and data_end != -1:
            json_str = stdout[data_start + len("===DATA_START==="):data_end].strip()
            
            # Also print regular stdout
            regular_out = stdout[:data_start].strip()
            if regular_out:
                for line in regular_out.split('\n'):
                    print(f"    ╰─ {line.strip()}")
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"    ╰─ JSON parse error: {e}")
                print(f"    ╰─ Raw: {json_str[:500]}")
                return {"success": False, "error": f"JSON parse: {e}"}
        else:
            print(f"    ╰─ Full stdout: {stdout[:2000]}")
            return {"success": False, "error": "No data markers found"}
    
    def create_account(self):
        """
        Create ONE Dola account.
        
        Flow:
        1. Tiger SMS → get temporary phone number
        2. Puppeteer → open Dola, enter phone, send OTP
        3. Tiger SMS → wait for SMS code
        4. Puppeteer → enter OTP, complete registration
        5. Extract cookies, save account
        """
        account_num = len(self.accounts) + 1
        print(f"\n{'━' * 50}")
        print(f"  ACCOUNT #{account_num}")
        print(f"{'━' * 50}")
        
        # ===== STEP 1: Get phone from Tiger SMS =====
        print("\n[1/5] Getting temporary phone number from Tiger SMS...")
        print(f"    ╰─ Country: Netherlands ({TIGER_COUNTRY}), Service: {TIGER_SERVICE}")
        
        try:
            balance = self.tiger.get_balance()
            print(f"    ╰─ Balance: {balance}")
        except Exception as e:
            print(f"    ╰─ Balance check: {e}")
        
        try:
            activation_id, phone = self.tiger.get_number()
        except Exception as e:
            print(f"    ╰─ Failed: {e}")
            return None
        
        # Format phone for Dola (remove + prefix if any)
        clean_phone = phone.replace("+", "").replace(" ", "")
        
        # ===== STEP 2: Run Puppeteer (enter phone, send OTP) =====
        print("\n[2/5] Launching Puppeteer to enter phone on Dola...")
        result = self._run_puppeteer(clean_phone)
        
        if not result.get("success", False) and not result.get("cookies_dict"):
            print(f"    ╰─ Puppeteer had issues, but may have sent OTP")
            # Continue anyway - OTP might have been sent
        
        # ===== STEP 3: Wait for SMS code from Tiger SMS =====
        print("\n[3/5] Waiting for SMS code...")
        self.tiger.report_sms_sent(activation_id)
        
        try:
            sms_code = self.tiger.wait_for_code(activation_id)
            print(f"    ╰─ Code: {sms_code}")
        except Exception as e:
            print(f"    ╰─ Failed: {e}")
            self.tiger.cancel_activation(activation_id)
            return None
        
        # ===== STEP 4: Run Puppeteer again with OTP =====
        print("\n[4/5] Entering OTP code and completing registration...")
        result = self._run_puppeteer(clean_phone, sms_code)
        
        # ===== STEP 5: Extract and save data =====
        print("\n[5/5] Saving account data...")
        
        cookies = result.get("cookies_dict", {})
        raw_cookies = result.get("cookies", [])
        local_storage = result.get("localStorage", {})
        
        account_data = {
            "account_number": account_num,
            "phone": clean_phone,
            "country": "Netherlands",
            "activation_id": activation_id,
            "created_at": datetime.now().isoformat(),
            "puppeteer_success": result.get("success", False),
            "final_url": result.get("url", ""),
            "session": {
                "cookies_dict": cookies,
                "raw_cookies": raw_cookies,
                "localStorage": local_storage,
                "user_agent": result.get("user_agent", ""),
            }
        }
        
        self.accounts.append(account_data)
        self._save()
        
        # Mark activation complete
        try:
            self.tiger.complete_activation(activation_id)
        except:
            pass
        
        print(f"\n{'=' * 50}")
        print(f"  [✓] ACCOUNT #{account_num} CREATED!")
        print(f"  Phone: {clean_phone}")
        print(f"  Cookies: {len(cookies)} items")
        print(f"{'=' * 50}")
        
        return account_data
    
    def test_account_session(self, account_index=None):
        """Test if saved cookies still work."""
        if not self.accounts:
            print("[!] No accounts saved yet.")
            return
        
        if account_index is None:
            account_index = len(self.accounts) - 1
        
        acc = self.accounts[account_index]
        phone = acc.get("phone", "unknown")
        print(f"\n[*] Testing session for account #{account_index + 1} ({phone})...")
        
        cookies = acc.get("session", {}).get("cookies_dict", {})
        
        if not cookies:
            print("    ╰─ No cookies found in this account")
            return
        
        import requests
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": acc.get("session", {}).get("user_agent", 
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
            "Accept": "application/json, text/plain, */*",
        })
        
        for name, value in cookies.items():
            session.cookies.set(name, value)
        
        # Test: access Dola chat page
        try:
            resp = session.get(
                "https://www.dola.com/chat/",
                timeout=15,
                allow_redirects=True
            )
            print(f"    ╰─ Status: {resp.status_code}")
            print(f"    ╰─ URL: {resp.url}")
            
            if resp.status_code == 200:
                print(f"    ╰─ [✓] Session is VALID!")
            elif resp.status_code == 302 or "login" in resp.url:
                print(f"    ╰─ [✗] Session expired - redirected to login")
            else:
                print(f"    ╰─ [?] Unknown state")
        except Exception as e:
            print(f"    ╰─ Error: {e}")
    
    def list_accounts(self):
        """List all created accounts."""
        if not self.accounts:
            print("[!] No accounts created yet.")
            return
        
        print(f"\n[*] Total accounts: {len(self.accounts)}")
        print(f"{'─' * 60}")
        for i, acc in enumerate(self.accounts):
            phone = acc.get("phone", "?")
            created = acc.get("created_at", "?")[:19]
            cookies = len(acc.get("session", {}).get("cookies_dict", {}))
            success = "✓" if acc.get("puppeteer_success") else "?"
            print(f"  #{i+1}. {phone}  |  {created}  |  {cookies} cookies  [{success}]")
        print(f"{'─' * 60}")


def main():
    print("""
    ╔══════════════════════════════════════════════╗
    ║     DOLA AUTO ACCOUNT CREATOR v1.0          
$$
