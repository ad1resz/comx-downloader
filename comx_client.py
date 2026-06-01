import json
import re
import time
import zipfile
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import rarfile
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager


class ComXLifeClient:
    def __init__(self, browser_choice="chrome", output_root="Manga", cookie_path=None):
        self.base_url = "https://com-x.life"
        self.browser_choice = browser_choice
        self.cookie_path = Path(cookie_path or "comx_cookies.json")
        self.output_root = Path(output_root)
        self.session = requests.Session()
        self.cookies = {}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': self.base_url
        }

    def load_cookies(self):
        if self.cookie_path.exists():
            with open(self.cookie_path, 'r', encoding='utf-8') as f:
                self.cookies = json.load(f)
            for name, value in self.cookies.items():
                self.session.cookies.set(name, value)
            return True
        return False

    def save_cookies(self):
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cookie_path, 'w', encoding='utf-8') as f:
            json.dump(self.cookies, f)

    def authorize_with_selenium(self, status_callback=None, timeout=600):
        if status_callback:
            status_callback('Запуск браузера для авторизации...')

        driver = None
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
                raise RuntimeError(f"Неподдерживаемый браузер: {self.browser_choice}")

            driver.get(self.base_url)
            if status_callback:
                status_callback('Откройте сайт com-x.life и войдите в аккаунт.')

            deadline = time.time() + timeout
            while time.time() < deadline:
                cookie = driver.get_cookie('dle_user_id')
                if cookie:
                    cookies_list = driver.get_cookies()
                    self.cookies = {item['name']: item['value'] for item in cookies_list}
                    for name, value in self.cookies.items():
                        self.session.cookies.set(name, value)
                    self.save_cookies()
                    if status_callback:
                        status_callback('Авторизация завершена. Cookies сохранены.')
                    return True
                time.sleep(1)

            raise RuntimeError('Время авторизации истекло. Попробуйте ещё раз.')
        except Exception as exc:
            raise RuntimeError(f'Ошибка авторизации: {exc}')
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _perform_search_page(self, query, page=1):
        encoded_query = quote(query)
        search_url = f"{self.base_url}/search/{encoded_query}/page/{page}/" if page > 1 else f"{self.base_url}/search/{encoded_query}"
        response = self.session.get(search_url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        content = soup.find('div', id='dle-content')
        if not content:
            return []
        results = []
        title_tags = content.find_all('h3', class_='readed__title')
        for title_tag in title_tags:
            if title_tag.a:
                title = title_tag.a.text.strip()
                url = title_tag.a['href']
                if not url.startswith('http'):
                    url = urljoin(self.base_url, url)
                results.append({'title': title, 'url': url})
        return results

    def search(self, query, limit=30):
        all_results = []
        page = 1
        while len(all_results) < limit:
            page_results = self._perform_search_page(query, page=page)
            if not page_results:
                break
            all_results.extend(page_results)
            page += 1
        return all_results[:limit]

    def get_manga_info(self, manga_url):
        response = self.session.get(manga_url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        script_data = None
        for script in soup.find_all('script'):
            if script.string and 'window.__DATA__' in script.string:
                script_data = script.string
                break
        if not script_data:
            raise RuntimeError('Не удалось найти window.__DATA__ на странице манги.')

        json_match = re.search(r'window\.__DATA__\s*=\s*({.+?});', script_data, re.DOTALL)
        if not json_match:
            raise RuntimeError('Не удалось распознать JSON-данные с главами.')

        data = json.loads(json_match.group(1))
        chapters = data.get('chapters', [])
        chapters.sort(key=lambda item: item.get('posi', 0))
        manga_title = self.sanitize_filename(data.get('title', 'Unknown Manga'))
        return chapters, manga_title

    def get_manga_id_from_url(self, url):
        match = re.search(r'/([0-9]+)-', url)
        return match.group(1) if match else None

    def download_chapter(self, chapter, base_manga_folder, news_id, manga_url, output_format='jpg'):
        chapter_id = chapter['id']
        raw_title = chapter.get('title', f"Глава {chapter.get('number', '?')}")
        chapter_posi = chapter.get('posi', 0)
        match = re.match(r'^\s*([\d\.]+)\s*-\s*([\d\.]+)\s*(.*)', raw_title)
        if match:
            vol = match.group(1).strip()
            ch = match.group(2).strip()
            title = match.group(3).strip()
            chapter_name = f"Vol. {vol} Ch. {ch} - {title}"
        else:
            chapter_name = f"Ch. {chapter_posi:03d} - {raw_title}"

        safe_title = self.sanitize_filename(chapter_name)
        if output_format == 'cbr':
            final_archive_path = base_manga_folder / f"{safe_title}.cbr"
            if final_archive_path.exists():
                return True, f"Пропущено: {safe_title}"
            base_manga_folder.mkdir(parents=True, exist_ok=True)
            temp_archive_path = base_manga_folder / f"__archive__{Path(final_archive_path).suffix}"
        else:
            chapter_folder = base_manga_folder / safe_title
            if chapter_folder.exists() and any(path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp'] for path in chapter_folder.iterdir()):
                return True, f"Пропущено: {safe_title}"
            chapter_folder.mkdir(parents=True, exist_ok=True)
            temp_archive_path = chapter_folder / '__archive__'

        api_url = f"{self.base_url}/engine/ajax/controller.php?mod=api&action=chapters/download"
        payload = {'chapter_id': chapter_id, 'news_id': news_id}
        headers = self.headers.copy()
        headers.update({
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Referer': manga_url,
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': self.base_url
        })

        link_resp = self.session.post(api_url, headers=headers, data=payload)
        link_resp.raise_for_status()
        json_data = link_resp.json()
        raw_url = json_data.get('data')
        if not raw_url:
            return False, f"API вернул ошибку: {json_data.get('error')}"

        download_url = 'https:' + raw_url.replace('\\/', '/')
        archive_response = self.session.get(download_url, headers=self.headers, stream=True, timeout=60)
        archive_response.raise_for_status()

        parsed_url = urlparse(download_url)
        ext = Path(parsed_url.path).suffix.lower()
        if ext not in ['.zip', '.cbr', '.cbz']:
            ext = '.cbr'
        if output_format == 'cbr':
            temp_archive_path = base_manga_folder / f"__archive__{ext}"
        else:
            temp_archive_path = chapter_folder / f"__archive__{ext}"

        with open(temp_archive_path, 'wb') as archive_file:
            for chunk in archive_response.iter_content(chunk_size=8192):
                if chunk:
                    archive_file.write(chunk)

        extracted = False
        try:
            if output_format == 'cbr':
                final_name = base_manga_folder / f"{safe_title}.cbr"
                temp_archive_path.replace(final_name)
                extracted = True
            else:
                # extract images into folder
                try:
                    with zipfile.ZipFile(temp_archive_path, 'r') as zf:
                        zf.extractall(chapter_folder)
                    extracted = True
                except (zipfile.BadZipFile, zipfile.LargeZipFile):
                    try:
                        with rarfile.RarFile(temp_archive_path, 'r') as rf:
                            rf.extractall(chapter_folder)
                        extracted = True
                    except Exception as exc:
                        return False, f"Ошибка распаковки архива: {exc}"
        finally:
            if temp_archive_path.exists():
                try:
                    temp_archive_path.unlink()
                except Exception:
                    pass

        return extracted, f"Скачано: {safe_title}"

    def download_manga(self, manga_url, output_dir=None, start_chapter=None, end_chapter=None, selected_chapters=None, status_callback=None, progress_callback=None, output_format='jpg'):
        if not self.load_cookies():
            raise RuntimeError('Cookies не найдены. Пройдите авторизацию.')

        news_id = self.get_manga_id_from_url(manga_url)
        if not news_id:
            raise RuntimeError('Не удалось определить ID манги из URL.')

        if selected_chapters:
            chapters = selected_chapters
            _, manga_title = self.get_manga_info(manga_url)
        else:
            chapters, manga_title = self.get_manga_info(manga_url)
            if chapters is None:
                raise RuntimeError('Не удалось получить список глав.')
            start = start_chapter or 1
            end = end_chapter or 99999
            if start_chapter or end_chapter:
                chapters = [chapter for chapter in chapters if start <= chapter.get('posi', 0) <= end]

        base_manga_folder = Path(output_dir or self.output_root) / manga_title
        base_manga_folder.mkdir(parents=True, exist_ok=True)

        total = len(chapters)
        success_count = 0
        results = []

        for index, chapter in enumerate(chapters, start=1):
            if progress_callback:
                progress_callback(index, total, chapter)

            success, message = self.download_chapter(chapter, base_manga_folder, news_id, manga_url, output_format=output_format)
            results.append({'chapter': chapter, 'success': success, 'message': message})
            if status_callback:
                status_callback(message)
            if success:
                success_count += 1
            # Reduced pause to improve throughput while avoiding aggressive request bursts
            time.sleep(0.1)

        return {
            'title': manga_title,
            'total': total,
            'success': success_count,
            'path': str(base_manga_folder),
            'results': results
        }

    @staticmethod
    def sanitize_filename(text):
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            text = text.replace(char, '_')
        return re.sub(r'[\s_]+', ' ', text).strip()

    @staticmethod
    def parse_range(range_str):
        value = range_str.strip()
        if not value:
            return None, None
        if '-' in value:
            left, right = value.split('-', 1)
            try:
                start = int(left) if left else None
            except ValueError:
                start = None
            try:
                end = int(right) if right else None
            except ValueError:
                end = None
            return start, end
        try:
            number = int(value)
            return number, number
        except ValueError:
            return None, None

    @staticmethod
    def chapter_exists(base_folder, chapter_safe_name):
        try:
            base_folder = Path(base_folder)
            if not base_folder.exists():
                return False
            chapter_folder = base_folder / chapter_safe_name
            if chapter_folder.exists() and any(p.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp'] for p in chapter_folder.iterdir()):
                return True
            archive_name = base_folder / f"{chapter_safe_name}.cbr"
            if archive_name.exists():
                return True
            archive_name = base_folder / f"{chapter_safe_name}.cbz"
            if archive_name.exists():
                return True
            archive_name = base_folder / f"{chapter_safe_name}.zip"
            if archive_name.exists():
                return True
            return False
        except Exception:
            return False
