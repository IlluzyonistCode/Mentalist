from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
from mentalist import Tracker, Booster, Stalker, Spinner, MentalistModule, GLOBAL_CONFIG, banner, Style, Fore, Back

app = Flask(__name__, template_folder='gui/templates', static_folder='gui/static')

# Словарь для хранения активных экземпляров модулей
active_modules = {}

def _initialize_modules():
    """Инициализирует все доступные модули Mentalist."""
    module_classes = [Tracker, Booster, Stalker]
    if os.name == 'nt':
        module_classes.append(Spinner)

    for module_class in module_classes:
        module_name = module_class.__name__
        try:
            instance = module_class()
            if instance.is_valid:
                active_modules[module_name] = instance
                print(f"Модуль {module_name} инициализирован.")
            else:
                # Output any initialization errors to console
                print(f"Модуль {module_name} не инициализирован корректно.")
        except Exception as e:
            print(f"Ошибка при инициализации модуля {module_name}: {e}")

@app.before_first_request
def setup_modules():
    _initialize_modules()

@app.context_processor
def inject_global_data():
    return {'now': datetime.utcnow()}

@app.route('/')
def index():
    modules_data = {}
    for name, module in active_modules.items():
        modules_data[name] = {
            'status': module.status,
            'is_running': module._thread and module._thread.is_alive()
        }
    return render_template('index.html', modules=modules_data)

@app.route('/module/<module_name>')
def module_detail(module_name):
    module = active_modules.get(module_name)
    if not module:
        return f"Модуль {module_name} не найден.", 404
    
    module_info = {
        'status': module.status,
        'output': module.get_output(),
        'is_running': module._thread and module._thread.is_alive()
    }
    return render_template('module_detail.html', module_name=module_name, module_info=module_info)

@app.route('/api/start/<module_name>', methods=['POST'])
def start_module(module_name):
    module = active_modules.get(module_name)
    if not module:
        return jsonify(success=False, message=f"Модуль {module_name} не найден."), 404
    
    if module._thread and module._thread.is_alive():
        return jsonify(success=False, message=f"Модуль {module_name} уже запущен."), 400
    
    try:
        module.start()
        return jsonify(success=True, message=f"Модуль {module_name} запущен.")
    except Exception as e:
        return jsonify(success=False, message=f"Ошибка при запуске {module_name}: {str(e)}"), 500

@app.route('/api/stop/<module_name>', methods=['POST'])
def stop_module(module_name):
    module = active_modules.get(module_name)
    if not module:
        return jsonify(success=False, message=f"Модуль {module_name} не найден."), 404
    
    if not (module._thread and module._thread.is_alive()):
        return jsonify(success=False, message=f"Модуль {module_name} не запущен."), 400
    
    try:
        module.stop()
        return jsonify(success=True, message=f"Модуль {module_name} остановлен.")
    except Exception as e:
        return jsonify(success=False, message=f"Ошибка при остановке {module_name}: {str(e)}"), 500

@app.route('/api/status/<module_name>')
def module_status(module_name):
    module = active_modules.get(module_name)
    if not module:
        return jsonify(success=False, message=f"Модуль {module_name} не найден."), 404
    
    output = module.get_output()
    # Apply colorama styles for display in the <pre> tag
    formatted_output = output.replace(Style.BRIGHT + Fore.RED, '<span class="console-red-bright">') \
                             .replace(Style.BRIGHT + Fore.YELLOW, '<span class="console-yellow-bright">') \
                             .replace(Style.BRIGHT + Fore.GREEN, '<span class="console-green-bright">') \
                             .replace(Style.BRIGHT + Fore.CYAN, '<span class="console-cyan-bright">') \
                             .replace(Style.BRIGHT + Fore.BLUE, '<span class="console-blue-bright">') \
                             .replace(Style.BRIGHT + Fore.MAGENTA, '<span class="console-magenta-bright">') \
                             .replace(Style.BRIGHT + Fore.WHITE, '<span class="console-white-bright">') \
                             .replace(Style.DIM, '<span class="console-dim">') \
                             .replace(Back.RED, '<span class="console-bg-red">') \
                             .replace(Back.GREEN, '<span class="console-bg-green">') \
                             .replace(Back.YELLOW, '<span class="console-bg-yellow">') \
                             .replace(Back.CYAN, '<span class="console-bg-cyan">') \
                             .replace(Fore.RESET + Style.RESET_ALL, '</span>') \
                             .replace(Style.RESET_ALL, '</span>') \
                             .replace(Fore.RESET, '</span>') \
                             .replace(Back.RESET, '</span>') \
                             .replace('\n', '<br>')
    # Also handle the banner if it's printed directly by modules
    banner_text = banner()
    if banner_text in formatted_output:
        formatted_output = formatted_output.replace(banner_text, f'<span class="console-banner">{banner_text}</span>')


    return jsonify(
        success=True,
        status=module.status,
        output=formatted_output
    )

@app.route('/api/send_input/<module_name>', methods=['POST'])
def send_module_input(module_name):
    module = active_modules.get(module_name)
    if not module:
        return jsonify(success=False, message=f"Модуль {module_name} не найден."), 404
    
    data = request.get_json()
    command = data.get('command')
    
    if not command:
        return jsonify(success=False, message="Команда не предоставлена."), 400
    
    try:
        module.send_input(command)
        return jsonify(success=True, message="Команда отправлена.")
    except Exception as e:
        return jsonify(success=False, message=f"Ошибка при отправке команды: {str(e)}"), 500

def run_gui():
    print("Запуск Mentalist GUI...")
    # Add a CSS rule for the banner
    # This might need to be added to main.css directly or injected. For now, just logging it.
    print("Не забудьте добавить стили для colorama в gui/static/css/main.css!")
    # Example to add to main.css:
    # .console-red-bright { color: red; font-weight: bold; }
    # .console-yellow-bright { color: yellow; font-weight: bold; }
    # ... and so on for all colors and backgrounds

    app.run(debug=True, host='0.0.0.0', port=5000)
