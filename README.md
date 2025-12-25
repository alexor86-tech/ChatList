# ChatList

Minimal PyQt application example.

## Installation

1. Create a virtual environment:
```bash
python3 -m venv venv
```

2. Activate the virtual environment:
```bash
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running

Activate the virtual environment (if not already activated) and run:
```bash
source venv/bin/activate
python main.py
```

## Building Executable

To create a standalone executable file:

1. Install PyInstaller (if not already installed):
```bash
source venv/bin/activate
pip install pyinstaller
```

2. Build the executable:
```bash
pyinstaller --onefile --windowed --name ChatList main.py
```

The executable will be created in the `dist/` directory as `ChatList`.

You can run it directly:
```bash
./dist/ChatList
```

## Description

Simple PyQt5 application with a window containing a label and a button. Clicking the button changes the label text.