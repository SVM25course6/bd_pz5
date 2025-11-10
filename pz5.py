# file: off_gui.py
import sys
import requests

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QMessageBox,
)

BASE = "https://world.openfoodfacts.org"

HEADERS = {
    "User-Agent": "Darcons-Trade-CalorieFetcher/1.0 (+https://darcons-trade.example)"
}


def get_product_by_barcode(barcode: str, fields=None, lang="ru", country="ru") -> dict:
    """
    Получение конкретного продукта по штрихкоду (API v2).
    """
    if fields is None:
        fields = "code,product_name,nutriments,brands,quantity,serving_size,language,lang,lc"

    url = f"{BASE}/api/v2/product/{barcode}"
    params = {"fields": fields, "lc": lang, "cc": country}

    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def search_products(query: str, page_size=5, fields=None, lang="ru", country="ru") -> dict:
    """
    Поиск продуктов по тексту (Search API v2).
    """
    if fields is None:
        fields = "code,product_name,brands,nutriments,quantity,serving_size,ecoscore_grade"

    url = f"{BASE}/api/v2/search"
    params = {
        "search_terms": query,
        "fields": fields,
        "page_size": page_size,
        "lc": lang,
        "cc": country,
    }

    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def extract_kcal(nutriments: dict) -> dict:
    """
    Извлекает калорийность и БЖУ.
    Возвращает значения на 100 г и на порцию (если доступно).
    """
    get = nutriments.get
    data = {
        "kcal_100g": get("energy-kcal_100g") or get("energy-kcal_value"),
        "protein_100g": get("proteins_100g"),
        "fat_100g": get("fat_100g"),
        "carbs_100g": get("carbohydrates_100g"),
        "kcal_serving": get("energy-kcal_serving"),
        "protein_serving": get("proteins_serving"),
        "fat_serving": get("fat_serving"),
        "carbs_serving": get("carbohydrates_serving"),
    }
    return {k: v for k, v in data.items() if v is not None}


def format_product_details(product: dict) -> str:
    """
    Формирует текст с информацией о продукте для отображения в интерфейсе.
    """
    name = product.get("product_name") or "—"
    brand = product.get("brands") or "—"
    code = product.get("code") or "—"
    quantity = product.get("quantity") or "—"
    serving = product.get("serving_size") or "—"

    nutr = extract_kcal(product.get("nutriments", {}))

    lines = [
        f"Название: {name}",
        f"Бренд: {brand}",
        f"Штрихкод: {code}",
        f"Упаковка: {quantity}",
        f"Порция: {serving}",
        "",
        "Питательные вещества:"
    ]

    if not nutr:
        lines.append("  данные о БЖУ не найдены")
    else:
        if "kcal_100g" in nutr:
            lines.append(f"  Калории на 100 г: {nutr['kcal_100g']}")
        if "protein_100g" in nutr:
            lines.append(f"  Белок на 100 г: {nutr['protein_100g']}")
        if "fat_100g" in nutr:
            lines.append(f"  Жиры на 100 г: {nutr['fat_100g']}")
        if "carbs_100g" in nutr:
            lines.append(f"  Углеводы на 100 г: {nutr['carbs_100g']}")

        if any(k.endswith("_serving") for k in nutr.keys()):
            lines.append("")
            lines.append("На порцию:")
            if "kcal_serving" in nutr:
                lines.append(f"  Калории на порцию: {nutr['kcal_serving']}")
            if "protein_serving" in nutr:
                lines.append(f"  Белок на порцию: {nutr['protein_serving']}")
            if "fat_serving" in nutr:
                lines.append(f"  Жиры на порцию: {nutr['fat_serving']}")
            if "carbs_serving" in nutr:
                lines.append(f"  Углеводы на порцию: {nutr['carbs_serving']}")

    return "\n".join(lines)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Поиск калорийности продуктов")
        self.resize(800, 600)

        # Простые стили
        self.setStyleSheet("""
            QWidget {
                font-family: Arial;
                font-size: 12px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTableWidget {
                border: 1px solid #ccc;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                font-weight: bold;
            }
            QTextEdit {
                border: 1px solid #ccc;
                background-color: #f9f9f9;
            }
        """)

        self.current_products = []

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        self.setLayout(main_layout)

        # --- Панель поиска ---
        search_layout = QHBoxLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["По штрихкоду", "По названию"])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)

        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("Введите штрихкод или название продукта")

        self.search_button = QPushButton("Найти")
        self.search_button.clicked.connect(self.on_search_clicked)

        search_layout.addWidget(QLabel("Режим:"))
        search_layout.addWidget(self.mode_combo)
        search_layout.addWidget(self.query_edit)
        search_layout.addWidget(self.search_button)

        main_layout.addLayout(search_layout)

        # --- Таблица результатов ---
        main_layout.addWidget(QLabel("Результаты поиска:"))
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Штрихкод", "Название", "Бренд", "Ккал/100г"])
        self.table.cellDoubleClicked.connect(self.on_table_double_clicked)
        self.table.hide()

        main_layout.addWidget(self.table)

        # --- Детальная информация ---
        main_layout.addWidget(QLabel("Информация о продукте:"))
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        main_layout.addWidget(self.details_text)

        self.on_mode_changed(0)

    def on_mode_changed(self, index: int):
        mode = self.mode_combo.currentText()
        self.details_text.clear()
        self.table.clearContents()
        self.table.setRowCount(0)

        if mode == "По штрихкоду":
            self.table.hide()
            self.query_edit.setPlaceholderText("Введите штрихкод (например 5449000000996)")
        else:
            self.table.show()
            self.query_edit.setPlaceholderText("Введите название (например 'творог 5%')")

    def on_search_clicked(self):
        query = self.query_edit.text().strip()
        if not query:
            QMessageBox.warning(self, "Ошибка", "Введите запрос.")
            return

        mode = self.mode_combo.currentText()

        try:
            if mode == "По штрихкоду":
                self.search_by_barcode(query)
            else:
                self.search_by_name(query)
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Ошибка сети", f"Не удалось выполнить запрос:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка:\n{e}")

    def search_by_barcode(self, barcode: str):
        self.details_text.clear()
        self.table.clearContents()
        self.table.setRowCount(0)

        data = get_product_by_barcode(barcode)
        product = data.get("product")

        if not product:
            QMessageBox.information(self, "Результат", "Продукт не найден.")
            return

        details = format_product_details(product)
        self.details_text.setPlainText(details)

    def search_by_name(self, name: str):
        self.details_text.clear()
        self.table.clearContents()
        self.table.setRowCount(0)
        self.current_products = []

        data = search_products(name, page_size=10)
        products = data.get("products", [])

        if not products:
            QMessageBox.information(self, "Результат", "Ничего не найдено.")
            return

        self.current_products = products
        self.table.setRowCount(len(products))

        for row, p in enumerate(products):
            code = p.get("code") or ""
            name = p.get("product_name") or ""
            brand = p.get("brands") or ""
            nutr = extract_kcal(p.get("nutriments", {}))
            kcal_100g = nutr.get("kcal_100g", "")

            self.table.setItem(row, 0, QTableWidgetItem(code))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem(brand))
            self.table.setItem(row, 3, QTableWidgetItem(str(kcal_100g)))

        self.table.resizeColumnsToContents()

    def on_table_double_clicked(self, row: int, column: int):
        if 0 <= row < len(self.current_products):
            product = self.current_products[row]
            details = format_product_details(product)
            self.details_text.setPlainText(details)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()