from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QComboBox


class NoScrollComboBox(QComboBox):
    """A combo box whose selection cannot be changed with the mouse wheel."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()
