/**
 * Dola AI Auto Account Creator - Puppeteer Script
 * 
 * This script:
 * 1. Launches headless Chrome
 * 2. Opens Dola login page
 * 3. Enters phone number (from Tiger SMS)
 * 4. Clicks "Send Code" - Dola's JS auto-generates sign/a_bogus/msToken
 * 5. After receiving OTP (passed via command line), submits it
 * 6. Completes age verification
 * 7. Exports all cookies to stdout as JSON
 * 
 * Usage: node dola_puppeteer.js <phone_number> <otp_code>
 *        node dola_puppeteer.js "31612345678" "123456"
 */

const puppeteer = require('puppeteer');
const fs = require('fs');

// ---- CONFIG ----
const DOLA_URL = 'https://www.dola.com/chat/?from_logout=1';
const HEADLESS = false;         // Set false to see the browser
const SLOW_MO = 50;            // ms delay between actions (human-like)
const TIMEOUT = 60000;         // 60 second max wait

// ---- MAIN ----
(async () => {
    const phoneNumber = process.argv[2];
    const otpCode = process.argv[3];
    
    if (!phoneNumber) {
        console.error('ERROR: Phone number required');
        console.error('Usage: node dola_puppeteer.js <phone> [otp_code]');
        process.exit(1);
    }
    
    console.log(`[*] Launching browser...`);
    const browser = await puppeteer.launch({
        headless: HEADLESS ? 'new' : false,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--window-size=1280,800',
        ],
        defaultViewport: { width: 1280, height: 800 },
    });
    
    const page = await browser.newPage();
    
    // Block unnecessary resources for speed
    await page.setRequestInterception(true);
    page.on('request', (req) => {
        const type = req.resourceType();
        if (['image', 'stylesheet', 'font', 'media'].includes(type)) {
            req.abort();
        } else {
            req.continue();
        }
    });
    
    // Set user agent
    await page.setUserAgent(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' +
        'AppleWebKit/537.36 (KHTML, like Gecko) ' +
        'Chrome/134.0.0.0 Safari/537.36'
    );
    
    // Listen for console messages from the page
    page.on('console', (msg) => {
        if (msg.type() === 'error') return; // Ignore JS errors
    });
    
    try {
        // ===== STEP 1: Load Dola =====
        console.log(`[*] Opening Dola...`);
        await page.goto(DOLA_URL, { 
            waitUntil: 'networkidle2', 
            timeout: 30000 
        });
        console.log(`[✓] Page loaded`);
        
        // Wait a moment for JS to initialize
        await page.waitForTimeout(2000);
        
        // ===== STEP 2: Click "Continue with Phone" =====
        console.log(`[*] Looking for phone login option...`);
        
        // Try different selectors for the phone button
        const phoneSelectors = [
            'button:has-text("Phone")',
            'button:has-text("phone")',
            'div:has-text("Phone")',
            '[class*="phone"]',
            '//span[contains(text(), "Phone")]',
            '//div[contains(text(), "Phone")]',
            'button:has-text("Continue")',
        ];
        
        let phoneBtn = null;
        for (const sel of phoneSelectors) {
            try {
                phoneBtn = await page.waitForSelector(sel, { timeout: 3000 });
                if (phoneBtn) {
                    console.log(`    ╰─ Found phone button: ${sel}`);
                    break;
                }
            } catch(e) {}
        }
        
        if (phoneBtn) {
            await phoneBtn.click();
            await page.waitForTimeout(1500);
        } else {
            console.log(`    ╰─ Phone button not found, continuing...`);
        }
        
        // ===== STEP 3: Enter Phone Number =====
        console.log(`[*] Entering phone: ${phoneNumber}`);
        
        // Try various input selectors
        const inputSelectors = [
            'input[type="tel"]',
            'input[placeholder*="phone"]',
            'input[placeholder*="Phone"]',
            'input[placeholder*="number"]',
            'input[inputmode="tel"]',
            'input:not([type="hidden"])',
        ];
        
        let inputField = null;
        for (const sel of inputSelectors) {
            try {
                inputField = await page.waitForSelector(sel, { timeout: 2000 });
                if (inputField) {
                    console.log(`    ╰─ Found input: ${sel}`);
                    break;
                }
            } catch(e) {}
        }
        
        if (inputField) {
            await inputField.click();
            await page.waitForTimeout(300);
            await inputField.type(phoneNumber, { delay: 80 });
            console.log(`[✓] Phone entered`);
        } else {
            // Fallback: find all visible inputs
            const allInputs = await page.$$('input');
            console.log(`    ╰─ Found ${allInputs.length} input fields`);
            if (allInputs.length > 0) {
                await allInputs[0].click();
                await page.waitForTimeout(300);
                await allInputs[0].type(phoneNumber, { delay: 80 });
                console.log(`[✓] Phone entered (fallback)`);
            } else {
                throw new Error('Could not find phone input field');
            }
        }
        
        await page.waitForTimeout(500);
        
        // ===== STEP 4: Click Send Code / Next button =====
        console.log(`[*] Clicking Send Code button...`);
        
        const sendBtnSelectors = [
            'button:has-text("Send")',
            'button:has-text("send")',
            'button:has-text("Next")',
            'button:has-text("next")',
            'button[type="submit"]',
            'button:has-text("Continue")',
            '//button[contains(text(), "Code")]',
        ];
        
        let sendBtn = null;
        for (const sel of sendBtnSelectors) {
            try {
                sendBtn = await page.waitForSelector(sel, { timeout: 2000 });
                if (sendBtn) {
                    console.log(`    ╰─ Found button: ${sel}`);
                    break;
                }
            } catch(e) {}
        }
        
        if (sendBtn) {
            await sendBtn.click();
            console.log(`[✓] Send Code clicked - OTP should be on its way!`);
        } else {
            console.log(`    ╰─ Send button not found, page might auto-send`);
        }
        
        // ===== STEP 5: Handle CAPTCHA (if any) =====
        // Dola uses ByteDance Whirl captcha. In browser mode,
        // the captcha may appear. We handle it by waiting briefly.
        console.log(`[*] Waiting for any captcha to process...`);
        await page.waitForTimeout(3000);
        
        // Check if there's a captcha element visible
        const captchaSelectors = [
            '[class*="captcha"]',
            '[class*="verify"]', 
            '[class*="slider"]',
            '[id*="captcha"]',
        ];
        
        for (const sel of captchaSelectors) {
            try {
                const captchaEl = await page.$(sel);
                if (captchaEl) {
                    const visible = await captchaEl.isIntersectingViewport();
                    if (visible) {
                        console.log(`[!] CAPTCHA detected: ${sel}`);
                        console.log(`    ╰─ Captcha must be solved manually or via service`);
                        console.log(`    ╰─ Waiting 30s for manual solve if browser visible...`);
                        
                        if (!HEADLESS) {
                            // Wait for captcha to be solved manually
                            try {
                                await page.waitForFunction(
                                    () => {
                                        const els = document.querySelectorAll('[class*="captcha"], [class*="verify"]');
                                        for (const el of els) {
                                            if (el.style.display === 'none' || !el.isConnected) return true;
                                        }
                                        return false;
                                    },
                                    { timeout: 60000 }
                                );
                                console.log(`[✓] Captcha solved!`);
                            } catch(e) {
                                console.log(`    ╰─ Captcha wait timeout, continuing...`);
                            }
                        } else {
                            console.log(`    ╰─ Captcha may need attention`);
                        }
                        break;
                    }
                }
            } catch(e) {}
        }
        
        // ===== STEP 6: Wait for SMS code if provided =====
        if (otpCode) {
            console.log(`[*] Entering OTP code: ${otpCode}`);
            await page.waitForTimeout(1000);
            
            // Try to find OTP input fields
            const otpSelectors = [
                'input[placeholder*="code"]',
                'input[placeholder*="Code"]',
                'input[placeholder*="OTP"]',
                'input[inputmode="numeric"]',
                'input[autocomplete="one-time-code"]',
                'input[maxlength="6"]',
                'input[maxlength="4"]',
                'input.digits',
                '[class*="otp"] input',
                '[class*="code"] input',
            ];
            
            let otpInput = null;
            for (const sel of otpSelectors) {
                try {
                    otpInput = await page.waitForSelector(sel, { timeout: 2000 });
                    if (otpInput) {
                        console.log(`    ╰─ Found OTP input: ${sel}`);
                        break;
                    }
                } catch(e) {}
            }
            
            if (otpInput) {
                await otpInput.click();
                await page.waitForTimeout(300);
                await otpInput.type(otpCode, { delay: 100 });
                console.log(`[✓] OTP entered`);
            } else {
                // Try to type anywhere and press enter
                console.log(`    ╰─ OTP input not found, trying to type on page...`);
                await page.keyboard.type(otpCode, { delay: 50 });
            }
            
            await page.waitForTimeout(1500);
            
            // ===== STEP 7: Click Submit/Verify button =====
            console.log(`[*] Looking for submit button...`);
            
            const submitSelectors = [
                'button:has-text("Confirm")',
                'button:has-text("confirm")',
                'button:has-text("Verify")',
                'button:has-text("verify")',
                'button:has-text("Login")',
                'button:has-text("login")',
                'button:has-text("Submit")',
                'button[type="submit"]',
                'button:has-text("Done")',
                'button:has-text("Next")',
            ];
            
            let submitBtn = null;
            for (const sel of submitSelectors) {
                try {
                    submitBtn = await page.waitForSelector(sel, { timeout: 2000 });
                    if (submitBtn) {
                        console.log(`    ╰─ Found submit button: ${sel}`);
                        break;
                    }
                } catch(e) {}
            }
            
            if (submitBtn) {
                await submitBtn.click();
                console.log(`[✓] Submit clicked!`);
            } else {
                // Try pressing Enter
                await page.keyboard.press('Enter');
                console.log(`    ╰- Pressed Enter as fallback`);
            }
            
            // ===== STEP 8: Wait for navigation / age gate =====
            console.log(`[*] Waiting for age verification...`);
            await page.waitForTimeout(3000);
            
            // Check for age confirmation (Dola requires 18+)
            const ageSelectors = [
                'button:has-text("18")',
                'button:has-text("above")',
                'button:has-text("Confirm")',
                'button:has-text("Yes")',
                'button:has-text("agree")',
                '[class*="age"] button',
            ];
            
            for (const sel of ageSelectors) {
                try {
                    const ageBtn = await page.waitForSelector(sel, { timeout: 3000 });
                    if (ageBtn) {
                        await ageBtn.click();
                        console.log(`[✓] Age confirmed!`);
                        await page.waitForTimeout(2000);
                        break;
                    }
                } catch(e) {}
            }
            
            // ===== STEP 9: Wait for account to finalize =====
            console.log(`[*] Waiting for account to finalize...`);
            await page.waitForTimeout(3000);
            
            // Wait for navigation to complete
            try {
                await page.waitForNavigation({ timeout: 15000 });
            } catch(e) {
                // Navigation might not happen
            }
            
            console.log(`[*] Final page URL: ${page.url()}`);
            
        } else {
            console.log(`[*] No OTP code provided. Browser will stay open.`);
            console.log(`[*] Phone number: ${phoneNumber}`);
            console.log(`[*] Waiting 30s for any manual input...`);
            await page.waitForTimeout(30000);
        }
        
        // ===== STEP 10: Export Cookies =====
        console.log(`\n[*] Exporting cookies...`);
        const cookies = await page.cookies();
        
        // Format cookies for Python requests compatibility
        const cookiesDict = {};
        for (const cookie of cookies) {
            cookiesDict[cookie.name] = cookie.value;
        }
        
        // Also get localStorage
        let localStorageData = {};
        try {
            localStorageData = await page.evaluate(() => {
                const data = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    data[key] = localStorage.getItem(key);
                }
                return data;
            });
        } catch(e) {
            console.log(`    ╰─ Could not get localStorage`);
        }
        
        // Output as JSON to stdout (captured by Python)
        const result = {
            success: true,
            phone: phoneNumber,
            url: page.url(),
            cookies: cookies,
            cookies_dict: cookiesDict,
            localStorage: localStorageData,
            user_agent: await page.evaluate(() => navigator.userAgent),
        };
        
        console.log(`\n===DATA_START===`);
        console.log(JSON.stringify(result));
        console.log(`===DATA_END===`);
        
        await browser.close();
        console.log(`[✓] Browser closed`);
        
    } catch (error) {
        console.error(`\n[!] Error: ${error.message}`);
        
        // Try to export whatever cookies we have
        try {
            const cookies = await page.cookies();
            const cookiesDict = {};
            for (const cookie of cookies) {
                cookiesDict[cookie.name] = cookie.value;
            }
            
            const result = {
                success: false,
                phone: phoneNumber,
                error: error.message,
                cookies: cookies,
                cookies_dict: cookiesDict,
            };
            
            console.log(`\n===DATA_START===`);
            console.log(JSON.stringify(result));
            console.log(`===DATA_END===`);
        } catch(e) {}
        
        await browser.close();
        process.exit(1);
    }
})();
