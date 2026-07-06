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
        """Run Puppeteer script and capture output."""
        cmd = ["node", "dola_puppeteer.js", phone]
        if otp_code:
            cmd.append(otp_code)
        
        print(f"    ╰─ Running Puppeteer...")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        try:
            stdout, stderr = process.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            print(f"    ╰─ Puppeteer timed out")
        
        if stderr:
            for line in stderr.split('\n'):
                if line.strip():
                    print(f"    ╰─ [Pup] {line.strip()[:100]}")
        
        # Parse JSON from stdout markers
        data_start = stdout.find("===DATA_START===")
        data_end = stdout.find("===DATA_END===")
        
        if data_start != -1 and data_end != -1:
            json_str = stdout[data_start + len("===DATA_START==="):data_end].strip()
            
            # Print regular log output
            regular_out = stdout[:data_start].strip()
            if regular_out:
                for line in regular_out.split('\n')[-5:]:  # Last 5 lines
                    print(f"    ╰─ {line.strip()[:120]}")
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                return {"success": False, "error": "JSON parse failed"}
        
        print(f"    ╰─ Puppeteer output: {stdout[:500]}")
        return {"success": False, "error": "No data markers"}
    
    def create_account(self):
        """Create ONE Dola account end-to-end."""
        account_num = len(self.accounts) + 1
        print(f"\n{'━' * 50}")
        print(f"  ACCOUNT #{account_num}")
        print(f"{'━' * 50}")
        
        # == STEP 1: Tiger SMS Phone ==
        print("\n[1/5] Getting temp phone from Tiger SMS...")
        try:
            balance = self.tiger.get_balance()
            print(f"    ╰─ Balance: ${balance}")
        except:
            pass
        
        try:
            activation_id, phone = self.tiger.get_number()
        except Exception as e:
            print(f"    ✗ Failed: {e}")
            return None
        
        clean_phone = phone.replace("+", "").replace(" ", "")
        
        # == STEP 2: Puppeteer — Enter Phone ==
        print("\n[2/5] Launching browser, entering phone...")
        result = self._run_puppeteer(clean_phone)
        
        # == STEP 3: Wait for SMS ==
        print("\n[3/5] Waiting for SMS code...")
        self.tiger.report_sms_sent(activation_id)
        
        try:
            sms_code = self.tiger.wait_for_code(activation_id)
            print(f"    ✓ Code received: {sms_code}")
        except Exception as e:
            print(f"    ✗ SMS failed: {e}")
            self.tiger.cancel_activation(activation_id)
            return None
        
        # == STEP 4: Puppeteer — Submit OTP ==
        print("\n[4/5] Submitting OTP and completing...")
        result = self._run_puppeteer(clean_phone, sms_code)
        
        # == STEP 5: Save ==
        print("\n[5/5] Saving account data...")
        
        account_data = {
            "account_number": account_num,
            "phone": clean_phone,
            "country": "Netherlands",
            "activation_id": activation_id,
            "created_at": datetime.now().isoformat(),
            "success": result.get("success", False),
            "final_url": result.get("url", ""),
            "session": {
                "cookies": result.get("cookies_dict", {}),
                "raw_cookies": result.get("cookies", []),
                "localStorage": result.get("localStorage", {}),
                "user_agent": result.get("user_agent", ""),
            }
        }
        
        self.accounts.append(account_data)
        self._save()
        
        try:
            self.tiger.complete_activation(activation_id)
        except:
            pass
        
        print(f"\n{'=' * 50}")
        print(f"  [✓] ACCOUNT #{account_num} CREATED!")
        print(f"  Phone: {clean_phone}")
        print(f"  Cookies: {len(account_data['session']['cookies'])} items")
        print(f"{'=' * 50}")
        
        return account_data


def main():
    print("""
╔══════════════════════════════════════════════╗
║     DOLA AUTO ACCOUNT CREATOR v1.0          ║
║     Tiger SMS + Puppeteer Automation        ║
╚══════════════════════════════════════════════╝
""")
    
    creator = DolaAccountCreator()
    
    print(f"[*] Will create {ACCOUNTS_TO_CREATE} account(s)")
    print(f"[*] Country: Netherlands ({TIGER_COUNTRY}), Service: {TIGER_SERVICE}")
    print(f"[*] Output: {OUTPUT_FILE}")
    
    for i in range(ACCOUNTS_TO_CREATE):
        creator.create_account()
        
        if i < ACCOUNTS_TO_CREATE - 1:
            print(f"\n[*] Waiting {DELAY_BETWEEN_ACCOUNTS}s before next...")
            time.sleep(DELAY_BETWEEN_ACCOUNTS)
    
    print(f"\n{'=' * 50}")
    print(f"[✓] COMPLETE! Created {len(creator.accounts)} accounts")
    print(f"[✓] Data saved to: {OUTPUT_FILE}")
    
    # Test the last session
    if creator.accounts:
        print(f"\n[*] Testing session validity...")
        creator.test_account_session()
    
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
