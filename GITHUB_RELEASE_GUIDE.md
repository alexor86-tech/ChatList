# Инструкция по публикации на GitHub Release и GitHub Pages

## 📋 Подготовка к публикации

### 1. Проверка версии

Убедитесь, что версия в `version.py` актуальна:

```bash
cat version.py
```

### 2. Сборка исполняемых файлов

#### Сборка для Linux

```bash
# Активируйте виртуальное окружение
source venv/bin/activate

# Соберите исполняемый файл
pyinstaller ChatList.spec

# Соберите .deb пакет
./build_deb.sh
```

Результат:
- `dist/ChatList-{VERSION}` - исполняемый файл
- `chatlist_{VERSION}_amd64.deb` - .deb пакет

## 🚀 Публикация на GitHub Release

### Шаг 1: Создание тега

```bash
# Получите версию из version.py
VERSION=$(python3 -c "import version; print(version.__version__)")

# Создайте тег
git tag -a "v${VERSION}" -m "Release v${VERSION}"

# Отправьте тег на GitHub
git push origin "v${VERSION}"
```

### Шаг 2: Подготовка файлов для релиза

Создайте директорию для релиза:

```bash
VERSION=$(python3 -c "import version; print(version.__version__)")
mkdir -p release_files
cp dist/ChatList-${VERSION} release_files/
cp chatlist_${VERSION}_amd64.deb release_files/
```

### Шаг 3: Создание Release Notes

Используйте шаблон из `.github/release_template.md`:

```bash
# Скопируйте шаблон
cp .github/release_template.md release_notes.md

# Отредактируйте release_notes.md, заменив:
# - {VERSION} на актуальную версию
# - {PREVIOUS_VERSION} на предыдущую версию
# - YOUR_USERNAME на ваш GitHub username
# - Заполните разделы с изменениями
```

### Шаг 4: Создание Release через GitHub Web Interface

1. Перейдите на страницу репозитория: `https://github.com/YOUR_USERNAME/ChatList`
2. Нажмите **Releases** → **Draft a new release**
3. Выберите тег `v{VERSION}` (создайте новый, если нужно)
4. Заголовок: `ChatList v{VERSION}`
5. Вставьте содержимое из `release_notes.md` в описание
6. Загрузите файлы:
   - `ChatList-{VERSION}` (Linux executable)
   - `chatlist_{VERSION}_amd64.deb` (Debian package)
7. Отметьте **This is a pre-release** если это бета/альфа версия
8. Нажмите **Publish release**

### Шаг 5: Создание Release через GitHub CLI (альтернатива)

Если установлен GitHub CLI:

```bash
VERSION=$(python3 -c "import version; print(version.__version__)")

gh release create "v${VERSION}" \
  --title "ChatList v${VERSION}" \
  --notes-file release_notes.md \
  "dist/ChatList-${VERSION}#Linux executable" \
  "chatlist_${VERSION}_amd64.deb#Debian package"
```

## 📄 Настройка GitHub Pages

### Шаг 1: Подготовка HTML-лендинга

1. HTML-лендинг уже создан в `docs/index.html`
2. Отредактируйте `docs/index.html`:
   - Замените `YOUR_USERNAME` на ваш GitHub username
   - Обновите ссылки на релизы
   - При необходимости обновите версию в заголовке

### Шаг 2: Включение GitHub Pages

1. Перейдите в **Settings** → **Pages** репозитория
2. В разделе **Source** выберите:
   - **Branch**: `main` (или `master`)
   - **Folder**: `/docs`
3. Нажмите **Save**

### Шаг 3: Проверка

Через несколько минут ваш сайт будет доступен по адресу:
```
https://YOUR_USERNAME.github.io/ChatList/
```

## 🔄 Автоматизация с GitHub Actions (опционально)

Создайте файл `.github/workflows/release.yml` для автоматической сборки и публикации:

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pyinstaller
    
    - name: Get version
      id: version
      run: |
        VERSION=$(python -c "import version; print(version.__version__)")
        echo "version=$VERSION" >> $GITHUB_OUTPUT
    
    - name: Build executable
      run: |
        pyinstaller ChatList.spec
    
    - name: Build .deb package
      run: |
        chmod +x build_deb.sh
        ./build_deb.sh
    
    - name: Create Release
      uses: softprops/action-gh-release@v1
      with:
        files: |
          dist/ChatList-${{ steps.version.outputs.version }}
          chatlist_${{ steps.version.outputs.version }}_amd64.deb
        body_path: .github/release_template.md
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## 📝 Чеклист перед публикацией

- [ ] Версия обновлена в `version.py`
- [ ] Все изменения закоммичены и запушены
- [ ] Исполняемые файлы собраны и протестированы
- [ ] Release notes подготовлены
- [ ] HTML-лендинг обновлен (заменен YOUR_USERNAME)
- [ ] Тег создан и отправлен на GitHub
- [ ] Release создан с правильными файлами
- [ ] GitHub Pages настроен и работает

## 🔗 Полезные ссылки

- [GitHub Releases Documentation](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## 💡 Советы

1. **Версионирование**: Используйте [Semantic Versioning](https://semver.org/)
2. **Changelog**: Ведите CHANGELOG.md для отслеживания изменений
3. **Тестирование**: Всегда тестируйте сборки перед публикацией
4. **Описания**: Делайте подробные описания изменений в Release Notes
5. **Скриншоты**: Добавляйте скриншоты интерфейса в Release Notes

