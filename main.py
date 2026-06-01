import re
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThreadPool, QPropertyAnimation, QTimer, QSettings
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QCheckBox,
    QPlainTextEdit,
    QProgressBar,
    QFileDialog,
    QVBoxLayout,
    QWidget,
)

from comx_client import ComXLifeClient
from workers import AuthorizationWorker, SearchWorker, ChapterWorker, DownloadWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('COM-X.LIFE Downloader')
        self.resize(980, 720)
        self.client = ComXLifeClient()
        self.threadpool = QThreadPool.globalInstance()
        self.current_manga_url = None
        self.current_manga_title = None
        self.current_chapters = []
        self.last_checked_index = None
        self._suppress_checkbox_handlers = False
        self.download_format = 'jpg'
        self.downloaded_chapters = set()  # Track downloaded chapters by index
        self.settings = QSettings('comx_downloader', 'comx_downloader')
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(3000)
        self.refresh_timer.timeout.connect(lambda: self._update_indicators())
        self._create_ui()
        self._load_settings()
        self._load_cookies()

    def _create_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        control_layout = QGridLayout()

        self.browser_combo = QComboBox()
        self.browser_combo.addItems(['Chrome', 'Firefox'])
        self.auth_button = QPushButton('Авторизоваться')
        self.auth_button.clicked.connect(self._start_authorization)
        self.auth_status = QLabel('Не авторизован')
        self.auth_status.setStyleSheet('color: #d14; font-weight: bold;')

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Введите URL или название манги')
        self.search_button = QPushButton('Найти')
        self.search_button.clicked.connect(self._start_search)

        self.folder_edit = QLineEdit('Manga')
        self.folder_edit.editingFinished.connect(self._save_folder_settings)
        self.output_button = QPushButton('Обзор...')
        self.output_button.clicked.connect(self._select_folder)
        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText('Диапазон, например 1-10 или 5')
        self.download_button = QPushButton('Скачать выбранное')
        self.download_button.clicked.connect(self._start_download)
        self.select_all_button = QPushButton('Выделить все')
        self.select_all_button.setCheckable(True)
        self.select_all_button.clicked.connect(self._toggle_select_all)
        self.format_combo = QComboBox()
        self.format_combo.addItems(['jpg', 'cbr'])
        self.format_combo.setCurrentText(self.download_format)
        self.format_combo.currentTextChanged.connect(self._on_format_changed)

        control_layout.addWidget(QLabel('Браузер:'), 0, 0)
        control_layout.addWidget(self.browser_combo, 0, 1)
        control_layout.addWidget(self.auth_button, 0, 2)
        control_layout.addWidget(self.auth_status, 0, 3)

        control_layout.addWidget(QLabel('Поиск:'), 1, 0)
        control_layout.addWidget(self.search_edit, 1, 1, 1, 3)
        control_layout.addWidget(self.search_button, 1, 4)

        control_layout.addWidget(QLabel('Папка:'), 2, 0)
        control_layout.addWidget(self.folder_edit, 2, 1, 1, 3)
        control_layout.addWidget(self.output_button, 2, 4)

        control_layout.addWidget(QLabel('Диапазон:'), 3, 0)
        control_layout.addWidget(self.range_edit, 3, 1, 1, 2)
        control_layout.addWidget(self.select_all_button, 3, 3)
        control_layout.addWidget(self.download_button, 3, 4)
        control_layout.addWidget(QLabel('Формат:'), 4, 0)
        control_layout.addWidget(self.format_combo, 4, 1)

        self.results_list = QListWidget()
        self.results_list.setAlternatingRowColors(True)
        self.results_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.results_list.itemSelectionChanged.connect(self._on_result_selected)

        self.chapters_list = QListWidget()
        self.chapters_list.setAlternatingRowColors(True)
        # we'll use embedded checkbox widgets; disable native selection
        self.chapters_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(500)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        main_layout.addLayout(control_layout)
        content_layout = QHBoxLayout()

        search_layout = QVBoxLayout()
        search_layout.addWidget(QLabel('Результаты поиска:'))
        search_layout.addWidget(self.results_list)

        chapters_layout = QVBoxLayout()
        chapters_layout.addWidget(QLabel('Главы:'))
        chapters_layout.addWidget(self.chapters_list)

        content_layout.addLayout(search_layout, 1)
        content_layout.addLayout(chapters_layout, 2)
        main_layout.addLayout(content_layout)
        main_layout.addWidget(QLabel('Журнал операций:'))
        main_layout.addWidget(self.log_output)
        main_layout.addWidget(self.progress_bar)

        self.statusBar().showMessage('Готово')

    def _load_cookies(self):
        if self.client.load_cookies():
            self.auth_status.setText('Авторизован')
            self.auth_status.setStyleSheet('color: #2d862d; font-weight: bold;')
            self._log('Cookies загружены из comx_cookies.json')
        else:
            self._log('Cookies не найдены. Нажмите «Авторизоваться».')

    def _load_settings(self):
        output_folder = self.settings.value('output_folder', '')
        if output_folder:
            self.folder_edit.setText(output_folder)
        self.download_format = self.settings.value('download_format', 'jpg')
        self.format_combo.setCurrentText(self.download_format)

    def _save_settings(self):
        self.settings.setValue('output_folder', self.folder_edit.text().strip())
        self.settings.setValue('download_format', self.download_format)

    def _save_folder_settings(self):
        self._save_settings()
        self._update_indicators()

    def _select_folder(self):
        directory = QFileDialog.getExistingDirectory(self, 'Выберите папку для сохранения', str(Path.cwd()))
        if directory:
            self.folder_edit.setText(directory)
            self._save_settings()
            self._update_indicators()

    def _start_authorization(self):
        self.auth_button.setEnabled(False)
        self.client.browser_choice = self.browser_combo.currentText().lower()
        worker = AuthorizationWorker(self.client)
        worker.signals.message.connect(self._log)
        worker.signals.error.connect(self._show_error)
        worker.signals.result.connect(self._on_auth_result)
        worker.signals.finished.connect(lambda: self.auth_button.setEnabled(True))
        self.threadpool.start(worker)

    def _on_auth_result(self, success):
        if success:
            self.auth_status.setText('Авторизован')
            self.auth_status.setStyleSheet('color: #2d862d; font-weight: bold;')
            self._show_message('Авторизация выполнена', 'Авторизация завершена успешно.')
        else:
            self.auth_status.setText('Не авторизован')
            self.auth_status.setStyleSheet('color: #d14; font-weight: bold;')
            self._show_message('Ошибка авторизации', 'Авторизация не завершена.')

    def _start_search(self):
        query = self.search_edit.text().strip()
        if not query:
            self._show_error('Введите URL или название манги для поиска.')
            return

        if 'com-x.life' in query.lower() and ('http://' in query.lower() or 'https://' in query.lower()):
            self.results_list.clear()
            self.chapters_list.clear()
            self.current_chapters = []
            list_item = QListWidgetItem(query)
            list_item.setData(Qt.ItemDataRole.UserRole, query)
            self.results_list.addItem(list_item)
            self.results_list.setCurrentRow(0)
            self._on_result_selected()
            return

        self.search_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.results_list.clear()
        self.chapters_list.clear()
        self.current_chapters = []
        self.current_manga_url = None
        worker = SearchWorker(self.client, query)
        worker.signals.message.connect(self._log)
        worker.signals.error.connect(self._show_error)
        worker.signals.result.connect(self._populate_results)
        worker.signals.finished.connect(lambda: self._set_controls_enabled(True))
        self.threadpool.start(worker)
        self._set_controls_enabled(False)

    def _populate_results(self, results):
        self.results_list.clear()
        self.chapters_list.clear()
        self.current_chapters = []
        self.current_manga_url = None

        if not results:
            self._log('Ничего не найдено.')
            self.statusBar().showMessage('Поиск завершён: ничего не найдено.')
            return

        for item in results:
            list_item = QListWidgetItem(item['title'])
            list_item.setData(Qt.ItemDataRole.UserRole, item['url'])
            self.results_list.addItem(list_item)

        self._log(f'Найдено {len(results)} результатов. Выберите мангу, чтобы загрузить список глав.')
        self.statusBar().showMessage(f'Найдено {len(results)} результатов.')
        if self.results_list.count() == 1:
            self.results_list.setCurrentRow(0)
            self._on_result_selected()

    def _on_result_selected(self):
        current_item = self.results_list.currentItem()
        if not current_item:
            return

        manga_url = current_item.data(Qt.ItemDataRole.UserRole)
        if manga_url == self.current_manga_url:
            return

        self.current_manga_url = manga_url
        self.chapters_list.clear()
        self.current_chapters = []
        self._log(f'Загружаем главы: {current_item.text()}')
        self.statusBar().showMessage('Загружаем список глав...')

        worker = ChapterWorker(self.client, manga_url)
        worker.signals.message.connect(self._log)
        worker.signals.error.connect(self._show_error)
        worker.signals.result.connect(self._populate_chapters)
        worker.signals.finished.connect(lambda: self._set_controls_enabled(True))
        self.threadpool.start(worker)
        self._set_controls_enabled(False)

    def _populate_chapters(self, data):
        self.chapters_list.clear()
        self.current_chapters = data.get('chapters', [])
        self.current_manga_title = data.get('title')
        self.last_checked_index = None
        self.downloaded_chapters.clear()  # Reset downloaded tracking for new manga

        if not self.current_chapters:
            self._log('Список глав пуст, либо не удалось получить информацию.')
            self.statusBar().showMessage('Список глав пуст.')
            self.refresh_timer.stop()
            return

        # create item widgets with checkbox + label + colored indicator (red=not downloaded, green=downloaded)
        for idx, chapter in enumerate(self.current_chapters):
            pos = chapter.get('posi', 0)
            title = chapter.get('title', '').strip()
            item_text = f"{int(pos):03d} — {title}" if title else f"{int(pos):03d}"
            list_item = QListWidgetItem()
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(6, 2, 6, 2)
            checkbox = QCheckBox()
            checkbox.setChecked(False)
            checkbox.setStyleSheet('QCheckBox::indicator { width:18px; height:18px; }')
            label = QLabel(item_text)
            label.setObjectName('chapter_label')
            h.addWidget(checkbox)
            h.addWidget(label)
            h.addStretch()
            indicator = QLabel()
            indicator.setObjectName('chapter_indicator')
            indicator.setFixedSize(14, 14)
            indicator.setStyleSheet('border-radius:7px; background: #ff6b6b;')
            h.addWidget(indicator)
            list_item.setSizeHint(container.sizeHint())
            list_item.setData(Qt.ItemDataRole.UserRole, chapter)
            self.chapters_list.addItem(list_item)
            self.chapters_list.setItemWidget(list_item, container)
            # try to detect already downloaded chapters and mark indicator green
            try:
                base = Path(self.folder_edit.text().strip() or 'Manga') / self.current_manga_title
                safe = ComXLifeClient.sanitize_filename(item_text)
                exists = ComXLifeClient.chapter_exists(base, safe)
                if exists:
                    checkbox.setChecked(True)
                    indicator.setStyleSheet('border-radius:7px; background: #77dd77;')
                    self.downloaded_chapters.add(idx)
                else:
                    indicator.setStyleSheet('QLabel { background-color: #ff6b6b; border-radius: 7px; }')
            except Exception:
                indicator.setStyleSheet('QLabel { background-color: #ff6b6b; border-radius: 7px; }')
            # connect checkbox handler with index
            checkbox.stateChanged.connect(lambda state, ix=idx: self._on_checkbox_toggled(ix, state == Qt.CheckState.Checked))

        self._log(f'Загружено {len(self.current_chapters)} глав.')
        self.statusBar().showMessage(f'Найдено {len(self.current_chapters)} глав.')
        # start periodic refresh of indicators
        self.refresh_timer.start()

    def _start_download(self):
        current_item = self.results_list.currentItem()
        if not current_item and self.results_list.count() == 1:
            current_item = self.results_list.item(0)

        if not current_item:
            query = self.search_edit.text().strip()
            if 'com-x.life' in query.lower() and ('http://' in query.lower() or 'https://' in query.lower()):
                list_item = QListWidgetItem(query)
                list_item.setData(Qt.ItemDataRole.UserRole, query)
                self.results_list.addItem(list_item)
                current_item = list_item
            else:
                self._show_error('Выберите результат поиска перед скачиванием.')
                return

        manga_url = current_item.data(Qt.ItemDataRole.UserRole)
        output_dir = self.folder_edit.text().strip() or 'Manga'
        start_chapter, end_chapter = ComXLifeClient.parse_range(self.range_edit.text())

        # collect selected chapters from checkbox widgets
        selected_chapters = []
        for i in range(self.chapters_list.count()):
            li = self.chapters_list.item(i)
            widget = self.chapters_list.itemWidget(li)
            if widget:
                cb = widget.findChild(QCheckBox)
                if cb and cb.isChecked():
                    selected_chapters.append(li.data(Qt.ItemDataRole.UserRole))
        if not selected_chapters:
            selected_chapters = None

        if not self.client.load_cookies():
            self._show_error('Не найден comx_cookies.json. Сначала выполните авторизацию.')
            return

        self.progress_bar.setValue(0)
        self.download_button.setEnabled(False)
        self.search_button.setEnabled(False)
        self.auth_button.setEnabled(False)

        worker = DownloadWorker(self.client, manga_url, output_dir, start_chapter, end_chapter, selected_chapters=selected_chapters, download_format=self.download_format)
        worker.signals.message.connect(self._on_worker_message)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.error.connect(self._show_error)
        worker.signals.result.connect(self._on_download_finished)
        worker.signals.finished.connect(lambda: self._set_controls_enabled(True))
        self.threadpool.start(worker)

    def _on_progress(self, value):
        self.progress_bar.setValue(value)

    def _on_download_finished(self, summary):
        self._log(f"Скачивание завершено: {summary['success']}/{summary['total']} глав.")
        self._show_message('Готово', f"Сохранено в: {summary['path']}")
        self.progress_bar.setValue(100)
        self.statusBar().showMessage('Загрузка завершена.')

    def _set_controls_enabled(self, enabled):
        self.search_button.setEnabled(enabled)
        self.download_button.setEnabled(enabled)
        self.auth_button.setEnabled(enabled)
        self.output_button.setEnabled(enabled)
        self.results_list.setEnabled(enabled)
        self.chapters_list.setEnabled(enabled)

    def _toggle_select_all(self):
        toggle_on = self.select_all_button.isChecked()
        self._suppress_checkbox_handlers = True
        for i in range(self.chapters_list.count()):
            li = self.chapters_list.item(i)
            widget = self.chapters_list.itemWidget(li)
            if widget:
                cb = widget.findChild(QCheckBox)
                if cb:
                    cb.setChecked(toggle_on)
        self._suppress_checkbox_handlers = False
        self.select_all_button.setText('Снять выделение' if toggle_on else 'Выделить все')

    def _on_format_changed(self, text):
        self.download_format = text
        self._save_settings()
        self._update_indicators()

    def _update_indicators(self):
        # Refresh indicators according to the chosen folder and actual chapter presence
        for i in range(self.chapters_list.count()):
            li = self.chapters_list.item(i)
            widget = self.chapters_list.itemWidget(li)
            if widget:
                lbl = widget.findChild(QLabel, 'chapter_label')
                ind = widget.findChild(QLabel, 'chapter_indicator')
                if lbl and ind and self.current_manga_title:
                    item_text = lbl.text()
                    safe = ComXLifeClient.sanitize_filename(item_text)
                    # Don't override green if already marked as downloaded
                    if i in self.downloaded_chapters:
                        ind.setStyleSheet('QLabel { background-color: #77dd77; border-radius: 7px; }')
                        continue
                    base = Path(self.folder_edit.text().strip() or 'Manga') / self.current_manga_title
                    exists = ComXLifeClient.chapter_exists(base, safe)
                    if exists:
                        ind.setStyleSheet('QLabel { background-color: #77dd77; border-radius: 7px; }')
                        self.downloaded_chapters.add(i)
                    else:
                        ind.setStyleSheet('QLabel { background-color: #ff6b6b; border-radius: 7px; }')

    def _on_checkbox_toggled(self, index, checked):
        if self._suppress_checkbox_handlers:
            return

        modifiers = QApplication.keyboardModifiers()
        shift = modifiers & Qt.KeyboardModifier.ShiftModifier

        if shift and self.last_checked_index is not None and self.last_checked_index != index:
            # select range between last_checked_index and index
            start = min(self.last_checked_index, index)
            end = max(self.last_checked_index, index)
            self._suppress_checkbox_handlers = True
            for i in range(start, end + 1):
                li = self.chapters_list.item(i)
                widget = self.chapters_list.itemWidget(li)
                if widget:
                    cb = widget.findChild(QCheckBox)
                    if cb:
                        cb.setChecked(checked)
            self._suppress_checkbox_handlers = False
        # update last checked if user clicked (or programmatic single click)
        self.last_checked_index = index


    def _on_worker_message(self, text):
        self._log(text)
        if text.startswith('Скачано:'):
            try:
                downloaded = text.split(':', 1)[1].strip()
                print(f"[DEBUG] Message after split: '{downloaded}'")
                match = re.search(r'Ch\.\s*0*([0-9]+)\s*-\s*(.*)', downloaded)
                downloaded_index = int(match.group(1)) if match else None
                print(f"[DEBUG] Extracted index: {downloaded_index}")
                for i in range(self.chapters_list.count()):
                    li = self.chapters_list.item(i)
                    widget = self.chapters_list.itemWidget(li)
                    if not widget:
                        continue
                    chapter = li.data(Qt.ItemDataRole.UserRole)
                    lbl = widget.findChild(QLabel, 'chapter_label')
                    indicator = widget.findChild(QLabel, 'chapter_indicator')
                    if chapter is None or lbl is None or indicator is None:
                        continue
                    chapter_pos = int(chapter.get('posi', 0))
                    print(f"[DEBUG] Checking chapter {i}: pos={chapter_pos}, label='{lbl.text()}'")
                    if downloaded_index is not None and chapter_pos == downloaded_index:
                        matched = True
                        print(f"[DEBUG] MATCHED by index! {chapter_pos} == {downloaded_index}")
                    else:
                        matched = downloaded in lbl.text() or downloaded in chapter.get('title', '')
                        if matched:
                            print(f"[DEBUG] MATCHED by text!")
                    if matched:
                        cb = widget.findChild(QCheckBox)
                        if cb:
                            cb.setChecked(True)
                        indicator.setStyleSheet('QLabel { background-color: #77dd77; border-radius: 7px; }')
                        self.downloaded_chapters.add(i)  # Mark as downloaded
                        indicator.update()
                        print(f"[DEBUG] Set indicator {i} to green and added to downloaded_chapters")
            except Exception as e:
                print(f"[DEBUG] Error in _on_worker_message: {e}")
                import traceback
                traceback.print_exc()

    def _log(self, text):
        self.log_output.appendPlainText(text)

    def _show_message(self, title, text):
        QMessageBox.information(self, title, text)

    def _show_error(self, message):
        self.log_output.appendPlainText(f'Ошибка: {message}')
        QMessageBox.critical(self, 'Ошибка', message)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(
        'QWidget { font-family: Arial, sans-serif; font-size: 12px; }'
        'QPushButton { min-height: 28px; padding: 4px 10px; }'
        'QLineEdit, QPlainTextEdit, QListWidget { border: 1px solid #c5c5c5; }'
        'QPlainTextEdit { background: #121212; color: #e8e8e8; }'
        'QProgressBar { min-height: 18px; }'
    )
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
