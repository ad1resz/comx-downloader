from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    message = pyqtSignal(str)
    progress = pyqtSignal(int)
    result = pyqtSignal(object)


class AuthorizationWorker(QRunnable):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            self.signals.message.emit('Открываем браузер для авторизации...')
            success = self.client.authorize_with_selenium(status_callback=self.signals.message.emit)
            self.signals.result.emit(success)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class SearchWorker(QRunnable):
    def __init__(self, client, query):
        super().__init__()
        self.client = client
        self.query = query
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            self.signals.message.emit(f"Ищем: {self.query}")
            results = self.client.search(self.query)
            self.signals.result.emit(results)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class ChapterWorker(QRunnable):
    def __init__(self, client, manga_url):
        super().__init__()
        self.client = client
        self.manga_url = manga_url
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            self.signals.message.emit('Загружаем список глав...')
            chapters, manga_title = self.client.get_manga_info(self.manga_url)
            self.signals.result.emit({'chapters': chapters, 'title': manga_title})
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class DownloadWorker(QRunnable):
    def __init__(self, client, manga_url, output_dir, start_chapter, end_chapter, selected_chapters=None, download_format='jpg'):
        super().__init__()
        self.client = client
        self.manga_url = manga_url
        self.output_dir = output_dir
        self.start_chapter = start_chapter
        self.end_chapter = end_chapter
        self.selected_chapters = selected_chapters
        self.download_format = download_format
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            summary = self.client.download_manga(
                self.manga_url,
                output_dir=self.output_dir,
                start_chapter=self.start_chapter,
                end_chapter=self.end_chapter,
                selected_chapters=self.selected_chapters,
                status_callback=self.signals.message.emit,
                progress_callback=self._emit_progress,
                output_format=self.download_format
            )
            self.signals.result.emit(summary)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

    def _emit_progress(self, index, total, chapter):
        percent = int((index / max(total, 1)) * 100)
        self.signals.progress.emit(percent)
