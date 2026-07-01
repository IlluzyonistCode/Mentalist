# Mentalist

![Python](https://img.shields.io/badge/Python-3776AB.svg?style=flat-square&logo=Python&logoColor=white)  ![Plotly](https://img.shields.io/badge/Plotly-3F4F75.svg?style=flat-square&logo=Plotly&logoColor=white)  ![pandas](https://img.shields.io/badge/pandas-150458.svg?style=flat-square&logo=pandas&logoColor=white)

## Overview

Mentalist is a Python desktop automation framework with a web UI bridge via Eel. It automates interactions on both Windows (pywinauto) and Android (uiautomator2), processes natural language input from in-game conversations, and authenticates to remote servers via HMAC challenge-response with SSL certificate pinning.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Contributing](#contributing)
- [License](#license)

---

## Features

|      | Component         | Details                                                                                                                                                                                                                                                          |
| :--- | :---------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ⚙️  | **Architecture**  | <ul><li>Python-based desktop automation framework</li><li>Web UI layer powered by `eel` (Python ↔ browser bridge)</li><li>Dual-platform automation: Windows (`pywinauto`) & Android (`uiautomator2`)</li><li>Config-driven behavior via `config.txt` & `.env`</li></ul> |
| 🔩 | **Code Quality**  | <ul><li>Dependency-pinned via `requirements.txt` for reproducibility</li><li>Environment variables managed with `python-dotenv`</li><li>Async support via `nest_asyncio` for nested event loops</li><li>No evidence of a linter or formatter config (e.g., no `.flake8`, `pyproject.toml`)</li></ul> |
| 📄 | **Documentation** | <ul><li>`LICENSE` file present — project is formally licensed</li><li>`config.txt` serves as lightweight runtime documentation</li><li>No dedicated docs folder, wiki, or docsite detected</li><li>No inline docstring standards enforced</li></ul> |
| 🔌 | **Integrations**  | <ul><li>**Browser automation** via `undetected-playwright-patch` (anti-bot evasion)</li><li>**Android device control** via `uiautomator2`</li><li>**Windows GUI automation** via `pywinauto` + `PyAutoGUI` + `PyGetWindow`</li><li>**HTTP client** via `requests`</li><li>**NTP time sync** via `ntplib`</li><li>**Audio playback** via `playsound3`</li></ul> |
| 🧩 | **Modularity**    | <ul><li>Separation of UI (`eel`) from automation logic</li><li>Platform-specific automation isolated by library (`pywinauto` vs `uiautomator2`)</li><li>Config externalized — runtime behavior adjustable without code changes</li><li>No formal plugin or module registry detected</li></ul> |

---

## Project Structure

```
└── Mentalist/
    ├── admin_cli.py
    ├── analytics.py
    ├── auth_client.py
    ├── auth_decorator.py
    ├── auth_protection.py
    ├── booster.py
    ├── build.py
    ├── config.txt
    ├── data_protection.py
    ├── favicon.ico
    ├── favicon.png
    ├── LICENSE
    ├── mastermind.py
    ├── mentalist_cli.py
    ├── mentalist_gui.py
    ├── README.md
    ├── requirements.txt
    ├── spinner.py
    ├── stalker.py
    ├── tracker.py
    ├── translations.py
    ├── updater.py
    └── utils.py
```

---

## Getting Started

### Prerequisites

- Python 3.10+ / Node.js 18+ *(depending on the stack above)*

### Installation

```sh
git clone "https://github.com/IlluzyonistCode/Mentalist
cd Mentalist"
pip install -r requirements.txt
```

### Usage

```sh
python main.py
```

---

## Contributing

- [Report Issues](https://github.com/IlluzyonistCode/Mentalist/issues)
- [Submit Pull Requests](https://github.com/IlluzyonistCode/Mentalist/pulls)
- [Discussions](https://github.com/IlluzyonistCode/Mentalist/discussions)

---

## License

Distributed under the [AGPL-3.0](LICENSE) license.
