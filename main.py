#!/usr/bin/env python3
"""
Minimal PyQt application example.
"""

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel


class MainWindow(QMainWindow):
    """
    Main application window.
    """
    
    def __init__(self):
        """
        Initialize the main window.
        """
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """
        Initialize the user interface.
        """
        # Local variables
        central_widget = QWidget()
        layout = QVBoxLayout()
        label = QLabel("Hello, PyQt!")
        button = QPushButton("Нажми меня")
        
        # Setup layout
        layout.addWidget(label)
        layout.addWidget(button)
        central_widget.setLayout(layout)
        
        # Connect button signal
        button.clicked.connect(self.on_button_clicked)
        
        # Setup window
        self.setCentralWidget(central_widget)
        self.setWindowTitle("Minimal PyQt App")
        self.setGeometry(100, 100, 300, 200)
    
    def on_button_clicked(self):
        """
        Handle button click event.
        """
        # Local variables
        label = self.centralWidget().layout().itemAt(0).widget()
        label.setText("Минимальная программа на Python")


def main():
    """
    Main entry point of the application.
    """
    # Local variables
    app = QApplication(sys.argv)
    window = MainWindow()
    
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

