import os
import sys
import time
import json
import re
import requests
import zipfile
import rarfile
import threading
import itertools
import inquirer
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from webdriver_manager.firefox import GeckoDriverManager
from urllib.parse import urljoin, urlparse, quote

# --- Цвета и Стили ---
CYAN = '\033[96m'
YELLOW = '\033[93m'
GREY = '\033[90m'
MAGENTA_BG = '\033[45m'
BLACK_FG = '\033[30m'
BOLD = '\033[1m'
RED = '\033[91m'
GREEN = '\033[92m'
ENDC = '\033[0m'
SEPARATOR = f"\n{GREY}────────────────────────────────────────────────────────────{ENDC}"

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_menu():
    title = f"{MAGENTA_BG}{BLACK_FG}{BOLD} COM-X.LIFE Downloader{ENDC}"
    author = f"{BOLD}Автор: https://github.com/smutchev{ENDC}"
    print(f"\n{title}  {author}\n")

class ComXLifeDownloader:
    def __init__(self, browser_choice='chrome'):
        self.base_url = "https://com-x.life"
        self.session = requests.Session()
        self.cookies = {}
        self.browser_choice = browser_choice
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': self.base_url
        }

    def get_cookies_via_selenium(self):
        print(SEPARATOR)
        print("АВТОРИЗАЦИЯ")
        driver = None
        browser_name_display = self.browser_choice.capitalize()
        try:
            if self.browser_choice == 'chrome':
                chrome_options = ChromeOptions()
                chrome_options.add_argument("--disable-blink-features=AutomationControlled")
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)
                service = ChromeService(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
            elif self.browser_choice == 'firefox':
                ff_options = FirefoxOptions()
                ff_options.set_preference("dom.webdriver.enabled", False)
                ff_options.set_preference('useAutomationExtension', False)
                ff_options.set_preference("general.useragent.override", self.headers['User-Agent'])
                service = FirefoxService(GeckoDriverManager().install())
                driver = webdriver.Firefox(service=service, options=ff_options)
            else:
                 print(f"✗ Неподдерживаемый браузер: {self.browser_choice}")
                 return False
        except Exception as e:
            print(f"✗ Ошибка запуска {browser_name_display}: {e}")
            print(f"\nПопробуйте установить {browser_name_display} или проверьте { 'ChromeDriver' if self.browser_choice == 'chrome' else 'GeckoDriver' }")
            return False
        if not driver:
             print("✗ Не удалось инициализировать драйвер")
             return False
        try:
            driver.get(self.base_url)
            print(f"\n⚠ Сейчас {browser_name_display} открыт")
            print("📝 Войдите в свой аккаунт на сайте com-x.life")
            print("⏳ Скрипт *автоматически* продолжит работу после обнаружения входа...")
            while True:
                try:
                    _ = driver.current_url
                    if driver.get_cookie("dle_user_id"):
                        print("\n✓ Обнаружен вход! Получаем cookies...")
                        cookies_list = driver.get_cookies()
                        for cookie in cookies_list:
                            self.cookies[cookie['name']] = cookie['value']
                            self.session.cookies.set(cookie['name'], cookie['value'])
                        if self.cookies:
                            self.save_cookies()
                            print(f"✓ Получено {len(self.cookies)} cookies\n")
                            return True
                        else:
                            print("✗ Не удалось извлечь cookies, хотя вход был обнаружен.")
                            return False
                    time.sleep(1)
                except Exception:
                    print(f"\n✗ Браузер был закрыт пользователем до завершения авторизации.")
                    return False
        except Exception as e:
            print(f"✗ Ошибка во время ожидания авторизации: {e}")
            return False
        finally:
            try:
                driver.quit()
            except:
                pass
        return False

    def save_cookies(self):
        cookies_file = Path('comx_cookies.json')
        with open(cookies_file, 'w', encoding='utf-8') as f:
            json.dump(self.cookies, f)
        print(f"✓ Cookies сохранены в {cookies_file}")

    def load_cookies(self):
        cookies_file = Path('comx_cookies.json')
        if cookies_file.exists():
            try:
                with open(cookies_file, 'r', encoding='utf-8') as f:
                    self.cookies = json.load(f)
                    for name, value in self.cookies.items():
                        self.session.cookies.set(name, value)
                print(f"✓ Cookies загружены из файла")
                return True
            except:
                pass
        return False

    def get_manga_id_from_url(self, url):
        match = re.search(r'/(\\d+)-', url)
        if match:
            return match.group(1)
        return None

    def _perform_search_page(self, query, page=1):
        try:
            encoded_query = quote(query)
            search_url = f"{self.base_url}/search/{encoded_query}/page/{page}/" if page > 1 else f"{self.base_url}/search/{encoded_query}"
            response = self.session.get(search_url, headers=self.headers)
            if response.status_code != 200: return []
            soup = BeautifulSoup(response.content, 'lxml')
            content = soup.find('div', id='dle-content')
            if not content: return []
            results = []
            title_tags = content.find_all('h3', class_='readed__title')
            if not title_tags: return []
            for title_tag in title_tags:
                if title_tag.a:
                    title = title_tag.a.text.strip()
                    url = title_tag.a['href']
                    if not url.startswith('http'):
                        url = urljoin(self.base_url, url)
                    results.append({'title': title, 'url': url})
            return results
        except Exception:
            return []

    def fetch_search_results_sync(self, query):
        all_results = []
        current_page = 1
        limit = 30
        while len(all_results) < limit:
            page_results = self._perform_search_page(query, page=current_page)
            if not page_results:
                break
            all_results.extend(page_results)
            current_page += 1
        return all_results[:limit]

    def get_chapters_list(self, manga_url):
        print(SEPARATOR)
        print("ПОЛУЧЕНИЕ СПИСКА ГЛАВ")
        clean_url = manga_url.split('#')[0]
        response = self.session.get(clean_url, headers=self.headers)
        if response.status_code != 200:
            print(f"✗ Ошибка при загрузке страницы: {response.status_code}")
            if "Just a moment..." in response.text or response.status_code == 403:
                 print("✗ Похоже на защиту Cloudflare или бан. Попробуйте удалить comx_cookies.json и авторизоваться заново.")
            return None, None
        soup = BeautifulSoup(response.content, 'lxml')
        script_data = None
        for script in soup.find_all('script'):
            if script.string and 'window.__DATA__' in script.string:
                script_data = script.string
                break
        if not script_data:
            print("✗ Не удалось найти данные о главах (window.__DATA__)")
            return None, None
        try:
            json_match = re.search(r'window\.__DATA__\s*=\s*({.+?});', script_data, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                chapters = data.get('chapters', [])
                chapters.sort(key=lambda x: x.get('posi', 0))
                manga_title_raw = data.get("title", "Unknown Manga")
                manga_title = self.sanitize_filename(manga_title_raw)
                print(f"✓ Найдено глав: {len(chapters)}")
                print(f"✓ Название манги: {manga_title}\n")
                return chapters, manga_title
        except Exception as e:
            print(f"✗ Ошибка парсинга данных: {e}")
        return None, None

    def download_chapter(self, chapter, base_manga_folder, news_id, manga_url):
        start_time = time.time()
        chapter_id = chapter['id']
        chapter_title_raw = chapter.get('title', f"Глава {chapter.get('number', '?')}")
        chapter_posi = chapter.get('posi', 0)

        match = re.match(r'^\s*([\d\.]+)\s*-\s*([\d\.]+)\s*(.*)', chapter_title_raw)
        if match:
            vol = match.group(1).strip()
            ch = match.group(2).strip()
            title = match.group(3).strip()
            chapter_name = f"Vol. {vol} Ch. {ch} - {title}"
        else:
            chapter_name = f"Ch. {chapter_posi:03d} - {chapter_title_raw}"

        chapter_title_safe = self.sanitize_filename(chapter_name)
        chapter_folder = base_manga_folder / chapter_title_safe

        if chapter_folder.exists() and any(f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp'] for f in chapter_folder.iterdir()):
            return True, f"Пропущено: {chapter_title_safe}"

        chapter_folder.mkdir(parents=True, exist_ok=True)
        temp_archive_path = None

        try:
            api_url = f"{self.base_url}/engine/ajax/controller.php?mod=api&action=chapters/download"
            payload = {'chapter_id': chapter_id, 'news_id': news_id}
            api_headers = self.headers.copy()
            api_headers.update({
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": manga_url,
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url
            })

            link_resp = self.session.post(api_url, headers=api_headers, data=payload)
            if link_resp.status_code != 200:
                return False, f"API ошибка {link_resp.status_code}"

            json_data = link_resp.json()
            raw_url = json_data.get("data")
            if not raw_url:
                return False, f"API не вернул ссылку ({json_data.get('error')})"

            download_url = "https:" + raw_url.replace("\\/", "/")
            parsed_url = urlparse(download_url)
            ext = Path(parsed_url.path).suffix
            if ext not in ['.zip', '.cbr', '.cbz']:
                ext = '.cbr'
            temp_archive_path = chapter_folder / f"__archive__{ext}"
            archive_response = self.session.get(download_url, headers=self.headers, stream=True, timeout=60)

            if archive_response.status_code != 200:
                return False, f"Ошибка скачивания {archive_response.status_code}"

            with open(temp_archive_path, 'wb') as f:
                for chunk in archive_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            extracted = False
            try:
                with zipfile.ZipFile(temp_archive_path, 'r') as zf:
                    zf.extractall(chapter_folder)
                extracted = True
            except (zipfile.BadZipFile, zipfile.LargeZipFile):
                try:
                    with rarfile.RarFile(temp_archive_path, 'r') as rf:
                        rf.extractall(chapter_folder)
                    extracted = True
                except Exception:
                    return False, f"Ошибка распаковки: не ZIP и не RAR"
            except Exception as e:
                return False, f"Ошибка распаковки ZIP: {e}"
            finally:
                if temp_archive_path and temp_archive_path.exists():
                    try:
                        temp_archive_path.unlink()
                    except:
                        pass

            elapsed = time.time() - start_time
            return extracted, f"Готово: {chapter_title_safe} ({elapsed:.2f}s)"
        except Exception as e:
            if temp_archive_path and temp_archive_path.exists():
                try:
                    temp_archive_path.unlink()
                except:
                    pass
            return False, f"Критическая ошибка: {e}"

    def download_manga(self, manga_url, output_dir=None, start_chapter=None, end_chapter=None, status_callback=None, progress_callback=None):
        if not self.load_cookies():
            raise RuntimeError('Cookies не найдены. Пройдите авторизацию.')

        news_id = self.get_manga_id_from_url(manga_url)
        if not news_id:
            raise RuntimeError('Не удалось определить ID манги из URL')

        chapters, manga_title = self.get_chapters_list(manga_url)
        if chapters is None or manga_title is None:
            raise RuntimeError('Не удалось получить список глав или название манги')

        start = start_chapter or 1
        end = end_chapter or 99999
        if start_chapter or end_chapter:
            chapters = [ch for ch in chapters if start <= ch.get('posi', 0) <= end]

        base_manga_folder = self.output_root / manga_title if output_dir is None else Path(output_dir) / manga_title
        base_manga_folder.mkdir(parents=True, exist_ok=True)

        total = len(chapters)
        results = []
        success_count = 0

        for index, chapter in enumerate(chapters, start=1):
            if progress_callback:
                progress_callback(index, total, chapter)

            success, message = self.download_chapter(chapter, base_manga_folder, news_id, manga_url)
            results.append({'chapter': chapter, 'success': success, 'message': message})
            if status_callback:
                status_callback(message)
            if success:
                success_count += 1
            time.sleep(0.5)

        return {
            'title': manga_title,
            'total': total,
            'success': success_count,
            'path': str(base_manga_folder),
            'results': results
        }

    def get_manga_id_from_url(self, url):
        match = re.search(r'/([0-9]+)-', url)
        return match.group(1) if match else None

    @staticmethod
    def sanitize_filename(filename):
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        filename = re.sub(r'[\s_]+', ' ', filename)
        return filename.strip()

    @staticmethod
    def parse_range(range_str):
        range_str = range_str.strip()
        if not range_str:
            return None, None
        if '-' in range_str:
            parts = range_str.split('-')
            try:
                start = int(parts[0]) if parts[0] else None
            except ValueError:
                start = None
            try:
                end = int(parts[1]) if parts[1] else None
            except ValueError:
                end = None
            return start, end
        try:
            num = int(range_str)
            return num, num
        except ValueError:
            return None, None
