# IPTV Manager

IPTV Manager is a self-hosted application for importing large M3U playlists, keeping stable
channel identities, tracking stream health, organizing favorites independently of upstream
playlists, and publishing TV-friendly Extended M3U endpoints.

The project is deliberately conservative about data loss: a refresh marks missing channels as
inactive, a failed health check adds history rather than deleting anything, and favorite groups
remain local source-of-truth data.

## Quick start

Requirements: Python 3.12+ and optional `ffprobe` (from FFmpeg) for deeper stream validation.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
iptv-manager
```

Open <http://localhost:8000>. API documentation is at <http://localhost:8000/docs>.

## Main workflow

1. Open the dashboard and keep the prefilled
   `https://iptv-org.github.io/iptv/index.m3u` source URL.
2. Select **Import / refresh**. Refreshes update channels in place and preserve favorite links.
3. Select **Scan active channels** to start a persistent, bounded health-scan job. The dashboard
   shows progress and results. A global scan can take hours because the application deliberately
   limits concurrent connections and waits for configured timeouts. If the application stops or
   you cancel the scan, select **Resume previous scan** to continue from the saved checkpoint.
4. Filter for **Live**, create a favorite group, and add the channels you want.
5. Copy the generated `/playlists/{group}.m3u` URL and add it at
   <https://hotplayer.app/upload>.

The playlist URL must be reachable from the TV. `localhost` and `127.0.0.1` refer to the device
opening the URL, so they will not work from Hot Player. Set `IPTV_PUBLIC_BASE_URL` to your
computer's LAN URL (for example `http://192.168.1.50:8000`) or to a public HTTPS reverse-proxy
address. Ensure the firewall permits the selected port.

For Docker:

```sh
docker compose up --build
```

Application state is stored in `data/iptv.db`. Configuration variables are documented in
`.env.example`.

## Як користуватися (українська інструкція)

### 1. Запустіть IPTV Manager

У GitHub Codespaces застосунок запускається автоматично. Відкрийте вкладку **Ports**, знайдіть
порт `8000` і натисніть **Open in Browser**. Якщо застосунок не запустився, виконайте в терміналі:

```bash
bash .devcontainer/start-app.sh
```

Для локального запуску на Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
iptv-manager
```

Після цього відкрийте <http://127.0.0.1:8000>.

### 2. Імпортуйте та перевірте канали

1. У полі **Playlist URL** залиште стандартну адресу
   `https://iptv-org.github.io/iptv/index.m3u` або введіть адресу іншого M3U-плейлиста.
2. Натисніть **Import / refresh**. Канали та їхні метадані буде збережено в локальній SQLite-базі.
3. Натисніть **Scan active channels**, щоб перевірити доступність усіх активних потоків.
4. Великий список перевіряється довго. Сторінку браузера можна закрити, але комп'ютер або
   Codespace має продовжувати працювати.
5. Якщо процес або Codespace зупинився, знову запустіть застосунок і натисніть
   **Resume previous scan**. Уже отримані результати не перевірятимуться повторно в межах
   відновленого завдання.

Один невдалий результат не видаляє канал. Він лише отримує стан **Failed**, **Uncertain** або
**Geographically restricted**, а історія перевірок зберігається.

### 3. Відберіть канали та створіть власні списки

Після завершення сканування перейдіть до списку каналів і використовуйте фільтри:

- **Health: Live** — показати лише канали, які пройшли останню перевірку;
- **Country** — країна каналу, наприклад `UA`;
- **Language** — мова, якщо джерело передає ці дані;
- **Category** — новини, спорт, музика та інші категорії;
- **Search** — пошук за назвою каналу.

У стандартному `iptv-org` плейлисті країна визначається також із `tvg-id`. Сам файл `index.m3u`
не містить повних мовних метаданих, тому фільтр **Language** може бути порожнім. Це не є помилкою
сканування.

Рекомендований порядок роботи:

1. Створіть групу Favorites, наприклад `UA Основні`, `Новини`, `Спорт`, `Фільми та серіали`,
   `Дитячі` або `Музика`.
2. У блоці **Desktop curation** скопіюйте **Verified-live playlist URL** у IPTVnator, QiTV або
   інший M3U-програвач. Також можна натиснути **Download live M3U** і відкрити локальний файл.
   Для сумісності з програвачами, які не показують `tvg-country`, видимі групи мають формат
   `UA - News`, `UA - Sports`, `US - Movies` тощо.
3. Переглядайте канали у зовнішньому програвачі та сформуйте/експортуйте вибрані канали як
   звичайний `.m3u` або `.m3u8` файл.
4. У полі **Import favorites into** виберіть створену групу, натисніть
   **Import favorites M3U** і виберіть експортований файл.
5. IPTV Manager спочатку зіставить записи за `tvg-id`, потім за URL. Наявні Favorites не
   видаляються, дублікати пропускаються, а інтерфейс покаже кількість доданих, невідомих і
   неоднозначних записів.
6. За бажанням канали також можна додавати безпосередньо в браузері кнопкою **+ Favorite**.
7. Для кожної групи застосунок створює окремий Extended M3U URL. Значення `group-title` у ньому
   відповідає назві вашої групи Favorites.

Favorites зовнішнього програвача не синхронізуються у фоні: після зміни добірки потрібно знову
експортувати її у M3U та імпортувати файл. IPTV Manager виконує безпечне об'єднання з вибраною
групою і залишається основним сховищем списку для Hot Player.

### 4. Оновлюйте вихідний плейлист без втрати Favorites

Коли список `iptv-org` зміниться, знову натисніть **Import / refresh**. Повторно створювати свої
групи не потрібно:

- існуючі канали зіставляються за стабільною ідентичністю, передусім за `tvg-id`;
- змінені URL, назви та метадані оновлюються;
- нові канали додаються;
- канали, яких більше немає у джерелі, позначаються неактивними, але не видаляються;
- групи Favorites та їхній порядок зберігаються незалежно від вихідного плейлиста;
- якщо зниклий канал повернеться, він знову стане активним у тому самому записі та залишиться
  у Favorites.

Після оновлення джерела запустіть нове сканування, якщо потрібні актуальні результати доступності
потоків. Старі Favorites при цьому залишаться на місці.

### 5. Зробіть резервну копію

Перед видаленням Codespace, великим оновленням або експериментами натисніть **Download backup**.
Файл містить локальну SQLite-базу з каналами, результатами перевірок і Favorites. Кнопка
**Restore backup** відновлює цей стан в іншому локальному середовищі або Codespace.

Дані Codespace не потрапляють до Git автоматично. Якщо видалити Codespace без резервної копії,
його локальну базу можна втратити.

### 6. Додайте готовий список у Hot Player

1. Виберіть потрібну групу Favorites.
2. Натисніть **Copy URL**.
3. Переконайтеся, що URL доступний із телевізора через звичайний HTTP або HTTPS.
4. Відкрийте <https://hotplayer.app/upload> і додайте URL як M3U-плейлист.
5. За потреби додайте URL інших груп як окремі плейлисти.

Адреси `localhost` і `127.0.0.1` працюють лише на комп'ютері, де запущений застосунок, тому
телевізор їх не відкриє. Приватний або зупинений Codespace також не є постійним хостингом для
телевізора. Для регулярного використання Hot Player запустіть IPTV Manager на постійно доступному
домашньому сервері/комп'ютері або опублікуйте його через захищений HTTPS reverse proxy. У домашній
мережі задайте, наприклад, `IPTV_PUBLIC_BASE_URL=http://192.168.1.50:8000` у `.env` і дозвольте цей
порт у firewall.

IPTV Manager публікує плейлист, але не керує внутрішніми Favorites Hot Player і не передбачає
наявності в Hot Player API. Перед заміною конфігурації на порталі перевірте, чи він зберігає вже
додані плейлисти та внутрішні Favorites.

## GitHub Codespaces

Select **Code → Codespaces → Create codespace** in GitHub. The included dev container provides
Python, installs the project dependencies, starts IPTV Manager, and opens its private forwarded
port. Codespaces uses HTTP stream validation by default; FFprobe remains an optional enhancement
for other deployments. The Codespace uses its own persistent `data/iptv.db` inside `/workspaces`.

To move channels, favorites, and health history between your computer and Codespaces:

1. Select **Download backup** in the source environment.
2. Open the destination dashboard and select **Restore backup**.
3. Choose the downloaded `.db` file. Restore is blocked while a scan is active and retains a
   timestamped safety copy of the replaced database.

Do not commit a database or `.env` file. Codespaces is an interactive workspace, not permanent TV
hosting: it stops after inactivity, and its forwarded port is private by default. See
`docs/codespaces.md` for the complete workflow and limitations.

## Current MVP

- Remote and inline Extended M3U imports with incremental upserts
- Stable per-source channel identity and duplicate URL fingerprints
- Search and filters through a paginated channel API
- Independent favorite groups with deterministic ordering
- Valid Extended M3U export for every favorite group
- Verified-live Extended M3U export for desktop IPTV players
- Non-destructive favorite M3U import with `tvg-id` and stream URL matching
- Bounded asynchronous health checks with HTTP evidence and optional `ffprobe`
- Persistent bulk-scan jobs with progress, cancellation, restart recovery, and favorite-first ordering
- Persistent, non-destructive health-check history
- Scan-origin labels plus safe SQLite backup and restore
- Responsive dashboard and OpenAPI documentation

See `docs/architecture.md` and `docs/roadmap.md` for design decisions and staged delivery.

## Development

```sh
pytest
ruff check .
```

This project does not automate Hot Player's upload portal and makes no claim that Hot Player's
internal favorites can be synchronized. The supported integration is a normal HTTP(S) playlist
URL generated by this application.
