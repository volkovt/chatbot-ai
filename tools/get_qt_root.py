import os, sys, importlib, site

def find():
    mods = []
    for name in ("PyQtWebEngine", "PyQt5"):
        try:
            m = importlib.import_module(name)
            mods.append(os.path.dirname(m.__file__))
        except Exception:
            pass

    candidates = []
    for root in mods:
        for qtname in ("Qt", "Qt5", "Qt6"):
            q = os.path.join(root, qtname)
            if os.path.isdir(q):
                candidates.append(q)

    def score(q):
        s = 0
        if os.path.isfile(os.path.join(q, "resources", "icudtl.dat")): s += 2
        if os.path.isdir(os.path.join(q, "translations", "qtwebengine_locales")): s += 1
        if os.path.isfile(os.path.join(q, "bin", "QtWebEngineProcess.exe")): s += 1
        return s

    candidates.sort(key=score, reverse=True)
    if candidates and score(candidates[0]) > 0:
        print(candidates[0])
        return 0

    packs = []
    try: packs += site.getsitepackages()
    except Exception: pass
    try: packs += [site.getusersitepackages()]
    except Exception: pass

    for sp in packs:
        for root, dirs, files in os.walk(sp):
            if "icudtl.dat" in files and ("\\Qt\\" in root or "\\Qt5\\" in root or "/Qt/" in root or "/Qt5/" in root):
                q = root
                if q.endswith(os.sep + "resources"):
                    q = os.path.dirname(q)
                print(q)
                return 0

    return 1

if __name__ == "__main__":
    sys.exit(find())
