# SMART TRAFFIC — версия со словарями

Данные карточек и лайки хранятся в `data/collections.py`. База данных не используется.
Фото и видео загружаются из существующего MinIO: `http://localhost:9000/media`.

Запуск из папки templating:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

Открыть http://localhost:8000/grid.

Исходники, шаблоны и CSS восстановлены из последних доступных записей истории VS Code за 13–15 сентября 2026 года. README, requirements.txt и .gitignore добавлены при восстановлении. Медиафайлы MinIO не включены.
