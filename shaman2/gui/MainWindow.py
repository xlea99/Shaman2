from PyQt6.QtCore import QUrl, QEventLoop
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QLineEdit, QTextEdit, QLabel
)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # Base setup
        self.setWindowTitle("Dynamic Tabbed Browser with XPath Finder")
        self.resize(1200, 800)
        mainContainer = QWidget()
        self.mainLayout = QHBoxLayout(mainContainer)
        self.setCentralWidget(mainContainer)



if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
