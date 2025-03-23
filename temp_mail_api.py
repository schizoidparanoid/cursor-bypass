import requests
import re
import json
import urllib3
import time
import sys
import datetime
from bs4 import BeautifulSoup
import traceback

# Disable insecure SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TempMailAPI:
    def __init__(self):
        self.base_url = "https://tempsmails.com"
        self.session = requests.Session()
        self.session.verify = False  # Disable SSL verification
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://tempsmails.com',
            'Referer': 'https://tempsmails.com/en',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }
        self.csrf_token = None
        self.session_cookie = None
        self.email_address = None
        self.messages = []
        self.last_check_time = None
        self.last_response = None
        self.verification_code = None
        
        # Debug settings
        self.debug = False
        self.log_file = "temp_mail_debug.log"
        
    def log_debug(self, message):
        """Log debug message to file and console"""
        # Skip if debug mode is not enabled
        if not self.debug:
            return
        
        # Add timestamp to message
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        
        # Show in console
        print(f"DEBUG: {message}")
        
        # Write to log file
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{log_message}\n")
        except Exception as e:
            print(f"Warning: Failed to write to log file: {e}")

    def initialize(self):
        """Get both CSRF token and session cookie in one request"""
        try:
            print("Connecting to tempsmails.com...")
            
            response = self.session.get(f"{self.base_url}/en", headers=self.headers, verify=False, timeout=30)
            
            if self.debug:
                self.log_debug(f"Server responded with code {response.status_code}")
            
            if response.status_code != 200:
                print(f"Error: Server responded with code {response.status_code}")
                return False
                
            # Search for CSRF token using regex
            html_content = response.text
            
            # Try different patterns to find CSRF token
            csrf_patterns = [
                r'<meta name="csrf-token" content="([^"]+)"',
                r'name="_token" value="([^"]+)"',
                r'<input type="hidden" name="_token" value="([^"]+)"',
                r'csrf-token" content="([^"]+)"',
                r'_token" value="([^"]+)"'
            ]
            
            for pattern in csrf_patterns:
                match = re.search(pattern, html_content)
                if match:
                    self.csrf_token = match.group(1)
                    if self.debug:
                        self.log_debug(f"Found CSRF token using pattern: {pattern}")
                    break
            
            if not self.csrf_token:
                # Look for any token that looks like a CSRF token (long alphanumeric string)
                token_pattern = r'value="([a-zA-Z0-9]{30,})"'
                match = re.search(token_pattern, html_content)
                if match:
                    self.csrf_token = match.group(1)
                    if self.debug:
                        self.log_debug("Found CSRF token using fallback pattern")
                else:
                    print("ERROR: Could not find CSRF token")
                    return False
            
            # Get session cookie
            cookies = response.cookies
            
            if 'temp_mail_session' in cookies:
                self.session_cookie = cookies['temp_mail_session']
            else:
                # Try to get cookies from Headers
                if 'Set-Cookie' in response.headers:
                    cookie_header = response.headers['Set-Cookie']
                    cookie_match = re.search(r'temp_mail_session=([^;]+)', cookie_header)
                    if cookie_match:
                        self.session_cookie = cookie_match.group(1)
                    else:
                        print("ERROR: Session cookie not found in headers")
                        return False
                else:
                    print("ERROR: No Set-Cookie header found")
                    return False
            
            # Check if we have all required data
            if not self.csrf_token:
                print("Failed: Could not obtain CSRF token")
                return False
                
            if not self.session_cookie:
                print("Failed: Could not obtain session cookie")
                return False
                
            print("Initialization successful")
            return True
            
        except requests.exceptions.Timeout:
            print("Error: Connection timed out")
            return False
        except requests.exceptions.ConnectionError:
            print("Error: Could not connect to server. Check your internet connection")
            return False
        except Exception as e:
            print(f"Error during initialization: {e}")
            return False

    def extract_verification_code(self, content):
        """Extract verification code from message content"""
        # Search for the standard verification code pattern
        print("\nLooking for verification code...")
        
        # Direct pattern - this is what we typically see in Cursor emails
        code_match = re.search(r'Your verification code is (\d{6})', content)
        if code_match:
            code = code_match.group(1)
            print(f"Verification code found: {code}")
            return code
        
        # If not found directly, look in any hidden divs
        print("Checking in hidden email sections...")
        hidden_pattern = r'<div style="display:none[^>]*>(.*?)</div>'
        hidden_text = re.search(hidden_pattern, content)
        if hidden_text:
            hidden_content = hidden_text.group(1)
            code_match = re.search(r'(\d{6})', hidden_content)
            if code_match:
                code = code_match.group(1)
                print(f"Verification code found in hidden text: {code}")
                return code
        
        # Look for any 6 digits with styling that might indicate it's a code
        code_match = re.search(r'letter-spacing[^>]*>(\d{6})<', content)
        if code_match:
            code = code_match.group(1)
            print(f"Verification code found in styled text: {code}")
            return code
        
        # Last resort: get all 6-digit numbers and return the first valid one
        all_six_digits = re.findall(r'\d{6}', content)
        if all_six_digits:
            # Filter out potential dates
            valid_codes = [num for num in all_six_digits if not num.startswith('19') and not num.startswith('20')]
            if valid_codes:
                print(f"Possible verification codes found: {', '.join(valid_codes[:5])}")
                print(f"Using first code: {valid_codes[0]}")
                return valid_codes[0]
        
        print("No verification code found")
        return None

    def format_verification_code(self, code):
        """Format verification code by adding spaces between digits for better readability"""
        if not code:
            return "No code found"
        
        # Add a space between each digit
        return ' '.join(list(code))
        
    def get_messages(self, silent=False):
        """Get messages using the CSRF token and session cookie"""
        if not self.csrf_token or not self.session_cookie:
            if not silent:
                print("CSRF token or session cookie not available")
            return None

        try:
            # Configure cookie in session
            if 'Cookie' not in self.session.cookies._cookies.get(self.base_url.replace('https://', ''), {}).get('/', {}):
                self.session.cookies.set('temp_mail_session', self.session_cookie, 
                                        domain=self.base_url.replace('https://', ''), path='/')
            
            # Add CSRF token to headers
            if 'X-CSRF-TOKEN' not in self.headers:
                self.headers['X-CSRF-TOKEN'] = self.csrf_token
            
            # Prepare POST data
            data = {
                '_token': self.csrf_token,
                'captcha': ''
            }
            
            # Send request
            response = self.session.post(
                f"{self.base_url}/messages",
                headers=self.headers,
                data=data,
                verify=False,
                timeout=30
            )
            
            # Check response status
            if response.status_code != 200:
                if not silent:
                    print(f"Error: HTTP {response.status_code}")
                return None
            
            # Parse JSON
            try:
                result = response.json()
                self.last_response = result
                
                # Get email address
                if 'mailbox' in result and not self.email_address:
                    self.email_address = result['mailbox']
                
                # Check for messages
                if 'messages' in result and result['messages']:
                    self.messages = result['messages']
                    
                    # Only print if not in silent mode
                    if not silent:
                        print("\n" + "="*50)
                        print(f"FOUND {len(result['messages'])} MESSAGES")
                        
                        # Process first message only
                        if result['messages']:
                            first_msg = result['messages'][0]
                            print(f"\nMESSAGE: {first_msg.get('subject', 'No subject')}")
                            print(f"FROM: {first_msg.get('from_email', 'Unknown')}")
                            print(f"ID: {first_msg.get('id', 'Unknown')}")
                            
                            # Process content if available
                            if 'content' in first_msg:
                                content = first_msg['content']
                                
                                # Look for verification code (6 digits followed by period)
                                print("\nSEARCHING FOR VERIFICATION CODE (6 DIGITS FOLLOWED BY PERIOD)...\n")
                                
                                # Specific pattern: 6 digits followed by period
                                matches = re.findall(r'(\d{6})\.', content)
                                
                                if matches:
                                    print("\n" + "="*50)
                                    print(f"VERIFICATION CODE FOUND: {matches[0]}")
                                    print("="*50 + "\n")
                                    
                                    # Instead of exiting, store the code and return it
                                    self.verification_code = matches[0]
                                    print("Program found verification code successfully.")
                                    return result  # Return normally instead of exiting
                                else:
                                    print("No 6-digit code followed by period found.")
                                    
                                    # Fall back to looking for any 6-digit code
                                    print("\nLooking for any 6-digit code as alternative...\n")
                                    all_codes = re.findall(r'\d{6}', content)
                                    if all_codes:
                                        # Filter out potential dates
                                        valid_codes = [code for code in all_codes if not code.startswith('20') and not code.startswith('19')]
                                        if valid_codes:
                                            print("\nCODES FOUND:")
                                            for i, code in enumerate(valid_codes):
                                                print(f"  > {i+1}. {code}")
                                            
                                            print(f"\nUSING FIRST CODE: {valid_codes[0]}\n")
                                            
                                            # Instead of exiting, store the code and return it
                                            self.verification_code = valid_codes[0]
                                            print("Program found verification code successfully.")
                                            return result  # Return normally instead of exiting
                            else:
                                print(f"Warning: Message has no 'content' field. Available fields: {list(first_msg.keys())}")
                elif not silent:
                    print("No messages found.")
                
                return result
                
            except json.JSONDecodeError:
                if not silent:
                    print("Error: Response is not valid JSON")
                return None
                
        except requests.exceptions.Timeout:
            if not silent:
                print("Error: Timeout getting messages")
            return None
        except Exception as e:
            if not silent:
                print(f"Error getting messages: {e}")
            return None

    def monitor_for_new_emails(self, callback=None, interval=2, timeout=300):
        """
        Monitor for new messages and execute a callback when they arrive.
        If no callback is provided, it will just print the new messages.
        
        Args:
            callback: Optional function to call with the verification code
            interval: Seconds between checks for new emails
            timeout: Maximum time to wait in seconds (default: 5 minutes)
            
        Returns:
            The verification code if found, None otherwise
        """
        if not self.email_address:
            print("\nError: Email not available. Please run get_messages() first.")
            return None
        
        print(f"\nMonitoring for new messages at {self.email_address}...")
        print(f"Checking every {interval} seconds. Press Ctrl+C to stop.\n")
        
        # Initialize message_ids if needed
        if not hasattr(self, 'message_ids'):
            self.message_ids = []
        
        # Track start time for timeout
        start_time = time.time()
        
        try:
            # Simple animation characters
            animation_chars = ['|', '/', '-', '\\']
            animation_idx = 0
            
            while True:
                # Check if we've exceeded the timeout
                elapsed = time.time() - start_time
                if timeout and elapsed > timeout:
                    print(f"\nTimeout after {timeout} seconds. No verification code received.")
                    return None
                
                try:
                    # Print animation without spamming the console
                    animation_char = animation_chars[animation_idx % len(animation_chars)]
                    print(f"\r{animation_char} Waiting for new messages... ({int(elapsed)}s elapsed) ", end="")
                    animation_idx += 1
                    
                    # Record the check time
                    current_check = datetime.datetime.now()
                    if self.last_check_time:
                        time_since_last = (current_check - self.last_check_time).total_seconds()
                        if self.debug:
                            self.log_debug(f"Time since last check: {time_since_last:.2f} seconds")
                    self.last_check_time = current_check
                    
                    # Get messages
                    result = self.get_messages(silent=True)
                    
                    # If a verification code was found during get_messages, return it
                    if hasattr(self, 'verification_code') and self.verification_code:
                        code = self.verification_code
                        formatted_code = self.format_verification_code(code)
                        print(f"\nVerification code found: {formatted_code}")
                        
                        # Execute callback if provided
                        if callback and callable(callback):
                            callback(code)
                        
                        return code
                    
                    # Check that result has data before processing
                    if not result or not isinstance(result, dict) or 'messages' not in result:
                        if self.debug:
                            self.log_debug("No valid messages returned from get_messages()")
                        time.sleep(interval)
                        continue
                    
                    messages = result['messages']
                    if not messages:
                        time.sleep(interval)
                        continue
                        
                    current_ids = [msg.get('id') for msg in messages if msg.get('id')]
                    
                    # First time checking, consider all messages as new
                    if not self.message_ids:
                        new_ids = current_ids
                    else:
                        new_ids = [m_id for m_id in current_ids if m_id not in self.message_ids]
                    
                    if new_ids:
                        # Clear the animation line
                        print("\r" + " " * 80 + "\r", end="")
                        
                        for msg in messages:
                            if msg.get('id') in new_ids:
                                subject = msg.get('subject', 'No subject')
                                from_email = msg.get('from_email', 'Unknown')
                                date = msg.get('date', 'Unknown')
                                
                                print(f"\nNew message received:")
                                print(f"   From: {from_email}")
                                print(f"   Subject: {subject}")
                                print(f"   Date: {date}\n")
                                
                                # Special handling for Cursor verification emails
                                is_cursor_email = False
                                
                                # Check if it's a Cursor email in various ways
                                if from_email and ("cursor" in from_email.lower() or "cursor.sh" in from_email.lower()):
                                    is_cursor_email = True
                                elif subject and "cursor" in subject.lower():
                                    is_cursor_email = True
                                elif from_email and "no-reply" in from_email.lower():
                                    # Many services use no-reply for verification emails
                                    is_cursor_email = True
                                    
                                if is_cursor_email or True:  # Process all emails to be safe
                                    if is_cursor_email:
                                        print(f"Verification email detected!")
                                        
                                    # Try to find the content in various fields
                                    content = None
                                    for field in ['content', 'body', 'html', 'text']:
                                        if field in msg:
                                            content = msg[field]
                                            print(f"Found '{field}' field in message")
                                            break
                                    
                                    if not content:
                                        print("Could not find message content! Available fields:")
                                        print(f"   {list(msg.keys())}")
                                        continue
                                    
                                    # Extract the verification code
                                    code = self.extract_verification_code(content)
                                    if code:
                                        self.verification_code = code
                                        formatted_code = self.format_verification_code(code)
                                        print(f"\nVERIFICATION CODE FOUND: {formatted_code}\n")
                                        
                                        # Execute callback if provided
                                        if callback and callable(callback):
                                            callback(code)
                                        
                                        return code
                
                    # Update message IDs for next check
                    self.message_ids = current_ids
                    
                    # Wait before checking again
                    time.sleep(interval)
                
                except KeyboardInterrupt:
                    print("\n\nMonitoring stopped by user.")
                    return None
                except Exception as e:
                    if self.debug:
                        self.log_debug(f"Error during monitoring: {str(e)}")
                        traceback.print_exc()
                    print(f"\nError checking messages: {e}")
                    time.sleep(interval)
                    
            return None
                    
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user.")
            return None
        except Exception as e:
            if self.debug:
                self.log_debug(f"Critical error in monitoring: {str(e)}")
                traceback.print_exc()
            print(f"\nError: {e}")
            return None

def main():
    # Create API instance
    api = TempMailAPI()
    
    # Check for debug mode
    if "--debug" in sys.argv:
        api.debug = True
        print("+-------------------------------+")
        print("| DEBUG MODE ENABLED            |")
        print("| Detailed logs will be written |")
        print("| to temp_mail_debug.log        |")
        print("+-------------------------------+")
        
        # Clear previous debug file
        with open(api.log_file, "w", encoding="utf-8") as f:
            f.write(f"Debug session started at {datetime.datetime.now()}\n")
    
    # Show welcome message and instructions
    print("\n===== CURSOR EMAIL VERIFICATION TOOL =====")
    print("This tool generates a temporary email and detects verification codes")
    print("sent by Cursor to facilitate account activation.")
    print("===========================================\n")
    
    # Initialize - get token and cookie
    print("Initializing connection to temporary email service...")
    if api.initialize():
        # Get initial email
        result = api.get_messages()
        
        if result and api.email_address:
            print(f"\nTemporary email generated: {api.email_address}")
            print(f"Email address will remain active for this session")
            print(f"Use this email for your Cursor verification\n")
            
            print("Instructions:")
            print("1. Copy the email address shown above")
            print("2. Use it to register or verify your Cursor account")
            print("3. Wait for the verification code to arrive")
            print("4. The code will be automatically detected and displayed\n")
            
            # Monitor for new emails with animation
            print("Starting email monitoring...")
            print("Press Ctrl+C to stop at any time\n")
            api.monitor_for_new_emails()
        else:
            print("\nERROR: Could not get email address. Check your connection.")
            print("If the problem persists, try restarting the script.")
    else:
        print("\nERROR: Initialization failed. Cannot connect to email service.")
        print("Check your internet connection and try again.")
        
    # Show final message
    print("\nThank you for using the Cursor Email Verification Tool!\n")

if __name__ == "__main__":
    main() 