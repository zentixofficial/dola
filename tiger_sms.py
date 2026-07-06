"""
Tiger SMS API Wrapper
- Get temporary phone number (Netherlands, service=other)
- Wait for SMS code
- Manage activation lifecycle
"""
import requests
import time
from config import TIGER_API_KEY, TIGER_COUNTRY, TIGER_SERVICE, SMS_TIMEOUT


class TigerSMS:
    """Handles all Tiger SMS API operations."""
    
    BASE_URL = "https://api.tiger-sms.com/stubs/handler_api.php"
    
    def __init__(self, api_key=None):
        self.api_key = api_key or TIGER_API_KEY
    
    def _call(self, params):
        """Make API call to Tiger SMS."""
        params["api_key"] = self.api_key
        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=30)
            print(f"    ╰─ Tiger SMS response: {resp.text[:150]}")
            return resp.text.strip()
        except Exception as e:
            print(f"    ╰─ Tiger SMS error: {e}")
            return f"ERROR:{e}"
    
    def get_balance(self):
        """Check account balance."""
        return self._call({"action": "getBalance"})
    
    def get_number(self, country=None, service=None):
        """
        Get a temporary phone number.
        Returns: (activation_id, phone_number)
        """
        params = {
            "action": "getNumber",
            "country": country or TIGER_COUNTRY,
            "service": service or TIGER_SERVICE,
        }
        result = self._call(params)
        
        if result.startswith("ACCESS_NUMBER"):
            parts = result.split(":")
            activation_id = parts[1]
            phone = parts[2]
            print(f"    ╰─ Got number: {phone} (ID: {activation_id})")
            return activation_id, phone
        else:
            raise Exception(f"Failed to get number: {result}")
    
    def set_status(self, activation_id, status):
        """
        Set activation status.
        1 = SMS sent (ready), 3 = request another SMS,
        6 = complete, 8 = cancel
        """
        result = self._call({
            "action": "setStatus",
            "id": activation_id,
            "status": str(status)
        })
        return result
    
    def get_status(self, activation_id):
        """Check activation status. Returns STATUS_OK:CODE or STATUS_WAIT_CODE."""
        return self._call({
            "action": "getStatus",
            "id": activation_id
        })
    
    def wait_for_code(self, activation_id, timeout=None):
        """
        Poll until SMS code is received.
        Returns: OTP code (string)
        """
        timeout = timeout or SMS_TIMEOUT
        start = time.time()
        poll_interval = 3  # seconds
        
        print(f"    ╰─ Waiting for SMS code (timeout: {timeout}s)...")
        
        while time.time() - start < timeout:
            status = self.get_status(activation_id)
            
            if status.startswith("STATUS_OK"):
                code = status.split(":")[1]
                print(f"    ╰─ SMS received! Code: {code}")
                return code
            
            elif status.startswith("STATUS_WAIT_CODE"):
                remaining = int(timeout - (time.time() - start))
                if remaining % 10 == 0:  # Print every 10s
                    print(f"    ╰─ Still waiting... ({remaining}s left)")
                time.sleep(poll_interval)
                continue
            
            elif status.startswith("STATUS_WAIT_RETRY"):
                print(f"    ╰─ Waiting for retry...")
                time.sleep(poll_interval)
                continue
            
            elif status.startswith("ACCESS_CANCEL"):
                raise Exception(f"Activation was cancelled")
            
            else:
                # STATUS_OK without code format - try anyway
                if "STATUS_OK" in status:
                    print(f"    ╰─ Possible code in: {status}")
                    return status.replace("STATUS_OK:", "").strip()
                print(f"    ╰─ Unknown status: {status}")
                time.sleep(poll_interval)
        
        raise TimeoutError("SMS code not received within timeout period")
    
    def report_sms_sent(self, activation_id):
        """Tell Tiger SMS that SMS has been sent to the number."""
        return self.set_status(activation_id, 1)
    
    def complete_activation(self, activation_id):
        """Mark activation as complete."""
        return self.set_status(activation_id, 6)
    
    def cancel_activation(self, activation_id):
        """Cancel activation (refund if unused)."""
        return self.set_status(activation_id, 8)


# Quick test
if __name__ == "__main__":
    tiger = TigerSMS()
    print(f"Balance: {tiger.get_balance()}")
