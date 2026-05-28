import zipfile, shutil, os

# Путь к исходному .pptx (тот, что сейчас на локалке)
PPTX_OLD = r"C:\projects\my-project\ОМТ\Еженедельный отчёт\Рынок СрАзии_25_05_2026.pptx"
# Куда сохранить исправленную копию (уже для сервера)
PPTX_NEW = r"C:\projects\my-project\ОМТ\Еженедельный отчёт\Рынок СрАзии_25_05_2026_server.pptx"

# В XML внутри .pptx пути всегда с прямыми слэшами
# UNC-путь \\сервер\шара записывается как //сервер/шара
OLD_PATH = r"file:///C:\projects\my-project\ОМТ\Еженедельный%20отчёт"
NEW_PATH = r"file:////192.168.1.3\битумы\0_Битумы_ДляОтчетов\Средняя%20Азия\РБСА_еженедельные"

shutil.copy2(PPTX_OLD, PPTX_NEW)

tmp = PPTX_NEW + ".tmp"
with zipfile.ZipFile(PPTX_NEW, "r") as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename.endswith(".rels") or item.filename.endswith(".xml"):
            text = data.decode("utf-8")
            if OLD_PATH in text:
                text = text.replace(OLD_PATH, NEW_PATH)
                print(f"  заменено в: {item.filename}")
            data = text.encode("utf-8")
        zout.writestr(item, data)

os.replace(tmp, PPTX_NEW)
print("готово")
