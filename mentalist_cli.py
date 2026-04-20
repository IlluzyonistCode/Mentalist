import os
import sys
import warnings

warnings.filterwarnings('ignore', category=Warning, module='gevent')

from gevent import monkey

if sys.platform != 'darwin':
    monkey.patch_all(subprocess=False)

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS

    ms_playwright_path = os.path.join(base_path, 'ms-playwright')

    if os.path.exists(ms_playwright_path):
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = ms_playwright_path

    for node_path in [
        os.path.join(base_path, 'playwright', 'driver', 'node.exe'),
        os.path.join(base_path, 'ms-playwright', 'node.exe'),
        os.path.join(base_path, 'node', 'node.exe'),
    ]:
        if os.path.exists(node_path):
            os.environ['PLAYWRIGHT_NODEJS_PATH'] = node_path
            break

from colorama import Fore, Back, Style, init
from utils import set_launch_mode, check_updates_on_startup, banner
from tracker import Tracker
from booster import Booster
from stalker import Stalker
from spinner import SpinnerDesktop, SpinnerMobile

set_launch_mode('CLI')


def main():
	try:
		init(autoreset=True)

		while True:
			banner()

			check_updates_on_startup()

			module_classes = [Tracker, Booster, Stalker, SpinnerMobile]

			if sys.platform == 'win32':
				module_classes.append(SpinnerDesktop)

			modules = []
			disabled_modules = []

			for module_class in module_classes:
				instance = module_class()

				if instance.is_valid:
					modules.append(instance)

				else:
					module_name = getattr(module_class, 'menu_name', module_class.__name__)

					disabled_modules.append(module_name)

			print()

			for i, module in enumerate(modules):
				module_name = getattr(module, 'menu_name', module.__class__.__name__)

				print(f'{Style.BRIGHT}{Fore.GREEN}{i + 1}. {Fore.RESET}{Back.GREEN}{module_name}')

			if len(disabled_modules) < len(modules):
				print(f'{Style.BRIGHT}{Fore.GREEN}{len(modules) + 1}. {Fore.RESET}{Back.GREEN}Updater')

			if disabled_modules:
				print()

				for module_name in disabled_modules:
					print(f'{Style.BRIGHT}{Fore.RED}Module {module_name} is disabled due to configuration errors.{Fore.RESET}')

			if not modules:
				print(f'\n{Style.BRIGHT}{Back.RED}All modules failed to load! Check your config.txt file.{Back.RESET}')
				input('Press Enter to exit.')

				break

			while True:
				try:
					choice = int(input(f'\n{Style.BRIGHT}{Fore.YELLOW}Module to run:{Fore.RESET} '))

					if 1 <= choice <= len(modules):
						module = modules[int(choice) - 1]

						break

					if choice == len(modules) + 1:
						if modules:
							modules[0].check_updates_menu()

						else:
							print('No modules available to run updater.')

					else:
						print(f'\n{Style.BRIGHT}{Back.RED}Incorrect choice!{Back.RESET}')
				except ValueError:
					print(f'\n{Style.BRIGHT}{Back.RED}Incorrect choice!{Back.RESET}')

			module.run()
	except KeyboardInterrupt:
		pass


if __name__ == '__main__':
	main()
