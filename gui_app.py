from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string(
        "<h1>Mentalist GUI (В разработке)</h1>"
        "<p>Установите GUI_ENABLED=false в .env для использования CLI.</p>"
        "<p>Для запуска GUI убедитесь, что все зависимости установлены: <code>pip install -r requirements.txt</code></p>"
        "<p>После запуска перейдите по адресу: <a href='http://127.0.0.1:5000'>http://127.0.0.1:5000</a></p>"
    )

def run_gui():
    print("Запуск Mentalist GUI...")
    app.run(debug=True, host='0.0.0.0', port=5000)
