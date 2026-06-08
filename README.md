# LearnPlatform 🎓 - YouTube Learning Accelerator

LearnPlatform to inteligentna platforma edukacyjna, która zamienia filmy z YouTube w pełnowartościowe kursy. Wykorzystuje automatyczną transkrypcję i szablony AI, aby tworzyć notatki, quizy oraz fiszki oparte na naukowych metodach zapamiętywania.

## 🌟 Główne Funkcje

- **Integracja z YouTube**: Automatyczne pobieranie transkrypcji z filmów.
- **AI-Powered Study Materials**: Generatory promptów dla LLM tworzące notatki, podsumowania i mapy myśli (Mermaid).
- **System Fiszek SRS**: Inteligentny algorytm powtórek **SM-2** (SuperMemo-2), który dostosowuje czas nauki do Twojej pamięci.
- **Interaktywne Quizy**: Testy sprawdzające wiedzę z opcją pytań wielokrotnego wyboru.
- **Panel Administratora**: Pełne zarządzanie strukturą kursów (rozdziały, lekcje) oraz edytor treści generowanych przez AI.
- **Śledzenie Postępów**: Dashboard z wizualizacją postępów w nauce i statystykami SRS.

## 🛠️ Stos Technologiczny

- **Backend**: Python, Flask, Flask-SQLAlchemy, Flask-Login, python-dotenv
- **Baza danych**: MySQL (rekomendowane), SQLite (opcjonalnie)
- **Frontend**: Jinja2, Bootstrap 5, Mermaid.js (mapy myśli)
- **Narzędzia**: youtube-transcript-api, markdown-python, mysql-connector-python

## 🚀 Szybki Start

### 1. Instalacja wymaganych bibliotek
```bash
pip install -r requirements.txt
```

### 2. Konfiguracja środowiska
Skopiuj przykładowy plik `.env` i uzupełnij dane dostępu do bazy danych MySQL:
```bash
cp .env.example .env # Jeśli dostępny, lub utwórz ręcznie
```

### 3. Konfiguracja bazy danych
System automatycznie utworzy tabele przy pierwszym uruchomieniu. Aby dodać administratora:
```bash
python seed_admin.py
```

### 4. Uruchomienie aplikacji
```bash
python app.py
```
Aplikacja będzie dostępna pod adresem: `http://127.0.0.1:5000`

## 📂 Struktura Projektu

- `app.py`: Główna logika aplikacji i trasy (routes).
- `models.py`: Definicje tabel bazy danych i modeli SQLAlchemy.
- `utils.py`: Funkcje pomocnicze, integracja z YouTube oraz szablony promptów AI.
- `templates/`: Szablony HTML (osobne widoki dla studenta i panelu admina).
- `static/`: Pliki CSS i JS.

## 📝 Licencja
Projekt stworzony w celach edukacyjnych.
