import sys
from PyQt5.QtCore import *
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QProgressBar,
)
from PyQt5.QtWebEngineWidgets import *
import re
from fontbakery.checkrunner import (
    get_module_profile,
    CheckRunner,
    INFO,
    START,
    ENDCHECK,
    distribute_generator,
)
from fontbakery.commands.check_profile import get_module
from fontbakery.reporters import FontbakeryReporter
from fontbakery.reporters.html import HTMLReporter

profiles = ["googlefonts", "adobefonts", "notofonts", "opentype"]


class ProgressReporter(FontbakeryReporter):
    def __init__(self, signal, is_async=False, runner=None):
        self.signal = signal
        super().__init__(is_async, runner)

    def receive(self, event):
        status, message, identity = event
        if status == START:
            self.count = len(message)
        elif status == ENDCHECK:
            self._tick += 1
        self.signal.emit(100 * self._tick / float(self.count))


class DragDropArea(QLabel):
    def __init__(self, parent):
        super(DragDropArea, self).__init__()
        self.parent = parent
        self.setText("Drop a font here to test")
        self.setStyleSheet("background-color: green ")
        self.setMargin(10)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and self.isAllFonts(event.mimeData()):
            self.setStyleSheet("background-color: yellow ")
            event.accept()
        else:
            self.setStyleSheet("background-color: red ")
            event.ignore()

    def isAllFonts(self, mime):
        for url in mime.urls():
            path = url.toLocalFile()
            if not re.match(r".*\.(otf|ttf|ttc|otc)$", path):
                return False
        return True

    def dragLeaveEvent(self, event):
        self.setStyleSheet("background-color: green ")

    def dropEvent(self, event):
        self.setStyleSheet("background-color: green ")
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        self.parent.run_fontbakery(paths)
        event.accept()


class ResultsDialog(QDialog):
    def __init__(self, html):
        super(ResultsDialog, self).__init__()
        self.setWindowTitle("FontBakery Results")
        QBtn = QDialogButtonBox.Ok
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)

        self.layout = QVBoxLayout()
        self.webrenderer = QWebEngineView()
        self.webrenderer.setHtml(html)
        self.layout.addWidget(self.webrenderer)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


class FontbakeryRunner(QObject):
    signalStatus = pyqtSignal(str)
    progressStatus = pyqtSignal(float)

    def __init__(self, profilename, paths, parent=None):
        super(self.__class__, self).__init__(parent)
        self.paths = paths
        self.profilename = profilename

    @pyqtSlot()
    def start(self):
        profile = get_module_profile(
            get_module("fontbakery.profiles." + self.profilename)
        )
        runner = CheckRunner(profile, values={"fonts": self.paths})
        hr = HTMLReporter(runner=runner, loglevels=[INFO])
        prog = ProgressReporter(self.progressStatus, runner=runner)
        reporters = [hr.receive, prog.receive]
        status_generator = runner.run()
        distribute_generator(status_generator, reporters)
        self.signalStatus.emit(hr.get_html())


class MainWindow(QWidget):
    def __init__(self):
        super(QWidget, self).__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(QLabel("Choose profile to check:"))
        self.checkwidget = QComboBox()
        for p in profiles:
            self.checkwidget.addItem(p)

        self.layout.addWidget(self.checkwidget)
        self.layout.addWidget(DragDropArea(self))
        self.progress = QProgressBar(self)
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.layout.addWidget(self.progress)

    def run_fontbakery(self, paths):
        self.progress.setValue(0)
        # Setup the worker object and the worker_thread.
        profilename = self.checkwidget.currentText()
        self.worker = FontbakeryRunner(profilename, paths)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.start)
        self.worker.signalStatus.connect(self.show_html)
        self.worker.progressStatus.connect(self.update_progress)
        self.worker_thread.start()

    def update_progress(self, value):
        self.progress.setValue(value)

    def show_html(self, html):
        ResultsDialog(html).exec_()


# # start my_app
my_app = QApplication(sys.argv)
mainwindow = MainWindow()
mainwindow.raise_()
mainwindow.show()
sys.exit(my_app.exec_())
