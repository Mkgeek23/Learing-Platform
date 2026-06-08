# Instrukcja Wdrożeniowa (Deployment Guide) - LearnPlatform 🚀

Jako profesjonalny DevOps, przygotowałem zestaw wytycznych dotyczących bezpiecznego i wydajnego wdrożenia projektu LearnPlatform na serwer produkcyjny.

---

## 1. Przygotowanie Środowiska (Best Practices)

### Zmienne Środowiskowe (.env)
Projekt korzysta z biblioteki `python-dotenv`. Na produkcji należy utworzyć plik `.env` w głównym katalogu aplikacji lub ustawić zmienne bezpośrednio w systemie/usłudze.

**Wymagane zmienne:**
```env
SECRET_KEY=twoj-super-tajny-klucz
DB_USER=uzytkownik_bazy
DB_PASS=haslo_bazy
DB_HOST=localhost
DB_NAME=learnplatform
```

### Baza Danych
Projekt został zaktualizowany do pełnej obsługi **MySQL/MariaDB** przy użyciu sterownika `mysql-connector-python`.
- **Rekomendacja:** Na produkcji używaj dedykowanego serwera MySQL.
- **Uwaga:** System automatycznie próbuje utworzyć bazę danych `learnplatform`, jeśli użytkownik ma odpowiednie uprawnienia.

---

## 2. Metoda A: Wdrożenie na VPS (Ubuntu + Nginx + Gunicorn)

To najbardziej profesjonalna i wydajna metoda.

### Krok 1: Instalacja zależności systemowych
```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx git mysql-server
```

### Krok 2: Przygotowanie aplikacji
```bash
git clone <url-twojego-repozytorium> /var/www/learnplatform
cd /var/www/learnplatform
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Utwórz plik .env i uzupełnij dane
nano .env
```

### Krok 3: Konfiguracja Gunicorn (Systemd)
Stwórz plik `/etc/systemd/system/learnplatform.service`:
```ini
[Unit]
Description=Gunicorn instance to serve LearnPlatform
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/learnplatform
Environment="PATH=/var/www/learnplatform/venv/bin"
# Zmienne można podać tutaj lub w pliku .env w WorkingDirectory
ExecStart=/var/www/learnplatform/venv/bin/gunicorn --workers 3 --bind unix:learnplatform.sock -m 007 wsgi:app

[Install]
WantedBy=multi-user.target
```
Następnie uruchom serwis:
```bash
sudo systemctl start learnplatform
sudo systemctl enable learnplatform
```

### Krok 4: Konfiguracja Nginx
Stwórz plik `/etc/nginx/sites-available/learnplatform`:
```nginx
server {
    listen 80;
    server_name twoja-domena.pl;

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/learnplatform/learnplatform.sock;
    }

    location /static/ {
        alias /var/www/learnplatform/static/;
    }
}
```
Aktywuj stronę i zrestartuj Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/learnplatform /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

---

## 3. Metoda B: Platformy PaaS (np. PythonAnywhere)

Najprostsza metoda dla projektów Flask.

1. Wgraj pliki do folderu na serwerze.
2. Stwórz **Virtualenv** w konsoli PythonAnywhere i zainstaluj `requirements.txt`.
3. W zakładce **Web**:
   - Ustaw ścieżkę do Virtualenv.
   - Skonfiguruj plik `WSGI configuration file` (zazwyczaj dostępny edytor w przeglądarce):
     ```python
     import sys
     path = '/home/twoj-uzytkownik/LearnPlatform'
     if path not in sys.path:
         sys.path.append(path)
     from app import app as application
     ```
4. Kliknij **Reload** i gotowe.

---

## 4. Bezpieczeństwo (Checklista DevOps)

- [ ] **SSL/HTTPS**: Użyj `Certbot` (Let's Encrypt) na VPS: `sudo apt install python3-certbot-nginx; sudo certbot --nginx`.
- [ ] **Debug Mode**: Upewnij się, że w pliku `.env` nie masz aktywnych trybów deweloperskich, a w `app.py` nie ma `debug=True`.
- [ ] **Firewall**: Zablokuj wszystkie porty poza 80, 443 i 22 (SSH).
- [ ] **Backup**: Skonfiguruj cykliczne backupy bazy danych MySQL (np. `mysqldump`).

---
*Dokument przygotowany przez: Professional DevOps Engineer*
