import os
import sys
import time
import subprocess
import json
import sqlite3
import uuid

# Import the TempMailAPI for email verification
try:
    from temp_mail_api import TempMailAPI
except ImportError:
    print("Error: temp_mail_api.py module not found. Make sure it's in the same directory.")
    sys.exit(1)

def print_step(step_number, description):
    """Print a step header with formatting"""
    print(f"\n{'=' * 80}")
    print(f"Step {step_number}: {description}")
    print(f"{'=' * 80}\n")

def check_if_process_running(process_name):
    """Check if a process is running"""
    try:
        output = subprocess.check_output(['tasklist', '/FI', f'IMAGENAME eq {process_name}'])
        return process_name.lower() in output.decode().lower()
    except:
        return False

def kill_process(process_name):
    """Kill a running process"""
    try:
        subprocess.run(['taskkill', '/F', '/IM', process_name], check=False)
        print(f"Successfully terminated {process_name}")
        return True
    except:
        print(f"Failed to terminate {process_name}")
        return False

def remove_directory(directory):
    """Remove a directory and its contents"""
    directory = os.path.expandvars(directory)
    if os.path.exists(directory):
        try:
            subprocess.run(['rd', '/s', '/q', directory], shell=True, check=False)
            print(f"Successfully removed directory: {directory}")
        except:
            print(f"Failed to remove directory: {directory}")

def update_machine_guid():
    """Update Windows machine GUID"""
    try:
        # Generate new GUID
        new_guid = str(uuid.uuid4())
        
        # Registry path for machine GUID
        registry_path = r"HKLM\SOFTWARE\Microsoft\Cryptography"
        
        # Update registry using reg command
        subprocess.run(['reg', 'add', registry_path, '/v', 'MachineGuid', '/t', 'REG_SZ', '/d', new_guid, '/f'], check=True)
        print(f"Successfully updated machine GUID to: {new_guid}")
        return new_guid
    except Exception as e:
        print(f"Error updating machine GUID: {e}")
        return None

def generate_random_identifiers():
    """Generate random identifiers for Cursor"""
    try:
        identifiers = {
            'device_id': str(uuid.uuid4()),
            'user_id': str(uuid.uuid4()),
            'session_id': str(uuid.uuid4()),
            'installation_id': str(uuid.uuid4()),
            'machine_id': str(uuid.uuid4())
        }
        print("Successfully generated random identifiers")
        return identifiers
    except Exception as e:
        print(f"Error generating identifiers: {e}")
        return None

def modify_storage_json(identifiers):
    """Modify Cursor's storage.json file with new identifiers"""
    try:
        storage_path = os.path.expandvars(r"%APPDATA%\Cursor\storage.json")
        if not os.path.exists(storage_path):
            print("storage.json not found")
            return False

        with open(storage_path, 'r', encoding='utf-8') as f:
            storage_data = json.load(f)

        # Update identifiers in storage data
        storage_data['deviceId'] = identifiers['device_id']
        storage_data['userId'] = identifiers['user_id']
        storage_data['sessionId'] = identifiers['session_id']
        storage_data['installationId'] = identifiers['installation_id']
        storage_data['machineId'] = identifiers['machine_id']

        # Write back to file
        with open(storage_path, 'w', encoding='utf-8') as f:
            json.dump(storage_data, f, indent=2)

        print("Successfully modified storage.json")
        return True
    except Exception as e:
        print(f"Error modifying storage.json: {e}")
        return False

def update_sqlite_database(identifiers):
    """Update Cursor's SQLite database with new identifiers"""
    try:
        db_path = os.path.expandvars(r"%APPDATA%\Cursor\Cursor.db")
        if not os.path.exists(db_path):
            print("Cursor.db not found")
            return False

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Update identifiers in database
        cursor.execute("UPDATE users SET device_id = ?, user_id = ?, session_id = ?, installation_id = ?, machine_id = ?",
                      (identifiers['device_id'], identifiers['user_id'], identifiers['session_id'],
                       identifiers['installation_id'], identifiers['machine_id']))

        conn.commit()
        conn.close()
        print("Successfully updated SQLite database")
        return True
    except Exception as e:
        print(f"Error updating database: {e}")
        return False

def create_cursor_account():
    """Create a new Cursor account using a temporary email"""
    print_step("A", "Creating a temporary email for Cursor account verification")
    
    # Create and initialize the TempMailAPI
    api = TempMailAPI()
    if not api.initialize():
        print("Failed to initialize temporary email service. Check your internet connection.")
        retry = input("Would you like to retry? (yes/no): ").lower()
        if retry in ['yes', 'y']:
            return create_cursor_account()
        return False
    
    # Get initial email address
    result = api.get_messages()
    if not result or not api.email_address:
        print("Failed to generate temporary email address. The service may be down.")
        retry = input("Would you like to retry? (yes/no): ").lower()
        if retry in ['yes', 'y']:
            return create_cursor_account()
        return False
    
    # Show email to user
    print(f"\nTemporary email generated: {api.email_address}")
    
    # Ask if they want to copy to clipboard
    try:
        import pyperclip
        pyperclip.copy(api.email_address)
        print("Email address copied to clipboard!")
    except ImportError:
        print("(Install 'pyperclip' package to enable clipboard copy)")
    except Exception:
        print("Could not copy to clipboard - please copy the email address manually.")

    print("\nInstructions for creating Cursor account:")
    print("1. Go to https://cursor.sh and click 'Sign Up'")
    print("2. Copy and paste this email address: " + api.email_address)
    print("3. Complete the registration form with any password")
    print("4. Click 'Sign Up' and wait for the verification email")
    print("5. This tool will automatically detect the verification code")
    
    print("\nWaiting for verification email... (Press Ctrl+C to cancel)")
    print("This may take up to 5 minutes. If no email arrives, you might need to try again.")
    
    try:
        # Monitor for verification emails and get the code (5 minute timeout)
        verification_code = api.monitor_for_new_emails(timeout=300)
        
        if verification_code:
            print(f"\n==========================================================")
            print(f"VERIFICATION CODE DETECTED: {verification_code}")
            print(f"==========================================================")
            print("\nPlease enter this code in the verification page.")
            print("After entering the code, your Cursor account will be created.")
            
            # Try to format the code for better readability
            try:
                formatted_code = api.format_verification_code(verification_code)
                print(f"Code with spaces: {formatted_code}")
            except:
                pass
                
            # Ask if they want to copy to clipboard
            try:
                import pyperclip
                pyperclip.copy(verification_code)
                print("Code copied to clipboard!")
            except:
                pass
            
            # Wait for the user to complete the verification
            input("\nPress Enter once you've completed the verification...")
            print("\nAccount creation completed successfully!")
            return True
        else:
            # If no code was found but monitoring stopped
            print("\nNo verification code was detected.")
            print("Possible issues:")
            print("1. Email service is experiencing delays")
            print("2. Cursor's verification system might be down")
            print("3. The verification email might have been filtered as spam")
            
            choice = input("\nDid you complete the account creation process anyway? (yes/no): ").lower()
            if choice in ['yes', 'y']:
                return True
                
            # Ask if they want to try again
            retry = input("Would you like to try with a new email address? (yes/no): ").lower()
            if retry in ['yes', 'y']:
                return create_cursor_account()
            return False
        
    except KeyboardInterrupt:
        print("\nAccount creation process cancelled by user")
        return False
    except Exception as e:
        print(f"\nError during account creation: {e}")
        retry = input("Would you like to retry? (yes/no): ").lower()
        if retry in ['yes', 'y']:
            return create_cursor_account()
        return False

def download_cursor():
    """Show Cursor download link and handle user choice"""
    try:
        print("\nCursor download link: https://www.cursor.com/")
        print("\nPlease download and install Cursor manually from the website.")
        
        while True:
            choice = input("\nHave you completed the download and installation? (yes/no): ").lower()
            if choice in ['yes', 'y']:
                print("Great! Continuing with the setup...")
                return True
            elif choice in ['no', 'n']:
                print("Please complete the installation and try again.")
                return False
            else:
                print("Please answer with 'yes' or 'no'")
    except Exception as e:
        print(f"Error during download process: {e}")
        return False

def setup_cursor():
    """Launch Cursor once and close it"""
    try:
        cursor_exe = os.path.expandvars(r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe")
        if os.path.exists(cursor_exe):
            subprocess.Popen([cursor_exe])
            print("Launched Cursor. Waiting 10 seconds before closing...")
            time.sleep(10)
            if check_if_process_running("Cursor.exe"):
                kill_process("Cursor.exe")
                time.sleep(2)
            return True
        else:
            print(f"Cursor executable not found at {cursor_exe}")
            return False
    except Exception as e:
        print(f"Error setting up Cursor: {e}")
        return False

def main():
    """Main function to run the Cursor bypass process"""
    print("\n" + "=" * 80)
    print("CURSOR BYPASS TOOL")
    print("=" * 80 + "\n")
    
    try:
        # Ask if user has a Cursor account
        print("Do you already have a Cursor account?")
        print("1. Yes, I already have an account")
        print("2. No, I need to create an account")
        
        account_choice = input("> ").strip()
        
        if account_choice == "2":
            # User needs to create an account
            account_created = create_cursor_account()
            if not account_created:
                print("\nAccount creation process was not completed successfully.")
                print("You can try again later or create an account manually at https://cursor.sh")
                choice = input("\nDo you want to continue with the bypass process anyway? (yes/no): ").lower()
                if choice not in ['yes', 'y']:
                    print("Exiting...")
                    return
        
        # Step 1: Terminate processes
        print_step(1, "Checking and terminating Cursor processes")
        if check_if_process_running("Cursor.exe"):
            kill_process("Cursor.exe")
        if check_if_process_running("cursor-updater.exe"):
            kill_process("cursor-updater.exe")
        time.sleep(2)
        
        # Step 2: Uninstall Cursor
        print_step(2, "Uninstalling Cursor")
        cursor_uninstaller = os.path.expandvars(r"%LOCALAPPDATA%\Programs\cursor\unins000.exe")
        if os.path.exists(cursor_uninstaller):
            subprocess.run([cursor_uninstaller, "/S"], shell=True, check=False)
            print("Waiting for uninstallation to complete...")
            time.sleep(10)
        else:
            print("Cursor uninstaller not found. Skipping uninstallation.")
        
        # Step 3: Delete directories
        print_step(3, "Deleting Cursor directories")
        directories_to_remove = [
            r"%APPDATA%\Cursor",
            r"%LOCALAPPDATA%\cursor-updater",
            r"%LOCALAPPDATA%\Programs\cursor"
        ]
        for directory in directories_to_remove:
            remove_directory(directory)
        
        # Step 4: Update machine GUID
        print_step(4, "Updating Windows machine GUID")
        if not update_machine_guid():
            print("Failed to update machine GUID")
            choice = input("Do you want to continue anyway? (yes/no): ").lower()
            if choice not in ['yes', 'y']:
                print("Exiting...")
                return
        
        # Step 5: Download and install Cursor
        print_step(5, "Downloading and installing Cursor")
        if not download_cursor():
            print("Failed to download and install Cursor")
            return
        
        # Step 6: Setup Cursor
        print_step(6, "Launching Cursor once and closing it")
        if not setup_cursor():
            print("Failed to setup Cursor")
            choice = input("Do you want to continue anyway? (yes/no): ").lower()
            if choice not in ['yes', 'y']:
                print("Exiting...")
                return
        
        # Step 7: Generate random identifiers
        print_step(7, "Generating random identifiers")
        identifiers = generate_random_identifiers()
        if not identifiers:
            print("Failed to generate identifiers")
            choice = input("Do you want to continue anyway? (yes/no): ").lower()
            if choice not in ['yes', 'y']:
                print("Exiting...")
                return
        
        # Step 8: Modify storage.json
        print_step(8, "Modifying storage.json with random identifiers")
        if not modify_storage_json(identifiers):
            print("Failed to modify storage.json")
            choice = input("Do you want to continue anyway? (yes/no): ").lower()
            if choice not in ['yes', 'y']:
                print("Exiting...")
                return
        
        # Step 9: Update database
        print_step(9, "Updating SQLite database with random identifiers")
        if not update_sqlite_database(identifiers):
            print("Failed to update database")
            choice = input("Do you want to continue anyway? (yes/no): ").lower()
            if choice not in ['yes', 'y']:
                print("Exiting...")
                return
        
        print("\n" + "=" * 80)
        print("SETUP COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print("\nYou can now launch Cursor and enjoy all Pro features!")
        
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nAn error occurred: {e}")
        choice = input("Do you want to try again? (yes/no): ").lower()
        if choice in ['yes', 'y']:
            main()
        else:
            sys.exit(1)

if __name__ == "__main__":
    main() 