#!/usr/bin/env python3
"""
ChatList - Main application file.
GUI application for comparing AI model responses.
"""

import sys
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import markdown
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QCheckBox,
    QComboBox, QLabel, QLineEdit, QMessageBox, QFileDialog, QMenuBar,
    QMenu, QStatusBar, QHeaderView, QProgressBar, QDialog, QFormLayout,
    QDialogButtonBox, QSpinBox, QAbstractItemView, QRadioButton, QButtonGroup,
    QGroupBox, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont
import db
import models
import network
import prompt_improver


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RequestWorker(QThread):
    """
    Worker thread for sending API requests.
    """
    
    finished = pyqtSignal(int, str, str, str)  # model_id, model_name, api_id, response/error
    progress = pyqtSignal(int, int)  # current, total
    
    def __init__(self, model_list: List[models.Model], prompt: str, 
                 timeout: int = 30, max_retries: int = 3):
        """
        Initialize worker thread.
        
        Args:
            model_list [in]: List of models to query
            prompt [in]: Prompt text
            timeout [in]: Request timeout
            max_retries [in]: Maximum retry attempts
        """
        super().__init__()
        self.model_list = model_list
        self.prompt = prompt
        self.timeout = timeout
        self.max_retries = max_retries
    
    def run(self):
        """
        Execute requests in thread.
        """
        total = len(self.model_list)
        for idx, model in enumerate(self.model_list):
            try:
                response = network.send_prompt_to_model(
                    model, self.prompt, self.timeout, self.max_retries
                )
                self.finished.emit(model.id, model.name, model.api_id, response)
            except network.APIError as e:
                # API-specific error (message already formatted)
                self.finished.emit(model.id, model.name, model.api_id, str(e))
            except ValueError as e:
                # Configuration error (e.g., missing API key)
                self.finished.emit(model.id, model.name, model.api_id, f"Ошибка конфигурации: {str(e)}")
            except Exception as e:
                # Other errors
                error_msg = str(e) if str(e) else type(e).__name__
                self.finished.emit(model.id, model.name, model.api_id, f"Ошибка: {error_msg}")
            
            self.progress.emit(idx + 1, total)


class ModelDialog(QDialog):
    """
    Dialog for adding/editing models.
    """
    
    def __init__(self, parent=None, model: Optional[models.Model] = None):
        """
        Initialize model dialog.
        
        Args:
            parent [in]: Parent widget
            model [in]: Model to edit (None for new model)
        """
        super().__init__(parent)
        self.model = model
        self.init_ui()
    
    def init_ui(self):
        """
        Initialize dialog UI.
        """
        # Local variables
        layout = QFormLayout()
        self.name_edit = QLineEdit()
        self.model_id_edit = QLineEdit()
        self.api_url_edit = QLineEdit()
        self.api_id_edit = QLineEdit()
        self.is_active_checkbox = QCheckBox("Активна")
        self.is_active_checkbox.setChecked(True)
        
        # If editing, populate fields
        if self.model:
            self.setWindowTitle("Редактировать модель")
            self.name_edit.setText(self.model.name)
            self.model_id_edit.setText(self.model.model_id)
            self.api_url_edit.setText(self.model.api_url)
            self.api_id_edit.setText(self.model.api_id)
            self.is_active_checkbox.setChecked(self.model.is_active == 1)
        else:
            self.setWindowTitle("Добавить модель")
        
        # Add fields to layout
        layout.addRow("Название модели:", self.name_edit)
        
        # Model ID field with tooltip
        model_id_label = QLabel("Идентификатор модели (model_id):")
        model_id_label.setToolTip("Идентификатор модели для использования в API запросах (например, openai/gpt-4 или gpt-4)")
        layout.addRow(model_id_label, self.model_id_edit)
        self.model_id_edit.setPlaceholderText("например: openai/gpt-4")
        
        layout.addRow("API URL:", self.api_url_edit)
        
        # API ID field with tooltip
        api_id_label = QLabel("Имя переменной окружения с API-ключом:")
        api_id_label.setToolTip("Имя переменной окружения из файла .env, содержащей API-ключ (например, OPENROUTER_API_KEY)")
        layout.addRow(api_id_label, self.api_id_edit)
        self.api_id_edit.setPlaceholderText("например: OPENROUTER_API_KEY")
        
        layout.addRow("", self.is_active_checkbox)
        
        # Add buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def get_data(self) -> Dict[str, Any]:
        """
        Get dialog data.
        
        Returns:
            Dict[str, Any]: Model data
        """
        return {
            "name": self.name_edit.text().strip(),
            "model_id": self.model_id_edit.text().strip(),
            "api_url": self.api_url_edit.text().strip(),
            "api_id": self.api_id_edit.text().strip(),
            "is_active": 1 if self.is_active_checkbox.isChecked() else 0
        }


class ManageModelsDialog(QDialog):
    """
    Dialog for managing models (view, edit, delete, enable/disable).
    """
    
    def __init__(self, parent=None):
        """
        Initialize manage models dialog.
        
        Args:
            parent [in]: Parent widget
        """
        super().__init__(parent)
        self.init_ui()
        self.load_models()
    
    def init_ui(self):
        """
        Initialize dialog UI.
        """
        # Local variables
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("Управление моделями")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Table
        self.models_table = QTableWidget()
        self.models_table.setColumnCount(6)
        self.models_table.setHorizontalHeaderLabels([
            "Название", "Model ID", "API URL", "Переменная окружения", "Активна", "Действия"
        ])
        self.models_table.horizontalHeader().setStretchLastSection(True)
        self.models_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.models_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.models_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.models_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.models_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.models_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.models_table.setAlternatingRowColors(True)
        self.models_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.models_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.models_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        layout.addWidget(self.models_table)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        add_button = QPushButton("Добавить")
        add_button.clicked.connect(self.add_model)
        
        edit_button = QPushButton("Редактировать")
        edit_button.clicked.connect(self.edit_selected_model)
        
        delete_button = QPushButton("Удалить")
        delete_button.clicked.connect(self.delete_selected_model)
        
        toggle_active_button = QPushButton("Включить/Отключить")
        toggle_active_button.clicked.connect(self.toggle_active)
        
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)
        
        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(edit_button)
        buttons_layout.addWidget(delete_button)
        buttons_layout.addWidget(toggle_active_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(close_button)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        
        # Setup window
        self.setWindowTitle("Управление моделями")
        self.setMinimumSize(900, 500)
    
    def load_models(self):
        """
        Load all models into table.
        """
        try:
            # Local variables
            all_models = models.get_all_models()
            self.models_table.setRowCount(len(all_models))
            
            for row, model in enumerate(all_models):
                # Name
                name_item = QTableWidgetItem(model.name)
                name_item.setData(Qt.UserRole, model.id)
                self.models_table.setItem(row, 0, name_item)
                
                # Model ID
                model_id_item = QTableWidgetItem(model.model_id)
                self.models_table.setItem(row, 1, model_id_item)
                
                # API URL
                url_item = QTableWidgetItem(model.api_url)
                self.models_table.setItem(row, 2, url_item)
                
                # API ID
                api_id_item = QTableWidgetItem(model.api_id)
                self.models_table.setItem(row, 3, api_id_item)
                
                # Active checkbox
                active_checkbox = QCheckBox()
                active_checkbox.setChecked(model.is_active == 1)
                active_checkbox.setEnabled(False)  # Disable direct editing
                self.models_table.setCellWidget(row, 4, active_checkbox)
                
                # Actions buttons
                actions_widget = QWidget()
                actions_layout = QHBoxLayout()
                actions_layout.setContentsMargins(2, 2, 2, 2)
                
                edit_btn = QPushButton("✏")
                edit_btn.setMaximumWidth(30)
                edit_btn.setToolTip("Редактировать")
                edit_btn.clicked.connect(lambda checked, m=model: self.edit_model(m))
                
                delete_btn = QPushButton("🗑")
                delete_btn.setMaximumWidth(30)
                delete_btn.setToolTip("Удалить")
                delete_btn.clicked.connect(lambda checked, m=model: self.delete_model(m))
                
                actions_layout.addWidget(edit_btn)
                actions_layout.addWidget(delete_btn)
                actions_layout.addStretch()
                
                actions_widget.setLayout(actions_layout)
                self.models_table.setCellWidget(row, 5, actions_widget)
                
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки моделей: {str(e)}")
    
    def get_selected_model_id(self) -> Optional[int]:
        """
        Get selected model ID from table.
        
        Returns:
            Optional[int]: Model ID or None if nothing selected
        """
        # Local variables
        current_row = self.models_table.currentRow()
        
        if current_row < 0:
            return None
        
        name_item = self.models_table.item(current_row, 0)
        if name_item:
            return name_item.data(Qt.UserRole)
        return None
    
    def add_model(self):
        """
        Add new model.
        """
        dialog = ModelDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            is_valid, error_msg = models.validate_model_config(
                data["name"], data["model_id"], data["api_url"], data["api_id"]
            )
            if not is_valid:
                QMessageBox.warning(self, "Ошибка валидации", error_msg)
                return
            
            new_model = models.create_model(
                data["name"], data["model_id"], data["api_url"], data["api_id"], data["is_active"]
            )
            if new_model:
                QMessageBox.information(self, "Успех", "Модель успешно добавлена")
                self.load_models()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось добавить модель")
    
    def edit_selected_model(self):
        """
        Edit selected model.
        """
        # Local variables
        model_id = self.get_selected_model_id()
        
        if model_id is None:
            QMessageBox.information(self, "Информация", "Пожалуйста, выберите модель для редактирования")
            return
        
        model = models.load_model_config(model_id)
        if not model:
            QMessageBox.critical(self, "Ошибка", "Не удалось загрузить модель")
            return
        
        self.edit_model(model)
    
    def edit_model(self, model: models.Model):
        """
        Edit model.
        
        Args:
            model [in]: Model to edit
        """
        dialog = ModelDialog(self, model)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            is_valid, error_msg = models.validate_model_config(
                data["name"], data["model_id"], data["api_url"], data["api_id"]
            )
            if not is_valid:
                QMessageBox.warning(self, "Ошибка валидации", error_msg)
                return
            
            success = models.update_model(
                model.id, data["name"], data["model_id"], data["api_url"], 
                data["api_id"], data["is_active"]
            )
            if success:
                QMessageBox.information(self, "Успех", "Модель успешно обновлена")
                self.load_models()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось обновить модель")
    
    def delete_selected_model(self):
        """
        Delete selected model.
        """
        # Local variables
        model_id = self.get_selected_model_id()
        
        if model_id is None:
            QMessageBox.information(self, "Информация", "Пожалуйста, выберите модель для удаления")
            return
        
        model = models.load_model_config(model_id)
        if not model:
            QMessageBox.critical(self, "Ошибка", "Не удалось загрузить модель")
            return
        
        self.delete_model(model)
    
    def delete_model(self, model: models.Model):
        """
        Delete model with confirmation.
        
        Args:
            model [in]: Model to delete
        """
        reply = QMessageBox.question(
            self, "Подтверждение удаления",
            f"Вы уверены, что хотите удалить модель '{model.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success = models.delete_model(model.id)
            if success:
                QMessageBox.information(self, "Успех", "Модель успешно удалена")
                self.load_models()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось удалить модель")
    
    def toggle_active(self):
        """
        Toggle active status of selected model.
        """
        # Local variables
        model_id = self.get_selected_model_id()
        
        if model_id is None:
            QMessageBox.information(self, "Информация", "Пожалуйста, выберите модель")
            return
        
        model = models.load_model_config(model_id)
        if not model:
            QMessageBox.critical(self, "Ошибка", "Не удалось загрузить модель")
            return
        
        # Toggle active status
        new_active = 0 if (model.is_active == 1) else 1
        success = models.update_model(model.id, is_active=new_active)
        
        if success:
            status_text = "включена" if (new_active == 1) else "отключена"
            QMessageBox.information(self, "Успех", f"Модель {status_text}")
            self.load_models()
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось изменить статус модели")


class MarkdownViewDialog(QDialog):
    """
    Dialog for viewing markdown-formatted text.
    """
    
    def __init__(self, title: str, text: str, parent=None):
        """
        Initialize markdown view dialog.
        
        Args:
            title [in]: Dialog title
            text [in]: Text to display (will be rendered as markdown)
            parent [in]: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)
        
        # Local variables
        layout = QVBoxLayout()
        
        # Text editor for markdown display
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        
        # Convert markdown to HTML and display
        try:
            html = markdown.markdown(
                text,
                extensions=['extra', 'codehilite', 'nl2br', 'sane_lists']
            )
            # Add basic CSS for better formatting
            html = f"""
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    font-size: 14px;
                    line-height: 1.6;
                    padding: 10px;
                }}
                pre {{
                    background-color: #f4f4f4;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    padding: 10px;
                    overflow-x: auto;
                }}
                code {{
                    background-color: #f4f4f4;
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: 'Courier New', monospace;
                }}
                pre code {{
                    background-color: transparent;
                    padding: 0;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    margin-top: 1em;
                    margin-bottom: 0.5em;
                }}
                blockquote {{
                    border-left: 4px solid #ddd;
                    margin-left: 0;
                    padding-left: 1em;
                    color: #666;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
            </style>
            {html}
            """
            self.text_edit.setHtml(html)
        except Exception as e:
            # Fallback to plain text if markdown conversion fails
            logging.error(f"Error converting markdown: {e}")
            self.text_edit.setPlainText(text)
        
        layout.addWidget(self.text_edit)
        
        # Close button
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)
        
        self.setLayout(layout)


class PromptDialog(QDialog):
    """
    Dialog for creating/editing prompts.
    """
    
    def __init__(self, parent=None, prompt_id: Optional[int] = None):
        """
        Initialize prompt dialog.
        
        @param [in] parent Parent widget
        @param [in] prompt_id Prompt ID to edit (None for new prompt)
        """
        super().__init__(parent)
        self.prompt_id = prompt_id
        self.init_ui()
        
        if prompt_id:
            self.load_prompt_data()
    
    def init_ui(self):
        """
        Initialize dialog UI.
        """
        # Local variables
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        self.prompt_text_edit = QTextEdit()
        self.prompt_text_edit.setMinimumHeight(150)
        form_layout.addRow("Промт *:", self.prompt_text_edit)
        
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Теги через запятую (необязательно)")
        form_layout.addRow("Теги:", self.tags_edit)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        title = "Редактировать промт" if self.prompt_id else "Создать промт"
        self.setWindowTitle(title)
        self.setMinimumWidth(600)
    
    def load_prompt_data(self):
        """
        Load prompt data for editing.
        """
        try:
            prompt_data = db.get_prompt(self.prompt_id)
            if prompt_data:
                self.prompt_text_edit.setPlainText(prompt_data["prompt"])
                self.tags_edit.setText(prompt_data["tags"] if prompt_data["tags"] else "")
        except Exception as e:
            logger.error(f"Error loading prompt data: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки данных промта: {str(e)}")
    
    def get_prompt_data(self) -> Dict[str, Any]:
        """
        Get prompt data from form.
        
        @return [out] Dictionary with prompt_text and tags
        """
        return {
            "prompt_text": self.prompt_text_edit.toPlainText().strip(),
            "tags": self.tags_edit.text().strip() or None
        }
    
    def accept(self):
        """
        Validate and accept dialog.
        """
        data = self.get_prompt_data()
        
        if not data["prompt_text"]:
            QMessageBox.warning(self, "Предупреждение", "Поле 'Промт' обязательно для заполнения.")
            return
        
        super().accept()


class PromptImprovementDialog(QDialog):
    """
    Dialog for improving prompts using AI.
    """
    
    def __init__(self, parent=None, original_prompt: str = "", 
                 improver: Optional[prompt_improver.PromptImprover] = None):
        """
        Initialize prompt improvement dialog.
        
        Args:
            parent [in]: Parent widget
            original_prompt [in]: Original prompt text
            improver [in]: PromptImprover instance
        """
        super().__init__(parent)
        self.original_prompt = original_prompt
        self.improver = improver
        self.selected_prompt = None
        self.init_ui()
    
    def init_ui(self):
        """
        Initialize dialog UI.
        """
        # Local variables
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("Улучшение промта")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Original prompt section
        original_group = QGroupBox("Исходный промт")
        original_layout = QVBoxLayout()
        self.original_text = QTextEdit()
        self.original_text.setPlainText(self.original_prompt)
        self.original_text.setReadOnly(True)
        self.original_text.setMaximumHeight(100)
        original_layout.addWidget(self.original_text)
        original_group.setLayout(original_layout)
        layout.addWidget(original_group)
        
        # Model selection
        model_layout = QHBoxLayout()
        model_label = QLabel("Модель для улучшения:")
        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)
        # Load active models
        try:
            active_models = models.get_active_models()
            for model in active_models:
                self.model_combo.addItem(model.name, model)
        except Exception as e:
            logger.error(f"Error loading models: {e}")
        
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        layout.addLayout(model_layout)
        
        # Adaptation type
        adaptation_layout = QHBoxLayout()
        adaptation_label = QLabel("Тип адаптации:")
        self.adaptation_combo = QComboBox()
        self.adaptation_combo.addItem("Общее улучшение", "general")
        self.adaptation_combo.addItem("Для кода", "code")
        self.adaptation_combo.addItem("Для анализа", "analysis")
        self.adaptation_combo.addItem("Для творчества", "creative")
        adaptation_layout.addWidget(adaptation_label)
        adaptation_layout.addWidget(self.adaptation_combo)
        layout.addLayout(adaptation_layout)
        
        # Progress indicator
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)
        
        # Results section
        results_group = QGroupBox("Результаты")
        results_layout = QVBoxLayout()
        
        # Improved version
        improved_label = QLabel("Улучшенная версия:")
        self.improved_text = QTextEdit()
        self.improved_text.setReadOnly(True)
        self.improved_text.setMaximumHeight(100)
        results_layout.addWidget(improved_label)
        results_layout.addWidget(self.improved_text)
        
        # Variants
        variants_label = QLabel("Альтернативные варианты:")
        results_layout.addWidget(variants_label)
        
        # Radio buttons for variants
        self.variants_group = QButtonGroup()
        self.variants_layout = QVBoxLayout()
        self.variant_radios = []
        
        # Create placeholder radio buttons (will be populated after improvement)
        for i in range(3):
            radio = QRadioButton()
            radio.setVisible(False)
            self.variant_radios.append(radio)
            self.variants_group.addButton(radio, i)
            self.variants_layout.addWidget(radio)
        
        results_layout.addLayout(self.variants_layout)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        improve_button = QPushButton("Улучшить")
        improve_button.clicked.connect(self.improve_prompt)
        
        insert_button = QPushButton("Подставить в поле ввода")
        insert_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(improve_button)
        buttons_layout.addWidget(insert_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_button)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        
        # Setup window
        self.setWindowTitle("Улучшение промта")
        self.setMinimumSize(700, 600)
    
    def improve_prompt(self):
        """
        Improve prompt using AI.
        """
        # Local variables
        current_model_data = self.model_combo.currentData()
        
        if not current_model_data:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, выберите модель для улучшения")
            return
        
        if not self.original_prompt.strip():
            QMessageBox.warning(self, "Предупреждение", "Исходный промт пуст")
            return
        
        # Show progress
        self.progress_label.setText("Улучшение промта...")
        self.progress_label.setVisible(True)
        self.setEnabled(False)
        
        try:
            # Get adaptation type
            adaptation_type = self.adaptation_combo.currentData()
            
            # Get number of variants from parent settings if available
            num_variants = 3  # Default
            if self.parent() and hasattr(self.parent(), 'improvement_num_variants'):
                num_variants = self.parent().improvement_num_variants
            
            # Improve prompt with variants
            result = self.improver.improve_with_variants(
                self.original_prompt, current_model_data, adaptation_type
            )
            
            # Limit variants to configured number
            if "variants" in result:
                result["variants"] = result["variants"][:num_variants]
            
            # Display improved version
            improved_text = result.get("improved", "")
            if improved_text:
                self.improved_text.setPlainText(improved_text)
                # Set improved as default selection
                self.selected_prompt = improved_text
            else:
                self.improved_text.setPlainText("Не удалось получить улучшенную версию")
            
            # Display variants
            variants = result.get("variants", [])
            for i, radio in enumerate(self.variant_radios):
                if i < len(variants):
                    # Truncate for display
                    display_text = variants[i]
                    if len(display_text) > 60:
                        display_text = display_text[:60] + "..."
                    radio.setText(f"Вариант {i + 1}: {display_text}")
                    radio.setVisible(True)
                    # Store full variant text
                    radio.setProperty("variant_text", variants[i])
                    # Connect signal to update selection
                    radio.toggled.connect(self.on_variant_selected)
                else:
                    radio.setVisible(False)
            
            # If no improved version but have variants, select first variant
            if not improved_text and variants:
                self.variant_radios[0].setChecked(True)
                self.selected_prompt = variants[0]
            
            self.progress_label.setText("Готово")
            
        except Exception as e:
            logger.error(f"Error improving prompt: {e}")
            error_msg = str(e) if str(e) else type(e).__name__
            QMessageBox.critical(
                self, "Ошибка",
                f"Ошибка при улучшении промта: {error_msg}"
            )
            self.progress_label.setVisible(False)
        finally:
            self.setEnabled(True)
            # Hide progress after a delay
            QTimer.singleShot(2000, lambda: self.progress_label.setVisible(False))
    
    def on_variant_selected(self, checked: bool):
        """
        Handle variant selection.
        
        Args:
            checked [in]: Whether radio button is checked
        """
        if checked:
            # Find which radio was checked
            for radio in self.variant_radios:
                if radio.isChecked():
                    variant_text = radio.property("variant_text")
                    if variant_text:
                        self.selected_prompt = variant_text
                    break
    
    def get_selected_prompt(self) -> Optional[str]:
        """
        Get selected prompt variant.
        
        Returns:
            Optional[str]: Selected prompt text or None
        """
        # Check if any variant is selected via radio button
        for radio in self.variant_radios:
            if radio.isVisible() and radio.isChecked():
                variant_text = radio.property("variant_text")
                if variant_text:
                    return variant_text
        
        # If no variant selected, return improved version
        improved = self.improved_text.toPlainText().strip()
        if improved and improved != "Не удалось получить улучшенную версию":
            return improved
        
        # Fallback to original
        return self.original_prompt if self.original_prompt.strip() else None


class ViewPromptsDialog(QDialog):
    """
    Dialog for viewing saved prompts.
    """
    
    prompt_selected = pyqtSignal(int)  # Emitted when prompt is selected for loading
    
    def __init__(self, parent=None):
        """
        Initialize view prompts dialog.
        
        Args:
            parent [in]: Parent widget
        """
        super().__init__(parent)
        self.init_ui()
        self.load_prompts()
    
    def init_ui(self):
        """
        Initialize dialog UI.
        """
        # Local variables
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("Сохраненные промты")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Поиск:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по тексту промта или тегам...")
        self.search_input.textChanged.connect(self.filter_prompts)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Table
        self.prompts_table = QTableWidget()
        self.prompts_table.setColumnCount(4)
        self.prompts_table.setHorizontalHeaderLabels([
            "Дата", "Промт", "Теги", "Действия"
        ])
        self.prompts_table.horizontalHeader().setStretchLastSection(True)
        self.prompts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.prompts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.prompts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.prompts_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.prompts_table.setAlternatingRowColors(True)
        self.prompts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.prompts_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.prompts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.prompts_table.setSortingEnabled(True)
        
        layout.addWidget(self.prompts_table)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        create_button = QPushButton("Создать")
        create_button.clicked.connect(self.create_prompt)
        
        load_button = QPushButton("Загрузить выбранный")
        load_button.clicked.connect(self.load_selected_prompt)
        
        edit_button = QPushButton("Редактировать выбранный")
        edit_button.clicked.connect(self.edit_selected_prompt)
        
        delete_button = QPushButton("Удалить выбранный")
        delete_button.clicked.connect(self.delete_selected_prompt)
        
        clear_all_button = QPushButton("Очистить все")
        clear_all_button.clicked.connect(self.clear_all_prompts)
        
        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.load_prompts)
        
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)
        
        buttons_layout.addWidget(create_button)
        buttons_layout.addWidget(load_button)
        buttons_layout.addWidget(edit_button)
        buttons_layout.addWidget(delete_button)
        buttons_layout.addWidget(clear_all_button)
        buttons_layout.addWidget(refresh_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(close_button)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        
        # Setup window
        self.setWindowTitle("Просмотр сохраненных промтов")
        self.setMinimumSize(900, 600)
    
    def load_prompts(self):
        """
        Load all prompts into table.
        """
        try:
            # Local variables
            all_prompts = db.get_all_prompts(sort_by="date", order="DESC")
            self.all_prompts = all_prompts  # Store for filtering
            self.filter_prompts()
        except Exception as e:
            logger.error(f"Error loading prompts: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки промтов: {str(e)}")
    
    def filter_prompts(self):
        """
        Filter prompts based on search text.
        """
        # Local variables
        search_text = self.search_input.text().lower().strip()
        
        if not hasattr(self, 'all_prompts'):
            return
        
        # Filter prompts
        if search_text:
            filtered_prompts = [
                p for p in self.all_prompts
                if search_text in p["prompt"].lower() or
                   (p["tags"] and search_text in p["tags"].lower())
            ]
        else:
            filtered_prompts = self.all_prompts
        
        # Update table
        self.prompts_table.setRowCount(len(filtered_prompts))
        
        for row, prompt in enumerate(filtered_prompts):
            # Date
            date_str = prompt["date"][:10] if len(prompt["date"]) > 10 else prompt["date"]
            date_item = QTableWidgetItem(date_str)
            date_item.setData(Qt.UserRole, prompt["id"])
            self.prompts_table.setItem(row, 0, date_item)
            
            # Prompt text (truncated for display)
            prompt_text = prompt["prompt"]
            display_text = prompt_text[:100] + "..." if len(prompt_text) > 100 else prompt_text
            prompt_item = QTableWidgetItem(display_text)
            prompt_item.setToolTip(prompt_text)  # Full text in tooltip
            prompt_item.setData(Qt.UserRole, prompt["id"])
            self.prompts_table.setItem(row, 1, prompt_item)
            
            # Tags
            tags_text = prompt["tags"] if prompt["tags"] else ""
            tags_item = QTableWidgetItem(tags_text)
            self.prompts_table.setItem(row, 2, tags_item)
            
            # Actions buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout()
            actions_layout.setContentsMargins(2, 2, 2, 2)
            
            load_btn = QPushButton("Загрузить")
            load_btn.setMaximumWidth(80)
            load_btn.setToolTip("Загрузить промт")
            load_btn.clicked.connect(lambda checked, p_id=prompt["id"]: self.load_prompt(p_id))
            
            edit_btn = QPushButton("Редактировать")
            edit_btn.setMaximumWidth(100)
            edit_btn.setToolTip("Редактировать промт")
            edit_btn.clicked.connect(lambda checked, p_id=prompt["id"]: self.edit_prompt(p_id))
            
            delete_btn = QPushButton("Удалить")
            delete_btn.setMaximumWidth(80)
            delete_btn.setToolTip("Удалить промт")
            delete_btn.clicked.connect(lambda checked, p_id=prompt["id"]: self.delete_prompt(p_id))
            
            actions_layout.addWidget(load_btn)
            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(delete_btn)
            actions_layout.addStretch()
            
            actions_widget.setLayout(actions_layout)
            self.prompts_table.setCellWidget(row, 3, actions_widget)
    
    def get_selected_prompt_id(self) -> Optional[int]:
        """
        Get selected prompt ID from table.
        
        Returns:
            Optional[int]: Prompt ID or None if nothing selected
        """
        # Local variables
        current_row = self.prompts_table.currentRow()
        
        if current_row < 0:
            return None
        
        date_item = self.prompts_table.item(current_row, 0)
        if date_item:
            return date_item.data(Qt.UserRole)
        return None
    
    def load_selected_prompt(self):
        """
        Load selected prompt.
        """
        # Local variables
        prompt_id = self.get_selected_prompt_id()
        
        if prompt_id is None:
            QMessageBox.information(self, "Информация", "Пожалуйста, выберите промт")
            return
        
        self.load_prompt(prompt_id)
    
    def load_prompt(self, prompt_id: int):
        """
        Load prompt and close dialog.
        
        Args:
            prompt_id [in]: Prompt ID to load
        """
        self.prompt_selected.emit(prompt_id)
        self.accept()
    
    def create_prompt(self):
        """
        Create a new prompt.
        """
        dialog = PromptDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            try:
                data = dialog.get_prompt_data()
                prompt_id = db.create_prompt(data["prompt_text"], data["tags"])
                QMessageBox.information(self, "Успех", "Промт успешно создан")
                self.load_prompts()
                # Refresh prompts in main window
                if hasattr(self.parent(), 'load_saved_prompts'):
                    self.parent().load_saved_prompts()
            except Exception as e:
                logger.error(f"Error creating prompt: {e}")
                QMessageBox.critical(self, "Ошибка", f"Ошибка создания промта: {str(e)}")
    
    def edit_selected_prompt(self):
        """
        Edit selected prompt.
        """
        # Local variables
        prompt_id = self.get_selected_prompt_id()
        
        if prompt_id is None:
            QMessageBox.information(self, "Информация", "Пожалуйста, выберите промт для редактирования")
            return
        
        self.edit_prompt(prompt_id)
    
    def edit_prompt(self, prompt_id: int):
        """
        Edit prompt.
        
        @param [in] prompt_id Prompt ID to edit
        """
        dialog = PromptDialog(self, prompt_id)
        if dialog.exec_() == QDialog.Accepted:
            try:
                data = dialog.get_prompt_data()
                success = db.update_prompt(prompt_id, data["prompt_text"], data["tags"])
                if success:
                    QMessageBox.information(self, "Успех", "Промт успешно обновлен")
                    self.load_prompts()
                    # Refresh prompts in main window
                    if hasattr(self.parent(), 'load_saved_prompts'):
                        self.parent().load_saved_prompts()
                else:
                    QMessageBox.critical(self, "Ошибка", "Не удалось обновить промт")
            except Exception as e:
                logger.error(f"Error updating prompt: {e}")
                QMessageBox.critical(self, "Ошибка", f"Ошибка обновления промта: {str(e)}")
    
    def delete_selected_prompt(self):
        """
        Delete selected prompt.
        """
        # Local variables
        prompt_id = self.get_selected_prompt_id()
        
        if prompt_id is None:
            QMessageBox.information(self, "Информация", "Пожалуйста, выберите промт для удаления")
            return
        
        self.delete_prompt(prompt_id)
    
    def delete_prompt(self, prompt_id: int):
        """
        Delete prompt with confirmation.
        
        Args:
            prompt_id [in]: Prompt ID to delete
        """
        try:
            prompt_data = db.get_prompt(prompt_id)
            if not prompt_data:
                QMessageBox.critical(self, "Ошибка", "Не удалось загрузить промт")
                return
            
            # Truncate prompt text for confirmation
            prompt_text = prompt_data["prompt"][:50]
            if len(prompt_data["prompt"]) > 50:
                prompt_text += "..."
            
            reply = QMessageBox.question(
                self, "Подтверждение удаления",
                f"Вы уверены, что хотите удалить промт '{prompt_text}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                success = db.delete_prompt(prompt_id)
                if success:
                    QMessageBox.information(self, "Успех", "Промт успешно удален")
                    self.load_prompts()
                    # Emit signal to refresh prompts in main window
                    if hasattr(self.parent(), 'load_saved_prompts'):
                        self.parent().load_saved_prompts()
                else:
                    QMessageBox.critical(self, "Ошибка", "Не удалось удалить промт")
        except Exception as e:
            logger.error(f"Error deleting prompt: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка удаления промта: {str(e)}")
    
    def clear_all_prompts(self):
        """
        Clear all prompts with confirmation.
        """
        try:
            # Get count of prompts
            all_prompts = db.get_all_prompts()
            prompt_count = len(all_prompts)
            
            if prompt_count == 0:
                QMessageBox.information(self, "Информация", "Нет промтов для удаления")
                return
            
            # Confirm deletion
            reply = QMessageBox.question(
                self, "Подтверждение удаления",
                f"Вы уверены, что хотите удалить все {prompt_count} промт(ов)?\n\n"
                "Это действие нельзя отменить!",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                deleted_count = db.delete_all_prompts()
                if deleted_count > 0:
                    QMessageBox.information(
                        self, "Успех",
                        f"Удалено {deleted_count} промт(ов)"
                    )
                    self.load_prompts()
                    # Refresh prompts in main window
                    if hasattr(self.parent(), 'load_saved_prompts'):
                        self.parent().load_saved_prompts()
                else:
                    QMessageBox.critical(self, "Ошибка", "Не удалось удалить промты")
        except Exception as e:
            logger.error(f"Error clearing all prompts: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка удаления промтов: {str(e)}")


class MainWindow(QMainWindow):
    """
    Main application window.
    """
    
    def __init__(self):
        """
        Initialize main window.
        """
        super().__init__()
        
        # Initialize database
        db.init_database()
        
        # Local variables
        self.current_prompt_id = None
        self.temp_results = []  # Temporary results in memory
        self.request_worker = None
        self.prompt_improver = prompt_improver.PromptImprover()
        
        self.init_ui()
        self.load_saved_prompts()
        self.load_settings()
    
    def init_ui(self):
        """
        Initialize user interface.
        """
        # Local variables
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Create menu bar
        self.create_menu_bar()
        
        # Top section: Prompt input
        prompt_section = self.create_prompt_section()
        main_layout.addWidget(prompt_section)
        # Prompt section should not stretch
        main_layout.setStretchFactor(prompt_section, 0)
        
        # Middle section: Results table
        results_section = self.create_results_section()
        main_layout.addWidget(results_section)
        # Results section should stretch to fill available space
        main_layout.setStretchFactor(results_section, 1)
        
        # Bottom section: Action buttons
        buttons_section = self.create_buttons_section()
        main_layout.addWidget(buttons_section)
        # Buttons section should not stretch
        main_layout.setStretchFactor(buttons_section, 0)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готово")
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Setup central widget
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Setup window
        self.setWindowTitle("ChatList - Сравнение AI моделей")
        self.setGeometry(100, 100, 1200, 800)
    
    def create_menu_bar(self):
        """
        Create menu bar.
        """
        # Local variables
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("Файл")
        export_action = file_menu.addAction("Экспортировать выбранные...")
        export_action.triggered.connect(self.export_selected_results)
        settings_action = file_menu.addAction("Настройки...")
        settings_action.triggered.connect(self.show_settings_dialog)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)
        
        # Models menu
        models_menu = menubar.addMenu("Модели")
        add_model_action = models_menu.addAction("Добавить модель...")
        add_model_action.triggered.connect(self.add_model)
        manage_models_action = models_menu.addAction("Управление моделями...")
        manage_models_action.triggered.connect(self.manage_models)
        
        # Prompts menu
        prompts_menu = menubar.addMenu("Промты")
        view_prompts_action = prompts_menu.addAction("Просмотр сохраненных промтов...")
        view_prompts_action.triggered.connect(self.view_saved_prompts)
        
        # Help menu
        help_menu = menubar.addMenu("Справка")
        about_action = help_menu.addAction("О программе")
        about_action.triggered.connect(self.show_about)
    
    def create_prompt_section(self) -> QWidget:
        """
        Create prompt input section.
        
        Returns:
            QWidget: Prompt section widget
        """
        # Local variables
        section = QWidget()
        layout = QVBoxLayout()
        
        # Label
        label = QLabel("Промт:")
        layout.addWidget(label)
        
        # Text input
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText("Введите ваш промт здесь...")
        self.prompt_text.setMaximumHeight(150)
        layout.addWidget(self.prompt_text)
        
        # Bottom row: saved prompts combo and buttons
        bottom_row = QHBoxLayout()
        
        # Saved prompts combo
        saved_label = QLabel("Сохраненные промты:")
        self.saved_prompts_combo = QComboBox()
        self.saved_prompts_combo.setEditable(False)
        # Don't auto-load on selection, user must click "Load Prompt" button
        
        bottom_row.addWidget(saved_label)
        bottom_row.addWidget(self.saved_prompts_combo)
        
        # Tags input
        tags_label = QLabel("Теги:")
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("теги через запятую")
        bottom_row.addWidget(tags_label)
        bottom_row.addWidget(self.tags_input)
        
        # Buttons
        improve_button = QPushButton("Улучшить промт")
        improve_button.clicked.connect(self.show_improve_prompt_dialog)
        load_button = QPushButton("Загрузить промт")
        load_button.clicked.connect(self.load_selected_prompt)
        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send_prompt)
        self.send_button.setDefault(True)
        
        bottom_row.addWidget(improve_button)
        bottom_row.addWidget(load_button)
        bottom_row.addWidget(self.send_button)
        
        layout.addLayout(bottom_row)
        section.setLayout(layout)
        return section
    
    def create_results_section(self) -> QWidget:
        """
        Create results table section.
        
        Returns:
            QWidget: Results section widget
        """
        # Local variables
        section = QWidget()
        layout = QVBoxLayout()
        
        # Label
        label = QLabel("Результаты:")
        layout.addWidget(label)
        
        # Table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Выбрать", "Модель", "Ответ", "Действия"])
        self.results_table.horizontalHeader().setStretchLastSection(False)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        # Enable word wrap for all cells
        self.results_table.setWordWrap(True)
        # Set vertical header to resize rows to content
        self.results_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        # Set minimum height for results table to ensure buttons are visible
        self.results_table.setMinimumHeight(400)
        # Limit maximum row height to prevent extremely tall rows
        # This ensures that long messages are scrollable within the cell
        self.results_table.verticalHeader().setMaximumSectionSize(300)
        
        layout.addWidget(self.results_table)
        # Set stretch factor for results section to take more vertical space
        layout.setStretchFactor(self.results_table, 1)
        section.setLayout(layout)
        return section
    
    def create_buttons_section(self) -> QWidget:
        """
        Create action buttons section.
        
        Returns:
            QWidget: Buttons section widget
        """
        # Local variables
        section = QWidget()
        layout = QHBoxLayout()
        
        # Buttons
        save_button = QPushButton("Сохранить выбранные")
        save_button.clicked.connect(self.save_selected_results)
        
        clear_button = QPushButton("Очистить")
        clear_button.clicked.connect(self.clear_results)
        
        export_button = QPushButton("Экспорт")
        export_button.clicked.connect(self.export_selected_results)
        
        new_query_button = QPushButton("Новый запрос")
        new_query_button.clicked.connect(self.new_query)
        
        layout.addWidget(save_button)
        layout.addWidget(clear_button)
        layout.addWidget(export_button)
        layout.addWidget(new_query_button)
        layout.addStretch()
        
        section.setLayout(layout)
        return section
    
    def load_saved_prompts(self):
        """
        Load saved prompts into combo box.
        """
        try:
            # Local variables
            prompts = db.get_all_prompts(sort_by="date", order="DESC")
            self.saved_prompts_combo.clear()
            self.saved_prompts_combo.addItem("-- Выберите сохраненный промт --", None)
            
            for prompt in prompts:
                # Truncate prompt text for display
                display_text = prompt["prompt"][:50]
                if len(prompt["prompt"]) > 50:
                    display_text += "..."
                self.saved_prompts_combo.addItem(
                    f"{display_text} ({prompt['date'][:10]})",
                    prompt["id"]
                )
        except Exception as e:
            logger.error(f"Error loading saved prompts: {e}")
    
    def load_settings(self):
        """
        Load application settings.
        """
        try:
            # Local variables
            settings = db.get_all_settings()
            self.timeout = int(settings.get("default_timeout", "30"))
            self.max_retries = int(settings.get("max_retries", "3"))
            
            # Load prompt improvement settings
            self.default_improvement_model_id = settings.get("default_improvement_model_id")
            self.improvement_num_variants = int(settings.get("improvement_num_variants", "3"))
            self.default_adaptation_type = settings.get("default_adaptation_type", "general")
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self.timeout = 30
            self.max_retries = 3
            self.default_improvement_model_id = None
            self.improvement_num_variants = 3
            self.default_adaptation_type = "general"
    
    
    def load_selected_prompt(self):
        """
        Load selected prompt from combo box.
        """
        # Local variables
        current_data = self.saved_prompts_combo.currentData()
        
        if current_data is None:
            QMessageBox.information(self, "Информация", "Пожалуйста, выберите сохраненный промт")
            return
        
        try:
            prompt_data = db.get_prompt(current_data)
            if prompt_data:
                # Clear current prompt
                self.prompt_text.clear()
                self.tags_input.clear()
                
                # Set new prompt
                prompt_text_value = prompt_data["prompt"]
                self.prompt_text.setPlainText(prompt_text_value)
                self.prompt_text.update()  # Force update
                
                if prompt_data["tags"]:
                    self.tags_input.setText(prompt_data["tags"])
                else:
                    self.tags_input.clear()
                self.tags_input.update()  # Force update
                
                self.current_prompt_id = current_data
                
                # Load saved results for this prompt
                self.load_saved_results_for_prompt(current_data)
                
                self.status_bar.showMessage(f"Промт загружен (ID: {current_data})")
                
                # Ensure text is visible
                self.prompt_text.ensureCursorVisible()
            else:
                QMessageBox.warning(self, "Предупреждение", "Промт не найден в базе данных")
        except Exception as e:
            logger.error(f"Error loading prompt: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки промта: {str(e)}")
    
    def send_prompt(self):
        """
        Send prompt to all active models.
        """
        # Local variables
        prompt_text = self.prompt_text.toPlainText().strip()
        
        if not prompt_text:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, введите промт")
            return
        
        # Get active models
        active_models = models.get_active_models()
        if not active_models:
            QMessageBox.warning(
                self, "Предупреждение",
                "Активные модели не найдены. Пожалуйста, добавьте модели в меню Модели."
            )
            return
        
        # Clear previous results
        self.clear_results()
        
        # Save prompt to database if new
        if self.current_prompt_id is None:
            try:
                tags = self.tags_input.text().strip() or None
                self.current_prompt_id = db.create_prompt(prompt_text, tags)
                self.load_saved_prompts()  # Refresh combo
                self.status_bar.showMessage("Промт сохранен")
            except Exception as e:
                logger.error(f"Error saving prompt: {e}")
        
        # Disable send button
        self.send_button.setEnabled(False)
        
        # Show progress
        self.progress_bar.setMaximum(len(active_models))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage(f"Отправка в {len(active_models)} моделей...")
        
        # Create and start worker thread
        self.request_worker = RequestWorker(
            active_models, prompt_text, self.timeout, self.max_retries
        )
        self.request_worker.finished.connect(self.on_request_finished)
        self.request_worker.progress.connect(self.on_request_progress)
        self.request_worker.start()
    
    def on_request_progress(self, current: int, total: int):
        """
        Handle request progress update.
        
        Args:
            current [in]: Current request number
            total [in]: Total requests
        """
        self.progress_bar.setValue(current)
    
    def on_request_finished(self, model_id: int, model_name: str, api_id: str, response: str):
        """
        Handle finished request.
        
        Args:
            model_id [in]: Model ID
            model_name [in]: Model name
            api_id [in]: Environment variable name for API key
            response [in]: Response text or error message
        """
        # Add to temporary results
        result = {
            "model_id": model_id,
            "model_name": model_name,
            "api_id": api_id,
            "response": response,
            "selected": False
        }
        self.temp_results.append(result)
        
        # Update table
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        # Checkbox (first column)
        checkbox = QCheckBox()
        checkbox.setChecked(False)
        # Store result index in checkbox data for easy retrieval
        checkbox.setProperty("result_index", len(self.temp_results) - 1)
        self.results_table.setCellWidget(row, 0, checkbox)
        
        # Model name
        model_item = QTableWidgetItem(model_name)
        model_item.setFlags(model_item.flags() & ~Qt.ItemIsEditable)
        # Store result index in item data
        model_item.setData(Qt.UserRole, len(self.temp_results) - 1)
        self.results_table.setItem(row, 1, model_item)
        
        # Response text (multiline)
        response_item = QTableWidgetItem(response)
        response_item.setFlags(response_item.flags() & ~Qt.ItemIsEditable)
        # Enable word wrap for response text
        response_item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.results_table.setItem(row, 2, response_item)
        
        # Actions column - Open button
        actions_widget = QWidget()
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(2, 2, 2, 2)
        
        open_btn = QPushButton("Открыть")
        open_btn.setMaximumWidth(80)
        open_btn.clicked.connect(lambda checked, r=response, m=model_name: self.open_markdown_view(m, r))
        
        actions_layout.addWidget(open_btn)
        actions_layout.addStretch()
        
        actions_widget.setLayout(actions_layout)
        self.results_table.setCellWidget(row, 3, actions_widget)
        
        # Resize row to fit content
        self.results_table.resizeRowToContents(row)
        
        # Check if all requests finished
        if len(self.temp_results) >= len(models.get_active_models()):
            self.progress_bar.setVisible(False)
            # Re-enable send button
            self.send_button.setEnabled(True)
            self.status_bar.showMessage("Все запросы завершены")
    
    def save_selected_results(self):
        """
        Save selected results to database.
        """
        if not self.temp_results:
            QMessageBox.information(self, "Информация", "Нет результатов для сохранения")
            return
        
        if self.current_prompt_id is None:
            QMessageBox.warning(self, "Предупреждение", "Нет промта, связанного с результатами")
            return
        
        # Local variables
        saved_count = 0
        errors = []
        
        try:
            # Iterate through all rows in the table
            for row in range(self.results_table.rowCount()):
                # Get checkbox from first column
                checkbox = self.results_table.cellWidget(row, 0)
                if checkbox and checkbox.isChecked():
                    # Get result index from checkbox property or model item
                    result_index = checkbox.property("result_index")
                    if result_index is None:
                        # Fallback: try to get from model item
                        model_item = self.results_table.item(row, 1)
                        if model_item:
                            result_index = model_item.data(Qt.UserRole)
                    
                    # Validate result index
                    if result_index is not None and 0 <= result_index < len(self.temp_results):
                        result = self.temp_results[result_index]
                        try:
                            db.create_result(
                                self.current_prompt_id,
                                result["model_id"],
                                result["response"]
                            )
                            saved_count += 1
                        except Exception as e:
                            error_msg = f"Ошибка сохранения результата для модели {result['model_name']}: {str(e)}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                    else:
                        logger.warning(f"Invalid result index {result_index} for row {row}")
            
            # Show results
            if saved_count > 0:
                message = f"Сохранено {saved_count} результат(ов) в базу данных"
                if errors:
                    message += f"\n\nОшибки при сохранении:\n" + "\n".join(errors)
                    QMessageBox.warning(self, "Частичный успех", message)
                else:
                    QMessageBox.information(self, "Успех", message)
                self.status_bar.showMessage(f"Сохранено {saved_count} результат(ов)")
            else:
                if errors:
                    QMessageBox.warning(self, "Ошибка", "Не удалось сохранить результаты:\n" + "\n".join(errors))
                else:
                    QMessageBox.information(self, "Информация", "Нет выбранных результатов")
        except Exception as e:
            logger.error(f"Error saving results: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения результатов: {str(e)}")
    
    def clear_results(self):
        """
        Clear results table.
        """
        self.results_table.setRowCount(0)
        self.temp_results = []
        self.status_bar.showMessage("Результаты очищены")
    
    def load_saved_results_for_prompt(self, prompt_id: int):
        """
        Load saved results for a specific prompt and display them in the results table.
        
        Args:
            prompt_id [in]: Prompt ID to load results for
        """
        try:
            # Clear current results
            self.results_table.setRowCount(0)
            self.temp_results = []
            
            # Get saved results from database
            saved_results = db.get_results_by_prompt(prompt_id)
            
            if not saved_results:
                self.status_bar.showMessage("Нет сохраненных результатов для этого промта")
                return
            
            # Load model names for display
            all_models = models.get_all_models()
            model_dict = {model.id: model.name for model in all_models}
            
            # Display results in table
            for result in saved_results:
                model_id = result["model_id"]
                model_name = model_dict.get(model_id, f"Модель ID: {model_id}")
                response_text = result["response_text"]
                
                # Add to temporary results
                temp_result = {
                    "model_id": model_id,
                    "model_name": model_name,
                    "api_id": "",  # Not available for saved results
                    "response": response_text,
                    "selected": False
                }
                self.temp_results.append(temp_result)
                
                # Add row to table
                row = self.results_table.rowCount()
                self.results_table.insertRow(row)
                
                # Checkbox (first column) - unchecked by default for saved results
                checkbox = QCheckBox()
                checkbox.setChecked(False)
                checkbox.setProperty("result_index", len(self.temp_results) - 1)
                self.results_table.setCellWidget(row, 0, checkbox)
                
                # Model name
                model_item = QTableWidgetItem(model_name)
                model_item.setFlags(model_item.flags() & ~Qt.ItemIsEditable)
                model_item.setData(Qt.UserRole, len(self.temp_results) - 1)
                self.results_table.setItem(row, 1, model_item)
                
                # Response text (multiline)
                response_item = QTableWidgetItem(response_text)
                response_item.setFlags(response_item.flags() & ~Qt.ItemIsEditable)
                # Enable word wrap for response text
                response_item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
                self.results_table.setItem(row, 2, response_item)
                
                # Actions column - Open button
                actions_widget = QWidget()
                actions_layout = QHBoxLayout()
                actions_layout.setContentsMargins(2, 2, 2, 2)
                
                open_btn = QPushButton("Открыть")
                open_btn.setMaximumWidth(80)
                open_btn.clicked.connect(lambda checked, r=response_text, m=model_name: self.open_markdown_view(m, r))
                
                actions_layout.addWidget(open_btn)
                actions_layout.addStretch()
                
                actions_widget.setLayout(actions_layout)
                self.results_table.setCellWidget(row, 3, actions_widget)
                
                # Resize row to fit content
                self.results_table.resizeRowToContents(row)
            
            self.status_bar.showMessage(f"Загружено {len(saved_results)} сохраненных результат(ов)")
        except Exception as e:
            logger.error(f"Error loading saved results: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки сохраненных результатов: {str(e)}")
    
    def open_markdown_view(self, model_name: str, response_text: str):
        """
        Open markdown view dialog for a response.
        
        Args:
            model_name [in]: Name of the model
            response_text [in]: Response text to display
        """
        dialog = MarkdownViewDialog(
            f"Ответ от {model_name}",
            response_text,
            self
        )
        dialog.exec_()
    
    def new_query(self):
        """
        Start new query (clear prompt and results).
        """
        self.prompt_text.clear()
        self.tags_input.clear()
        self.current_prompt_id = None
        self.clear_results()
        self.status_bar.showMessage("Готово к новому запросу")
    
    def export_selected_results(self):
        """
        Export selected results to file.
        """
        if not self.temp_results:
            QMessageBox.information(self, "Информация", "Нет результатов для экспорта")
            return
        
        # Get export format from settings
        export_format = db.get_setting("export_format") or "markdown"
        
        # Get file path
        if export_format == "markdown":
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Экспорт результатов", "", "Файлы Markdown (*.md);;Все файлы (*)"
            )
        else:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Экспорт результатов", "", "Файлы JSON (*.json);;Все файлы (*)"
            )
        
        if not file_path:
            return
        
        try:
            # Collect selected results
            selected_results = []
            for idx, result in enumerate(self.temp_results):
                checkbox = self.results_table.cellWidget(idx, 0)
                if checkbox and checkbox.isChecked():
                    selected_results.append(result)
            
            if not selected_results:
                QMessageBox.information(self, "Информация", "Нет выбранных результатов")
                return
            
            # Export based on format
            if export_format == "markdown":
                self.export_to_markdown(file_path, selected_results)
            else:
                self.export_to_json(file_path, selected_results)
            
            QMessageBox.information(self, "Успех", "Результаты успешно экспортированы")
        except Exception as e:
            logger.error(f"Error exporting results: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта: {str(e)}")
    
    def export_to_markdown(self, file_path: str, results: List[Dict[str, Any]]):
        """
        Export results to Markdown format.
        
        Args:
            file_path [in]: Output file path
            results [in]: List of results to export
        """
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# Экспорт ChatList\n\n")
            f.write(f"**Дата экспорта:** {datetime.now().isoformat()}\n\n")
            
            if self.current_prompt_id:
                try:
                    prompt_data = db.get_prompt(self.current_prompt_id)
                    if prompt_data:
                        f.write(f"**Промт:** {prompt_data['prompt']}\n\n")
                        if prompt_data["tags"]:
                            f.write(f"**Теги:** {prompt_data['tags']}\n\n")
                except Exception:
                    pass
            
            f.write("---\n\n")
            
            for result in results:
                f.write(f"## {result['model_name']}\n\n")
                f.write(f"{result['response']}\n\n")
                f.write("---\n\n")
    
    def export_to_json(self, file_path: str, results: List[Dict[str, Any]]):
        """
        Export results to JSON format.
        
        Args:
            file_path [in]: Output file path
            results [in]: List of results to export
        """
        # Local variables
        export_data = {
            "export_date": datetime.now().isoformat(),
            "prompt_id": self.current_prompt_id,
            "results": results
        }
        
        if self.current_prompt_id:
            try:
                prompt_data = db.get_prompt(self.current_prompt_id)
                if prompt_data:
                    export_data["prompt"] = prompt_data["prompt"]
                    export_data["tags"] = prompt_data["tags"]
            except Exception:
                pass
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    def add_model(self):
        """
        Show dialog to add new model.
        """
        dialog = ModelDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            is_valid, error_msg = models.validate_model_config(
                data["name"], data["model_id"], data["api_url"], data["api_id"]
            )
            if not is_valid:
                QMessageBox.warning(self, "Ошибка валидации", error_msg)
                return
            
            new_model = models.create_model(
                data["name"], data["model_id"], data["api_url"], data["api_id"], data["is_active"]
            )
            if new_model:
                QMessageBox.information(self, "Успех", "Модель успешно добавлена")
            else:
                # Check if it's a duplicate name error
                existing_models = models.get_all_models()
                if any(m.name == data["name"] for m in existing_models):
                    QMessageBox.warning(self, "Ошибка", f"Модель с названием '{data['name']}' уже существует")
                else:
                    QMessageBox.critical(self, "Ошибка", "Не удалось добавить модель")
    
    def manage_models(self):
        """
        Show dialog to manage models.
        """
        dialog = ManageModelsDialog(self)
        dialog.exec_()
    
    def view_saved_prompts(self):
        """
        Show saved prompts dialog.
        """
        dialog = ViewPromptsDialog(self)
        dialog.prompt_selected.connect(self.load_prompt_by_id)
        dialog.exec_()
    
    def load_prompt_by_id(self, prompt_id: int):
        """
        Load prompt by ID into main window.
        
        Args:
            prompt_id [in]: Prompt ID to load
        """
        try:
            prompt_data = db.get_prompt(prompt_id)
            if prompt_data:
                # Clear current prompt
                self.prompt_text.clear()
                self.tags_input.clear()
                
                # Set new prompt
                prompt_text_value = prompt_data["prompt"]
                self.prompt_text.setPlainText(prompt_text_value)
                self.prompt_text.update()  # Force update
                
                if prompt_data["tags"]:
                    self.tags_input.setText(prompt_data["tags"])
                else:
                    self.tags_input.clear()
                self.tags_input.update()  # Force update
                
                self.current_prompt_id = prompt_id
                
                # Load saved results for this prompt
                self.load_saved_results_for_prompt(prompt_id)
                
                self.status_bar.showMessage(f"Промт загружен (ID: {prompt_id})")
                
                # Refresh saved prompts combo and select the loaded prompt
                self.load_saved_prompts()
                
                # Select the loaded prompt in combo box
                for i in range(self.saved_prompts_combo.count()):
                    if self.saved_prompts_combo.itemData(i) == prompt_id:
                        self.saved_prompts_combo.setCurrentIndex(i)
                        break
                
                # Ensure text is visible
                self.prompt_text.ensureCursorVisible()
            else:
                QMessageBox.warning(self, "Предупреждение", "Промт не найден в базе данных")
        except Exception as e:
            logger.error(f"Error loading prompt: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки промта: {str(e)}")
    
    def show_settings_dialog(self):
        """
        Show settings dialog.
        """
        QMessageBox.information(
            self, "Информация",
            "Диалог настроек будет реализован в будущей версии"
        )
    
    def show_improve_prompt_dialog(self):
        """
        Show prompt improvement dialog.
        """
        # Local variables
        prompt_text = self.prompt_text.toPlainText().strip()
        
        if not prompt_text:
            reply = QMessageBox.question(
                self, "Пустой промт",
                "Поле ввода промта пустое. Хотите использовать сохраненный промт?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                # Try to load from saved prompts
                current_data = self.saved_prompts_combo.currentData()
                if current_data:
                    try:
                        prompt_data = db.get_prompt(current_data)
                        if prompt_data:
                            prompt_text = prompt_data["prompt"]
                        else:
                            QMessageBox.information(
                                self, "Информация",
                                "Пожалуйста, введите промт или выберите сохраненный"
                            )
                            return
                    except Exception as e:
                        logger.error(f"Error loading prompt: {e}")
                        QMessageBox.critical(
                            self, "Ошибка",
                            f"Ошибка загрузки промта: {str(e)}"
                        )
                        return
                else:
                    QMessageBox.information(
                        self, "Информация",
                        "Пожалуйста, введите промт или выберите сохраненный"
                    )
                    return
            else:
                return
        
        # Check if there are active models
        active_models = models.get_active_models()
        if not active_models:
            QMessageBox.warning(
                self, "Предупреждение",
                "Нет активных моделей. Пожалуйста, добавьте модели в меню Модели."
            )
            return
        
        # Show improvement dialog
        dialog = PromptImprovementDialog(self, prompt_text, self.prompt_improver)
        
        # Set default model if configured
        if hasattr(self, 'default_improvement_model_id') and self.default_improvement_model_id:
            try:
                model_id = int(self.default_improvement_model_id)
                # Find model in combo and select it
                for i in range(dialog.model_combo.count()):
                    model = dialog.model_combo.itemData(i)
                    if model and model.id == model_id:
                        dialog.model_combo.setCurrentIndex(i)
                        break
            except (ValueError, TypeError):
                pass
        
        # Set default adaptation type if configured
        if hasattr(self, 'default_adaptation_type') and self.default_adaptation_type:
            for i in range(dialog.adaptation_combo.count()):
                if dialog.adaptation_combo.itemData(i) == self.default_adaptation_type:
                    dialog.adaptation_combo.setCurrentIndex(i)
                    break
        
        if dialog.exec_() == QDialog.Accepted:
            selected_prompt = dialog.get_selected_prompt()
            if selected_prompt:
                # Insert selected prompt into input field
                self.prompt_text.setPlainText(selected_prompt)
                self.status_bar.showMessage("Улучшенный промт подставлен в поле ввода")
    
    def show_about(self):
        """
        Show about dialog.
        """
        QMessageBox.about(
            self, "О программе ChatList",
            "ChatList - Инструмент сравнения AI моделей\n\n"
            "Сравнивайте ответы от нескольких AI моделей.\n"
            "Версия 1.0"
        )


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
