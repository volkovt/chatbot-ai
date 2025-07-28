import sys
from PyQt5.QtWidgets import QApplication, QPushButton, QMainWindow

from presentation.advanced_selection import AdvancedSelectionDialog
from utils.utilities import get_style_sheet

if __name__ == "__main__":
    app = QApplication(sys.argv)

    main_window = QMainWindow()
    main_window.setWindowTitle("Mock Advanced Selector")
    main_window.resize(800, 600)
    main_window.setStyleSheet(get_style_sheet())

    lists_data = [
        [
            {"name": "Maçã", "description": "Uma fruta vermelha e doce"},
            {"name": "Banana", "description": "Uma fruta amarela rica em potássio"},
            {"name": "Laranja", "description": "Suco cítrico refrescante"},
            {"name": "Uva", "description": "Pequena fruta roxa ou verde"},
            {"name": "Manga", "description": "Fruta tropical suculenta"},
            {"name": "Abacaxi", "description": "Fruta tropical com casca espinhosa"},
            {"name": "Morango", "description": "Fruta vermelha com sementes na superfície"},
            {"name": "Pera", "description": "Fruta doce e suculenta"},
            {"name": "Kiwi", "description": "Fruta pequena e peluda com polpa verde"},
            {"name": "Melancia", "description": "Fruta grande e refrescante"}
        ],
        [
            {"name": "Cachorro", "description": "Amigo leal do homem"},
            {"name": "Gato", "description": "Animal doméstico independente"},
            {"name": "Papagaio", "description": "Ave que imita sons"},
        ],
        [
            {"name": "Carro", "description": "Veículo motorizado de transporte"},
            {"name": "Bicicleta", "description": "Veículo de duas rodas"},
            {"name": "Avião", "description": "Veículo aéreo de transporte"},
        ],
        [
            {"name": "Navio", "description": "Grande embarcação para transporte marítimo"},
            {"name": "Trem", "description": "Veículo ferroviário de passageiros"},
            {"name": "Ônibus", "description": "Veículo de transporte público"},
        ]
    ]
    selection_types = [AdvancedSelectionDialog.SelectionMode.MULTI_SELECTION,
                        AdvancedSelectionDialog.SelectionMode.SINGLE_GLOBAL_SELECTION,
                        AdvancedSelectionDialog.SelectionMode.SINGLE_GLOBAL_SELECTION,
                        AdvancedSelectionDialog.SelectionMode.MULTI_SELECTION]
    titles = ["Frutas", "Animais", "Veículos", "Transporte"]
    dialog = AdvancedSelectionDialog(lists_data, selection_types, titles, parent=main_window)

    btn_ok = QPushButton("OK")
    btn_cancel = QPushButton("Cancelar")
    dialog.add_header_widget(btn_ok)
    dialog.add_footer_widget(btn_cancel)

    def on_selected(idx, items):
        texts = [item for item in items]
        print(f"Lista {idx} selecionada: {texts}")
    dialog.itemSelected.connect(on_selected)

    dialog.show()
    sys.exit(app.exec_())