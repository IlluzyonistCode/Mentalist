import requests
import json
import sys
from dotenv import dotenv_values
from colorama import Back, Fore, Style, init

init(autoreset=True)
requests.packages.urllib3.disable_warnings()

config = dotenv_values('.env')
SERVER_URL = config.get('MENTALIST_SERVER_URL', 'http://localhost:1101')
ADMIN_SECRET = config.get('MENTALIST_ADMIN_SECRET', '')


def get_server_health():
    try:
        response = requests.get(f'{SERVER_URL}/health', timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            uptime_hours = data.get('uptime_seconds', 0) / 3600
            
            print(f'\n{Style.BRIGHT}{Fore.GREEN}🟢 Server Status: Online{Fore.RESET}')
            print(f'{Style.BRIGHT}{Fore.CYAN}Server URL: {SERVER_URL}{Fore.RESET}')
            print(f'{Style.BRIGHT}{Fore.CYAN}Uptime: {uptime_hours:.2f} hours{Fore.RESET}')
            print(f'{Style.BRIGHT}{Fore.CYAN}Total Syncs: {data.get("total_syncs", 0)}{Fore.RESET}')
            print(f'{Style.BRIGHT}{Fore.CYAN}Active Clients: {data.get("active_clients", 0)}{Fore.RESET}')
            
            return True
    except Exception as e:
        print(f'\n{Style.BRIGHT}{Fore.RED}🔴 Server Status: Offline{Fore.RESET}')
        print(f'{Style.BRIGHT}{Fore.YELLOW}Error: {str(e)}{Fore.RESET}')
        
        return False

def get_user_by_id(user_id):
    response = requests.get(
        f'{SERVER_URL}/admin/users',
        headers={'X-Admin-Secret': ADMIN_SECRET}
    )
    
    if response.status_code != 200:
        print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {response.text}{Fore.RESET}')
        
        return
    
    users = response.json()['users']
    user = next((u for u in users if u['id'] == user_id), None)
    
    if not user:
        print(f'{Style.BRIGHT}{Fore.RED}❌ User with ID {user_id} not found{Fore.RESET}')
        
        return

    return user

def create_user(permissions=31):
    response = requests.post(
        f'{SERVER_URL}/admin/create_user',
        headers={
            'X-Admin-Secret': ADMIN_SECRET,
            'Content-Type': 'application/json'
        },
        json={'permissions': permissions}
    )
    
    if response.status_code == 200:
        data = response.json()

        print(f'\n{Style.BRIGHT}{Fore.GREEN}✅ User created successfully!{Fore.RESET}')
        print(f'{Style.BRIGHT}{Fore.CYAN}API Key: {Fore.YELLOW}{data["api_key"]}{Fore.RESET}')
        print(f'{Style.BRIGHT}{Fore.CYAN}Permissions: {Fore.YELLOW}{data["permissions"]}{Fore.RESET}')
        print(f'\n{Style.BRIGHT}{Fore.YELLOW}User should add this to their .env file:{Fore.RESET}')
        print(f'{Style.BRIGHT}{Back.BLUE}MENTALIST_SERVER_API_KEY={data["api_key"]}{Back.RESET}')

    else:
        print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {response.text}{Fore.RESET}')

def list_users():
    response = requests.get(
        f'{SERVER_URL}/admin/users',
        headers={'X-Admin-Secret': ADMIN_SECRET}
    )
    
    if response.status_code == 200:
        data = response.json()
        users = data['users']
        
        print(f'\n{Style.BRIGHT}{Fore.CYAN}📋 Total Users: {len(users)}{Fore.RESET}\n')
        print(f'{Style.BRIGHT}{"="*140}{Style.RESET_ALL}')
        
        for user in users:
            status_icon = f'{Fore.GREEN}✅' if user['status'] == 1 else f'{Fore.RED}❌'
            status_text = 'Active' if user['status'] == 1 else 'Disabled'
            perms = user['permissions']
            
            modules = []
            if perms & 1: modules.append(f'{Fore.GREEN}Tracker{Fore.RESET}')
            if perms & 2: modules.append(f'{Fore.BLUE}Stalker{Fore.RESET}')
            if perms & 4: modules.append(f'{Fore.MAGENTA}Booster{Fore.RESET}')
            if perms & 8: modules.append(f'{Fore.YELLOW}Spinner{Fore.RESET}')
            if perms & 16: modules.append(f'{Fore.RED}Mastermind{Fore.RESET}')
            
            print(f'{Style.BRIGHT}{Fore.CYAN}ID: {user["id"]}{Fore.RESET} | {status_icon} {status_text}{Fore.RESET}')
            print(f'{Style.BRIGHT}{Fore.YELLOW}API Key: {Fore.WHITE}{user["api_key"][:48]}...{Fore.RESET}')
            print(f'{Style.BRIGHT}{Fore.CYAN}Modules: {", ".join(modules) if modules else f"{Fore.RED}None{Fore.RESET}"}{Fore.RESET}')
            print(f'{Style.BRIGHT}{Fore.CYAN}Created: {Fore.WHITE}{user["created_at"]}{Fore.RESET}')
            print(f'{Style.BRIGHT}{Fore.CYAN}Last Seen: {Fore.WHITE}{user["last_connection"] or "Never"}{Fore.RESET}')
            
            usage_str = (f'{Fore.GREEN}T:{user["usage"]["tracker"]}{Fore.RESET} '
                        f'{Fore.BLUE}S:{user["usage"]["stalker"]}{Fore.RESET} '
                        f'{Fore.MAGENTA}B:{user["usage"]["booster"]}{Fore.RESET} '
                        f'{Fore.YELLOW}Sp:{user["usage"]["spinner"]}{Fore.RESET} '
                        f'{Fore.RED}M:{user["usage"]["mastermind"]}{Fore.RESET}')
            
            print(f'{Style.BRIGHT}{Fore.CYAN}Usage: {usage_str}')
            
            if user.get('bearer_token'):
                print(f'{Style.BRIGHT}{Fore.CYAN}Bearer Token: {Fore.WHITE}{user["bearer_token"][:32]}...{Fore.RESET}')
            
            if user.get('tracker_api_keys'):
                print(f'{Style.BRIGHT}{Fore.CYAN}Tracker Keys: {Fore.WHITE}{user["tracker_api_keys"][:64]}...{Fore.RESET}')
            
            if user.get('stalker_api_keys'):
                print(f'{Style.BRIGHT}{Fore.CYAN}Stalker Keys: {Fore.WHITE}{user["stalker_api_keys"][:64]}...{Fore.RESET}')
            
            print(f'{Style.BRIGHT}{"-"*140}{Style.RESET_ALL}')

    else:
        print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {response.text}{Fore.RESET}')

def show_user_details(user_id):
    user = get_user_by_id(user_id)
    
    if not user:
        return
    
    print(f'\n{Style.BRIGHT}{Fore.CYAN}{"="*80}{Fore.RESET}')
    print(f'{Style.BRIGHT}{Fore.GREEN}USER DETAILS{Fore.RESET}')
    print(f'{Style.BRIGHT}{Fore.CYAN}{"="*80}{Fore.RESET}\n')
    
    status_icon = f'{Fore.GREEN}✅' if user['status'] == 1 else f'{Fore.RED}❌'
    status_text = 'Active' if user['status'] == 1 else 'Disabled'
    
    print(f'{Style.BRIGHT}{Fore.CYAN}Status: {status_icon} {status_text}{Fore.RESET}')
    print(f'{Style.BRIGHT}{Fore.CYAN}User ID: {Fore.WHITE}{user["id"]}{Fore.RESET}')
    print(f'{Style.BRIGHT}{Fore.CYAN}API Key: {Fore.YELLOW}{user["api_key"]}{Fore.RESET}')
    print(f'{Style.BRIGHT}{Fore.CYAN}Permissions: {Fore.WHITE}{user["permissions"]}{Fore.RESET}')
    print(f'{Style.BRIGHT}{Fore.CYAN}Created: {Fore.WHITE}{user["created_at"]}{Fore.RESET}')
    print(f'{Style.BRIGHT}{Fore.CYAN}Last Connection: {Fore.WHITE}{user["last_connection"] or "Never"}{Fore.RESET}\n')
    
    perms = user['permissions']
    print(f'{Style.BRIGHT}{Fore.YELLOW}Module Access:{Fore.RESET}')
    print(f'  {Fore.GREEN}✅ Tracker{Fore.RESET}' if perms & 1 else f'  {Fore.RED}❌ Tracker{Fore.RESET}')
    print(f'  {Fore.GREEN}✅ Stalker{Fore.RESET}' if perms & 2 else f'  {Fore.RED}❌ Stalker{Fore.RESET}')
    print(f'  {Fore.GREEN}✅ Booster{Fore.RESET}' if perms & 4 else f'  {Fore.RED}❌ Booster{Fore.RESET}')
    print(f'  {Fore.GREEN}✅ Spinner{Fore.RESET}' if perms & 8 else f'  {Fore.RED}❌ Spinner{Fore.RESET}')
    print(f'  {Fore.GREEN}✅ Mastermind{Fore.RESET}' if perms & 16 else f'  {Fore.RED}❌ Mastermind{Fore.RESET}')
    
    print(f'\n{Style.BRIGHT}{Fore.YELLOW}Usage Statistics:{Fore.RESET}')
    print(f'  {Fore.GREEN}Tracker: {user["usage"]["tracker"]} requests{Fore.RESET}')
    print(f'  {Fore.BLUE}Stalker: {user["usage"]["stalker"]} requests{Fore.RESET}')
    print(f'  {Fore.MAGENTA}Booster: {user["usage"]["booster"]} requests{Fore.RESET}')
    print(f'  {Fore.YELLOW}Spinner: {user["usage"]["spinner"]} requests{Fore.RESET}')
    print(f'  {Fore.RED}Mastermind: {user["usage"]["mastermind"]} requests{Fore.RESET}')
    
    total_requests = sum(user["usage"].values())
    print(f'\n{Style.BRIGHT}{Fore.CYAN}Total Requests: {Fore.WHITE}{total_requests}{Fore.RESET}')
    
    if user.get('bearer_token'):
        print(f'\n{Style.BRIGHT}{Fore.YELLOW}Bearer Token:{Fore.RESET}')
        print(f'{Style.BRIGHT}{Fore.WHITE}{user["bearer_token"]}{Fore.RESET}')
    
    if user.get('tracker_api_keys'):
        print(f'\n{Style.BRIGHT}{Fore.YELLOW}Tracker API Keys:{Fore.RESET}')
        print(f'{Style.BRIGHT}{Fore.WHITE}{user["tracker_api_keys"]}{Fore.RESET}')
    
    if user.get('stalker_api_keys'):
        print(f'\n{Style.BRIGHT}{Fore.YELLOW}Stalker API Keys:{Fore.RESET}')
        print(f'{Style.BRIGHT}{Fore.WHITE}{user["stalker_api_keys"]}{Fore.RESET}')
    
    print(f'\n{Style.BRIGHT}{Fore.CYAN}{"="*80}{Fore.RESET}')

def disable_user(user_id):
    user = get_user_by_id(user_id)
    
    if not user:
        return
    
    api_key = user['api_key']
    
    response = requests.post(
        f'{SERVER_URL}/admin/disable_user',
        headers={
            'X-Admin-Secret': ADMIN_SECRET,
            'Content-Type': 'application/json'
        },
        json={'api_key': api_key}
    )
    
    if response.status_code == 200:
        print(f'{Style.BRIGHT}{Fore.GREEN}✅ User #{user_id} disabled ({api_key[:32]}...){Fore.RESET}')
    
    else:
        print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {response.text}{Fore.RESET}')

def delete_user(user_id):
    user = get_user_by_id(user_id)
    
    if not user:
        return
    
    api_key = user['api_key']
    
    confirm = input(f'{Style.BRIGHT}{Fore.RED}⚠️  Are you sure you want to DELETE user #{user_id} ({api_key[:32]}...)? (yes/no): {Fore.RESET}')
    
    if confirm.lower() != 'yes':
        print(f'{Style.BRIGHT}{Fore.YELLOW}Cancelled.{Fore.RESET}')
        return
    
    response = requests.post(
        f'{SERVER_URL}/admin/delete_user',
        headers={
            'X-Admin-Secret': ADMIN_SECRET,
            'Content-Type': 'application/json'
        },
        json={'api_key': api_key}
    )
    
    if response.status_code == 200:
        print(f'{Style.BRIGHT}{Fore.GREEN}✅ User #{user_id} deleted ({api_key[:32]}...){Fore.RESET}')
    
    else:
        print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {response.text}{Fore.RESET}')

def set_permissions(user_id, permissions):
    user = get_user_by_id(user_id)
    
    if not user:
        return
    
    api_key = user['api_key']
    
    response = requests.post(
        f'{SERVER_URL}/admin/set_permissions',
        headers={
            'X-Admin-Secret': ADMIN_SECRET,
            'Content-Type': 'application/json'
        },
        json={'api_key': api_key, 'permissions': permissions}
    )
    
    if response.status_code == 200:
        print(f'{Style.BRIGHT}{Fore.GREEN}✅ Permissions updated for user #{user_id} to {permissions}{Fore.RESET}')
    
    else:
        print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {response.text}{Fore.RESET}')

def main():
    if not ADMIN_SECRET:
        print(f'{Style.BRIGHT}{Back.RED}❌ MENTALIST_ADMIN_SECRET not found in .env{Back.RESET}')
        sys.exit(1)
    
    print(f'\n{Style.BRIGHT}{Fore.RED}{"="*60}{Fore.RESET}')
    print(f'{Style.BRIGHT}{Fore.RED}Men{Fore.YELLOW}tal{Fore.WHITE}ist {Fore.RED}ADMIN PANEL{Fore.RESET}')
    print(f'{Style.BRIGHT}{Fore.RED}{"="*60}{Fore.RESET}')
    
    get_server_health()
    
    print(f'\n{Style.BRIGHT}{Fore.YELLOW}Commands:{Fore.RESET}')
    print(f'{Style.BRIGHT}{Fore.GREEN}  1.{Fore.RESET} Create user')
    print(f'{Style.BRIGHT}{Fore.GREEN}  2.{Fore.RESET} List users')
    print(f'{Style.BRIGHT}{Fore.GREEN}  3.{Fore.RESET} Show user details')
    print(f'{Style.BRIGHT}{Fore.GREEN}  4.{Fore.RESET} Disable user')
    print(f'{Style.BRIGHT}{Fore.GREEN}  5.{Fore.RESET} Delete user')
    print(f'{Style.BRIGHT}{Fore.GREEN}  6.{Fore.RESET} Set permissions')
    print(f'{Style.BRIGHT}{Fore.GREEN}  7.{Fore.RESET} Server health')
    print(f'{Style.BRIGHT}{Fore.GREEN}  8.{Fore.RESET} Exit')
    
    while True:
        choice = input(f'\n{Style.BRIGHT}{Fore.RED}>{Fore.RESET} ').strip()
        
        if choice == '1':
            print(f'\n{Style.BRIGHT}{Fore.YELLOW}Permissions:{Fore.RESET}')
            print(f'{Style.BRIGHT}{Fore.GREEN}  1  ={Fore.RESET} Tracker only')
            print(f'{Style.BRIGHT}{Fore.BLUE}  2  ={Fore.RESET} Stalker only')
            print(f'{Style.BRIGHT}{Fore.MAGENTA}  4  ={Fore.RESET} Booster only')
            print(f'{Style.BRIGHT}{Fore.YELLOW}  8  ={Fore.RESET} Spinner only')
            print(f'{Style.BRIGHT}{Fore.RED}  16 ={Fore.RESET} Mastermind only')
            print(f'{Style.BRIGHT}{Fore.CYAN}  31 ={Fore.RESET} All modules (default)')

            perms = input(f'{Style.BRIGHT}{Fore.YELLOW}Enter permissions (default 31): {Fore.RESET}').strip()
            create_user(int(perms) if perms else 31)
        
        elif choice == '2':
            list_users()
        
        elif choice == '3':
            user_id = input(f'{Style.BRIGHT}{Fore.YELLOW}Enter user ID: {Fore.RESET}').strip()
            
            if user_id.isdigit():
                show_user_details(int(user_id))
            
            else:
                print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid ID{Fore.RESET}')
        
        elif choice == '4':
            user_id = input(f'{Style.BRIGHT}{Fore.YELLOW}Enter user ID to disable: {Fore.RESET}').strip()
            
            if user_id.isdigit():
                disable_user(int(user_id))
            
            else:
                print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid ID{Fore.RESET}')
        
        elif choice == '5':
            user_id = input(f'{Style.BRIGHT}{Fore.YELLOW}Enter user ID to delete: {Fore.RESET}').strip()
            
            if user_id.isdigit():
                delete_user(int(user_id))
            
            else:
                print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid ID{Fore.RESET}')
        
        elif choice == '6':
            user_id = input(f'{Style.BRIGHT}{Fore.YELLOW}Enter user ID: {Fore.RESET}').strip()
            perms = input(f'{Style.BRIGHT}{Fore.YELLOW}Enter new permissions: {Fore.RESET}').strip()
            
            if user_id.isdigit() and perms.isdigit():
                set_permissions(int(user_id), int(perms))
            
            else:
                print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid input{Fore.RESET}')
        
        elif choice == '7':
            get_server_health()
        
        elif choice == '8':
            print(f'\n{Style.BRIGHT}{Fore.GREEN}Goodbye!{Fore.RESET}')
            
            break


if __name__ == '__main__':
    main()
