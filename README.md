<div align="center">

# COM-X.LIFE Downloader

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.7+-blue.svg" alt="Python 3.7+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License MIT">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey.svg" alt="Platform">
</p>

**Графический загрузчик манги для сайта `com-x.life`.**

Приложение позволяет искать мангу, выбирать главы и скачивать их в формате `jpg` или `cbr`.

---

## О приложении

Это GUI-приложение на Python для автоматического скачивания манги с сайта **com-x.life**.

Функции:
- Поиск манги по названию или URL.
- Выбор нескольких глав с помощью списка и чекбоксов.
- Поддержка форматов:
  - `jpg` — глава распаковывается в папку с изображениями;
  - `cbr` — сохраняется одиночный архив `.cbr`.
- Авторизация через браузер и сохранение cookies в файл `comx_cookies.json`.
- Сохранение выбранной папки и формата между запусками.

---

## Первый запуск

1. **Выберите браузер** (Chrome/Firefox).
2. **Авторизуйтесь** на сайте `com-x.life` в открывшемся окне браузера.
3. **Дождитесь автоматического сохранения cookies** — скрипт продолжит работу автоматически.

> ⚠️ **Важно!** Авторизация требуется только при первом запуске. Cookies сохраняются в файл `comx_cookies.json`.

---

## Установка

### Требования

- Python 3.7 или новее
- Google Chrome или Mozilla Firefox
- Аккаунт на `com-x.life`

### Клонирование репозитория

```powershell
git clone https://github.com/ad1resz/comx-downloader.git
cd comx-downloader
```

### Установка зависимостей

```powershell
python -m venv venv
venv/Scripts/activate
pip install -r requirements.txt
```

---

## Запуск

```powershell
python main.py
```

После запуска откроется окно приложения. Если это первый запуск, нажмите **Авторизоваться** и выполните вход на сайте `com-x.life`.

---

## Как пользоваться

1. Введите название манги или URL в поле поиска.
2. Нажмите кнопку **Найти**.
3. Выберите папку для скачивания.
4. Отметьте нужные главы в списке.
5. Выберите формат: `jpg` или `cbr`.
6. Нажмите **Скачать выбранное**.

---

## Упаковка в ZIP и EXE

### ZIP-архив

Чтобы создать ZIP-пакет с текущей версией проекта:

```powershell
git archive -o comx-downloader.zip HEAD
```

Если хотите собрать архив со всеми файлами проекта:

```powershell
Compress-Archive -Path . -DestinationPath comx-downloader.zip -Force
```

### EXE-файл

Для создания EXE используйте `PyInstaller`:

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed main.py
```

Собранный файл появится в папке `dist/`.

> 💡 Если приложение использует дополнительные файлы, добавляйте их через `--add-data`.

---

## Публикация на GitHub

Если локально ещё не связан репозиторий с GitHub, выполните:

```powershell
git branch -M main
git remote add origin https://github.com/ad1resz/comx-downloader.git
git add .
git commit -m "Initial commit"
git push -u origin main
```

Если репозиторий уже добавлен, просто отправьте изменения:

```powershell
git add .
git commit -m "Update README"
git push
```

---

## Скриншоты

Добавьте скриншоты приложения в папку `screenshots/` и подключите их в README:

```markdown
![Главное окно](screenshots/main-window.png)
![Результаты поиска](screenshots/search-results.png)
```

---

## Лицензия

Проект распространяется под лицензией MIT. Подробнее в файле [LICENSE](LICENSE).
