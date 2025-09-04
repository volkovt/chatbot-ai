import os
from qtpy import API_NAME, QT_VERSION
from qtpy.QtCore import QLibraryInfo

print("QT_API =", os.environ.get("QT_API"))
print("QtPy backend:", API_NAME)
print("Qt version:", QT_VERSION)
print("Has QtWebEngine path():", hasattr(QLibraryInfo, "path"))
