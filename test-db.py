#!/usr/bin/env python3
"""
Test program for SQLite database viewer with CRUD operations.
Allows browsing tables, viewing data with pagination, and performing CRUD operations.
"""

import sqlite3
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QListWidget, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox, QDialog, QFormLayout,
    QDialogButtonBox, QSplitter, QSpinBox, QHeaderView
)
from PyQt5.QtCore import Qt
from typing import Optional, List, Dict, Any


class RecordDialog(QDialog):
    """
    Dialog window for creating/updating database records.
    """
    
    def __init__(self, parent: QWidget, title: str, schema: List[Dict[str, Any]], current_values: Optional[Dict[str, Any]]):
        """
        Initialize record dialog.
        
        @param [in] parent Parent window
        @param [in] title Dialog title
        @param [in] schema Table schema information
        @param [in] current_values Current values for update (None for create)
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.schema = schema
        self.result = None
        self.fields = {}
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        for col in schema:
            label_text = col["name"]
            if col["pk"]:
                label_text += " (PK)"
            if col["notnull"]:
                label_text += " *"
            
            value = ""
            if current_values and col["name"] in current_values:
                value = str(current_values[col["name"]]) if current_values[col["name"]] is not None else ""
            
            entry = QLineEdit()
            entry.setText(value)
            form_layout.addRow(label_text, entry)
            self.fields[col["name"]] = entry
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._ok_clicked)
        button_box.rejected.connect(self._cancel_clicked)
        layout.addWidget(button_box)
    
    def _ok_clicked(self):
        """
        Handle OK button click - validate and collect form data.
        """
        self.result = {}
        
        for col in self.schema:
            value = self.fields[col["name"]].text().strip()
            
            # Check required fields
            if col["notnull"] and not value and not col["pk"]:
                QMessageBox.warning(self, "Validation Error", f"Field '{col['name']}' is required.")
                return
            
            # Convert empty string to None for optional fields
            if not value:
                value = None
            
            self.result[col["name"]] = value
        
        self.accept()
    
    def _cancel_clicked(self):
        """
        Handle Cancel button click.
        """
        self.result = None
        self.reject()


class DatabaseViewer(QMainWindow):
    """
    Main application class for SQLite database viewer.
    """
    
    def __init__(self):
        """
        Initialize the database viewer application.
        """
        super().__init__()
        self.setWindowTitle("SQLite Database Viewer")
        self.setGeometry(100, 100, 1200, 800)
        
        self.db_path: Optional[str] = None
        self.db_connection: Optional[sqlite3.Connection] = None
        self.current_table: Optional[str] = None
        self.current_page: int = 1
        self.rows_per_page: int = 20
        self.total_rows: int = 0
        
        self._create_widgets()
    
    def _create_widgets(self):
        """
        Create and layout all GUI widgets.
        """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Top frame for file selection
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Database File:"))
        
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        top_layout.addWidget(self.file_path_edit)
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_file)
        top_layout.addWidget(browse_btn)
        
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._load_database)
        top_layout.addWidget(load_btn)
        
        main_layout.addLayout(top_layout)
        
        # Splitter for table list and data view
        splitter = QSplitter(Qt.Horizontal)
        
        # Left pane: Table list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Tables:"))
        
        self.table_list = QListWidget()
        self.table_list.itemSelectionChanged.connect(self._on_table_select)
        left_layout.addWidget(self.table_list)
        
        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self._open_table)
        self.open_button.setEnabled(False)
        left_layout.addWidget(self.open_button)
        
        splitter.addWidget(left_widget)
        
        # Right pane: Table data view
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Toolbar for CRUD operations
        toolbar_layout = QHBoxLayout()
        
        create_btn = QPushButton("Create")
        create_btn.clicked.connect(self._create_record)
        toolbar_layout.addWidget(create_btn)
        
        update_btn = QPushButton("Update")
        update_btn.clicked.connect(self._update_record)
        toolbar_layout.addWidget(update_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_record)
        toolbar_layout.addWidget(delete_btn)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_table)
        toolbar_layout.addWidget(refresh_btn)
        
        toolbar_layout.addStretch()
        right_layout.addLayout(toolbar_layout)
        
        # Table info label
        self.table_info_label = QLabel("No table selected")
        right_layout.addWidget(self.table_info_label)
        
        # Table widget for displaying data
        self.table_widget = QTableWidget()
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_widget.setSelectionMode(QTableWidget.ExtendedSelection)
        right_layout.addWidget(self.table_widget)
        
        # Pagination controls
        pagination_layout = QHBoxLayout()
        
        first_btn = QPushButton("<< First")
        first_btn.clicked.connect(self._first_page)
        pagination_layout.addWidget(first_btn)
        
        prev_btn = QPushButton("< Prev")
        prev_btn.clicked.connect(self._prev_page)
        pagination_layout.addWidget(prev_btn)
        
        self.page_label = QLabel("Page 1 of 1")
        pagination_layout.addWidget(self.page_label)
        
        next_btn = QPushButton("Next >")
        next_btn.clicked.connect(self._next_page)
        pagination_layout.addWidget(next_btn)
        
        last_btn = QPushButton("Last >>")
        last_btn.clicked.connect(self._last_page)
        pagination_layout.addWidget(last_btn)
        
        pagination_layout.addStretch()
        pagination_layout.addWidget(QLabel("Rows per page:"))
        
        self.rows_spinbox = QSpinBox()
        self.rows_spinbox.setMinimum(5)
        self.rows_spinbox.setMaximum(100)
        self.rows_spinbox.setValue(self.rows_per_page)
        self.rows_spinbox.valueChanged.connect(self._change_rows_per_page)
        pagination_layout.addWidget(self.rows_spinbox)
        
        right_layout.addLayout(pagination_layout)
        
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(splitter)
    
    def _browse_file(self):
        """
        Open file dialog to select SQLite database file.
        """
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select SQLite Database",
            "",
            "SQLite databases (*.db *.sqlite *.sqlite3);;All files (*.*)"
        )
        
        if filename:
            self.file_path_edit.setText(filename)
            self.db_path = filename
    
    def _load_database(self):
        """
        Load database and populate table list.
        """
        db_path = self.file_path_edit.text()
        
        if not db_path:
            QMessageBox.warning(self, "Warning", "Please select a database file first.")
            return
        
        try:
            # Close existing connection if any
            if self.db_connection:
                self.db_connection.close()
            
            self.db_connection = sqlite3.connect(db_path)
            self.db_path = db_path
            
            # Get list of tables
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Update list widget
            self.table_list.clear()
            self.table_list.addItems(tables)
            
            if tables:
                QMessageBox.information(self, "Success", f"Database loaded. Found {len(tables)} table(s).")
            else:
                QMessageBox.warning(self, "Warning", "Database loaded but no tables found.")
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Error", f"Failed to load database: {e}")
            self.db_connection = None
    
    def _on_table_select(self):
        """
        Handle table selection in list widget.
        """
        if self.table_list.currentItem():
            self.open_button.setEnabled(True)
        else:
            self.open_button.setEnabled(False)
    
    def _open_table(self):
        """
        Open selected table and display its data.
        """
        current_item = self.table_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a table first.")
            return
        
        if not self.db_connection:
            QMessageBox.critical(self, "Error", "No database connection. Please load a database first.")
            return
        
        table_name = current_item.text()
        self.current_table = table_name
        self.current_page = 1
        self._refresh_table()
    
    def _refresh_table(self):
        """
        Refresh current table view with pagination.
        """
        if not self.current_table or not self.db_connection:
            return
        
        try:
            cursor = self.db_connection.cursor()
            
            # Get total row count
            cursor.execute(f"SELECT COUNT(*) FROM {self.current_table}")
            self.total_rows = cursor.fetchone()[0]
            
            # Get column names
            cursor.execute(f"PRAGMA table_info({self.current_table})")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Calculate pagination
            total_pages = max(1, (self.total_rows + self.rows_per_page - 1) // self.rows_per_page)
            offset = (self.current_page - 1) * self.rows_per_page
            
            # Fetch data for current page
            query = f"SELECT * FROM {self.current_table} LIMIT {self.rows_per_page} OFFSET {offset}"
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Configure table widget
            self.table_widget.setRowCount(len(rows))
            self.table_widget.setColumnCount(len(columns))
            self.table_widget.setHorizontalHeaderLabels(columns)
            
            # Populate table
            for row_idx, row in enumerate(rows):
                for col_idx, value in enumerate(row):
                    item = QTableWidgetItem(str(value) if value is not None else "")
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make read-only
                    self.table_widget.setItem(row_idx, col_idx, item)
            
            # Resize columns to content
            self.table_widget.resizeColumnsToContents()
            
            # Update pagination label
            self.page_label.setText(f"Page {self.current_page} of {total_pages} (Total rows: {self.total_rows})")
            self.table_info_label.setText(f"Table: {self.current_table}")
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Error", f"Failed to load table data: {e}")
    
    def _first_page(self):
        """
        Navigate to first page.
        """
        self.current_page = 1
        self._refresh_table()
    
    def _prev_page(self):
        """
        Navigate to previous page.
        """
        if self.current_page > 1:
            self.current_page -= 1
            self._refresh_table()
    
    def _next_page(self):
        """
        Navigate to next page.
        """
        total_pages = max(1, (self.total_rows + self.rows_per_page - 1) // self.rows_per_page)
        if self.current_page < total_pages:
            self.current_page += 1
            self._refresh_table()
    
    def _last_page(self):
        """
        Navigate to last page.
        """
        total_pages = max(1, (self.total_rows + self.rows_per_page - 1) // self.rows_per_page)
        self.current_page = total_pages
        self._refresh_table()
    
    def _change_rows_per_page(self, value: int):
        """
        Change number of rows per page and refresh view.
        
        @param [in] value New rows per page value
        """
        self.rows_per_page = value
        self.current_page = 1
        self._refresh_table()
    
    def _get_table_schema(self) -> List[Dict[str, Any]]:
        """
        Get schema information for current table.
        
        @return [out] List of column information dictionaries
        """
        if not self.current_table or not self.db_connection:
            return []
        
        cursor = self.db_connection.cursor()
        cursor.execute(f"PRAGMA table_info({self.current_table})")
        
        columns = []
        for row in cursor.fetchall():
            columns.append({
                "cid": row[0],
                "name": row[1],
                "type": row[2],
                "notnull": row[3],
                "default_value": row[4],
                "pk": row[5]
            })
        
        return columns
    
    def _create_record(self):
        """
        Open dialog to create a new record.
        """
        if not self.current_table or not self.db_connection:
            QMessageBox.warning(self, "Warning", "Please open a table first.")
            return
        
        schema = self._get_table_schema()
        if not schema:
            return
        
        dialog = RecordDialog(self, "Create Record", schema, None)
        
        if dialog.exec_() == QDialog.Accepted and dialog.result:
            try:
                cursor = self.db_connection.cursor()
                
                # Build INSERT query
                columns = [col["name"] for col in schema if not col["pk"] or dialog.result.get(col["name"])]
                values = [dialog.result.get(col["name"]) for col in schema if col["name"] in columns]
                
                placeholders = ",".join(["?" for _ in values])
                column_names = ",".join(columns)
                
                query = f"INSERT INTO {self.current_table} ({column_names}) VALUES ({placeholders})"
                cursor.execute(query, values)
                self.db_connection.commit()
                
                QMessageBox.information(self, "Success", "Record created successfully.")
                self._refresh_table()
                
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Error", f"Failed to create record: {e}")
                self.db_connection.rollback()
    
    def _update_record(self):
        """
        Open dialog to update selected record.
        """
        if not self.current_table or not self.db_connection:
            QMessageBox.warning(self, "Warning", "Please open a table first.")
            return
        
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Warning", "Please select a record to update.")
            return
        
        # Get selected row index
        row_idx = selected_rows[0].row()
        
        schema = self._get_table_schema()
        if not schema:
            return
        
        # Create dictionary of current values
        current_values = {}
        for col_idx, col in enumerate(schema):
            item = self.table_widget.item(row_idx, col_idx)
            if item:
                current_values[col["name"]] = item.text()
            else:
                current_values[col["name"]] = None
        
        dialog = RecordDialog(self, "Update Record", schema, current_values)
        
        if dialog.exec_() == QDialog.Accepted and dialog.result:
            try:
                cursor = self.db_connection.cursor()
                
                # Build UPDATE query
                pk_columns = [col["name"] for col in schema if col["pk"]]
                if not pk_columns:
                    QMessageBox.critical(self, "Error", "Table has no primary key. Cannot update record.")
                    return
                
                set_clauses = []
                set_values = []
                for col in schema:
                    if col["name"] in dialog.result and col["name"] not in pk_columns:
                        set_clauses.append(f"{col['name']} = ?")
                        set_values.append(dialog.result[col["name"]])
                
                where_clauses = []
                where_values = []
                for pk_col in pk_columns:
                    where_clauses.append(f"{pk_col} = ?")
                    col_idx = next(i for i, c in enumerate(schema) if c["name"] == pk_col)
                    item = self.table_widget.item(row_idx, col_idx)
                    where_values.append(item.text() if item else None)
                
                query = f"UPDATE {self.current_table} SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)}"
                cursor.execute(query, set_values + where_values)
                self.db_connection.commit()
                
                QMessageBox.information(self, "Success", "Record updated successfully.")
                self._refresh_table()
                
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Error", f"Failed to update record: {e}")
                self.db_connection.rollback()
    
    def _delete_record(self):
        """
        Delete selected record(s).
        """
        if not self.current_table or not self.db_connection:
            QMessageBox.warning(self, "Warning", "Please open a table first.")
            return
        
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Warning", "Please select record(s) to delete.")
            return
        
        # Confirm deletion
        count = len(selected_rows)
        reply = QMessageBox.question(
            self,
            "Confirm",
            f"Delete {count} record(s)?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        schema = self._get_table_schema()
        pk_columns = [col["name"] for col in schema if col["pk"]]
        
        if not pk_columns:
            QMessageBox.critical(self, "Error", "Table has no primary key. Cannot delete record.")
            return
        
        try:
            cursor = self.db_connection.cursor()
            deleted_count = 0
            
            # Process rows in reverse order to maintain indices
            row_indices = sorted([row.row() for row in selected_rows], reverse=True)
            
            for row_idx in row_indices:
                # Build WHERE clause using primary key
                where_clauses = []
                where_values = []
                for pk_col in pk_columns:
                    col_idx = next(i for i, c in enumerate(schema) if c["name"] == pk_col)
                    item = self.table_widget.item(row_idx, col_idx)
                    if item:
                        where_clauses.append(f"{pk_col} = ?")
                        where_values.append(item.text())
                
                if where_clauses:
                    query = f"DELETE FROM {self.current_table} WHERE {' AND '.join(where_clauses)}"
                    cursor.execute(query, where_values)
                    deleted_count += 1
            
            self.db_connection.commit()
            QMessageBox.information(self, "Success", f"Deleted {deleted_count} record(s).")
            self._refresh_table()
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Error", f"Failed to delete record(s): {e}")
            self.db_connection.rollback()


def main():
    """
    Main entry point for the application.
    """
    app = QApplication(sys.argv)
    window = DatabaseViewer()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
