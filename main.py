import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow


class AboriStoresWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Abori Stores POS")
        self.resize(1000, 650)

        welcome_label = QLabel("Abori Stores POS")
        welcome_label.setStyleSheet(
            "font-size: 32px; font-weight: bold;"
        )

        self.setCentralWidget(welcome_label)


def main():
    app = QApplication(sys.argv)

    window = AboriStoresWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
    