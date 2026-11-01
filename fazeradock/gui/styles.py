"""
FazeraDock GUI Styles
=====================

Defines the application-wide QSS stylesheet and color constants
for the FazeraDock molecular docking interface.

Uses a modern dark-blue / teal scientific color scheme.
"""

# ---------------------------------------------------------------------------
# Color constants
# ---------------------------------------------------------------------------
PRIMARY: str = "#1565C0"
PRIMARY_DARK: str = "#0D47A1"
PRIMARY_LIGHT: str = "#1E88E5"
ACCENT: str = "#00BCD4"
ACCENT_DARK: str = "#00838F"
SUCCESS: str = "#4CAF50"
WARNING: str = "#FF9800"
ERROR: str = "#F44336"
BG: str = "#FAFAFA"
BG_DARK: str = "#263238"
BG_CARD: str = "#FFFFFF"
BORDER: str = "#B0BEC5"
TEXT: str = "#212121"
TEXT_SECONDARY: str = "#546E7A"
TEXT_LIGHT: str = "#FFFFFF"

# ---------------------------------------------------------------------------
# Main QSS stylesheet
# ---------------------------------------------------------------------------
MAIN_STYLESHEET: str = f"""
/* ===== Global ===== */
QWidget {{
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: {TEXT};
    background-color: {BG};
}}

/* ===== Main Window ===== */
QMainWindow {{
    background-color: {BG};
}}

/* ===== Menu Bar ===== */
QMenuBar {{
    background-color: {PRIMARY_DARK};
    color: {TEXT_LIGHT};
    padding: 2px 0px;
    font-size: 13px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 14px;
    border-radius: 3px;
}}
QMenuBar::item:selected {{
    background-color: {PRIMARY_LIGHT};
}}
QMenu {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    padding: 4px 0px;
}}
QMenu::item {{
    padding: 7px 32px 7px 20px;
}}
QMenu::item:selected {{
    background-color: {PRIMARY};
    color: {TEXT_LIGHT};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 10px;
}}

/* ===== Tab Widget ===== */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-top: 2px solid {PRIMARY};
    background: {BG_CARD};
    border-radius: 0px 0px 4px 4px;
}}
QTabBar::tab {{
    background: #ECEFF1;
    color: {TEXT_SECONDARY};
    padding: 10px 24px;
    margin-right: 2px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-radius: 4px 4px 0px 0px;
    font-weight: 500;
    min-width: 100px;
}}
QTabBar::tab:selected {{
    background: {BG_CARD};
    color: {PRIMARY};
    font-weight: 600;
    border-bottom: 2px solid {BG_CARD};
    margin-bottom: -2px;
}}
QTabBar::tab:hover:!selected {{
    background: #CFD8DC;
    color: {TEXT};
}}

/* ===== Push Buttons ===== */
QPushButton {{
    background-color: {PRIMARY};
    color: {TEXT_LIGHT};
    border: none;
    padding: 8px 20px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 13px;
    min-height: 18px;
}}
QPushButton:hover {{
    background-color: {PRIMARY_LIGHT};
}}
QPushButton:pressed {{
    background-color: {PRIMARY_DARK};
}}
QPushButton:disabled {{
    background-color: #B0BEC5;
    color: #78909C;
}}
QPushButton[cssClass="accent"] {{
    background-color: {ACCENT};
}}
QPushButton[cssClass="accent"]:hover {{
    background-color: #26C6DA;
}}
QPushButton[cssClass="success"] {{
    background-color: {SUCCESS};
}}
QPushButton[cssClass="success"]:hover {{
    background-color: #66BB6A;
}}
QPushButton[cssClass="danger"] {{
    background-color: {ERROR};
}}
QPushButton[cssClass="danger"]:hover {{
    background-color: #EF5350;
}}
QPushButton[cssClass="warning"] {{
    background-color: {WARNING};
}}
QPushButton[cssClass="warning"]:hover {{
    background-color: #FFA726;
}}
QPushButton[cssClass="flat"] {{
    background-color: transparent;
    color: {PRIMARY};
    border: 1px solid {PRIMARY};
}}
QPushButton[cssClass="flat"]:hover {{
    background-color: #E3F2FD;
}}

/* ===== Line Edit ===== */
QLineEdit {{
    padding: 7px 10px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {BG_CARD};
    font-size: 13px;
    selection-background-color: {PRIMARY};
}}
QLineEdit:focus {{
    border: 2px solid {PRIMARY};
    padding: 6px 9px;
}}
QLineEdit:read-only {{
    background-color: #ECEFF1;
}}

/* ===== Spin Boxes ===== */
QSpinBox, QDoubleSpinBox {{
    padding: 6px 8px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {BG_CARD};
    min-width: 80px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {PRIMARY};
    padding: 5px 7px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 20px;
    border: none;
    background: transparent;
}}

/* ===== Combo Box ===== */
QComboBox {{
    padding: 7px 10px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {BG_CARD};
    min-width: 120px;
}}
QComboBox:focus {{
    border: 2px solid {PRIMARY};
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {PRIMARY};
    selection-color: {TEXT_LIGHT};
    padding: 2px;
}}

/* ===== Check Box & Radio Button ===== */
QCheckBox, QRadioButton {{
    spacing: 8px;
    font-size: 13px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 18px;
    height: 18px;
}}
QCheckBox::indicator:unchecked {{
    border: 2px solid {BORDER};
    border-radius: 3px;
    background: {BG_CARD};
}}
QCheckBox::indicator:checked {{
    border: 2px solid {PRIMARY};
    border-radius: 3px;
    background: {PRIMARY};
}}
QRadioButton::indicator:unchecked {{
    border: 2px solid {BORDER};
    border-radius: 10px;
    background: {BG_CARD};
}}
QRadioButton::indicator:checked {{
    border: 2px solid {PRIMARY};
    border-radius: 10px;
    background: {PRIMARY};
}}

/* ===== Group Box ===== */
QGroupBox {{
    font-weight: 600;
    font-size: 13px;
    color: {PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 12px;
    color: {PRIMARY};
}}

/* ===== Text Edit / Plain Text Edit ===== */
QTextEdit, QPlainTextEdit {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {BG_CARD};
    padding: 6px;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {PRIMARY};
}}

/* ===== Table Widget ===== */
QTableWidget, QTableView {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {BG_CARD};
    gridline-color: #E0E0E0;
    selection-background-color: #BBDEFB;
    selection-color: {TEXT};
    alternate-background-color: #F5F5F5;
}}
QHeaderView::section {{
    background-color: {PRIMARY};
    color: {TEXT_LIGHT};
    padding: 8px 6px;
    border: none;
    font-weight: 600;
    font-size: 12px;
}}
QHeaderView::section:hover {{
    background-color: {PRIMARY_LIGHT};
}}

/* ===== Progress Bar ===== */
QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    text-align: center;
    background-color: #E0E0E0;
    color: {TEXT};
    font-weight: 600;
    min-height: 22px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {PRIMARY}, stop:1 {ACCENT});
    border-radius: 5px;
}}

/* ===== Status Bar ===== */
QStatusBar {{
    background-color: {BG_DARK};
    color: {TEXT_LIGHT};
    font-size: 12px;
    padding: 2px 8px;
}}
QStatusBar::item {{
    border: none;
}}
QStatusBar QLabel {{
    color: {TEXT_LIGHT};
    padding: 0px 8px;
    background: transparent;
}}

/* ===== Scroll Bar ===== */
QScrollBar:vertical {{
    background: #ECEFF1;
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: #90A4AE;
    min-height: 30px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: #78909C;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: #ECEFF1;
    height: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal {{
    background: #90A4AE;
    min-width: 30px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #78909C;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ===== List Widget ===== */
QListWidget {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {BG_CARD};
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 6px 8px;
    border-radius: 3px;
}}
QListWidget::item:selected {{
    background-color: #BBDEFB;
    color: {TEXT};
}}
QListWidget::item:hover:!selected {{
    background-color: #E3F2FD;
}}

/* ===== Splitter ===== */
QSplitter::handle {{
    background-color: {BORDER};
}}
QSplitter::handle:horizontal {{
    width: 2px;
}}
QSplitter::handle:vertical {{
    height: 2px;
}}

/* ===== Tool Tip ===== */
QToolTip {{
    background-color: {BG_DARK};
    color: {TEXT_LIGHT};
    border: none;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 12px;
}}

/* ===== Dialog ===== */
QDialog {{
    background-color: {BG};
}}

/* ===== Label ===== */
QLabel {{
    background: transparent;
}}
QLabel[cssClass="heading"] {{
    font-size: 18px;
    font-weight: 700;
    color: {PRIMARY_DARK};
}}
QLabel[cssClass="subheading"] {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
}}
QLabel[cssClass="success"] {{
    color: {SUCCESS};
    font-weight: 600;
}}
QLabel[cssClass="error"] {{
    color: {ERROR};
    font-weight: 600;
}}
QLabel[cssClass="warning"] {{
    color: {WARNING};
    font-weight: 600;
}}
"""
