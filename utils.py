from youtube_transcript_api import YouTubeTranscriptApi
import re

def get_video_id(url):
    pattern = r'(?:v=|"/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_transcription_with_timestamps(video_id):
    try:
        transcript = YouTubeTranscriptApi().fetch(video_id)
        return transcript.snippets
    except Exception as e:
        return []

def get_transcription(video_id):
    try:
        transcript = YouTubeTranscriptApi().fetch(video_id)
        return " ".join([entry.text for entry in transcript.snippets])
    except Exception as e:
        return f"Could not get transcript: {str(e)}"

def generate_notes(transcription):
    sentences = transcription.split('. ')
    notes = "### Key Features:\n"
    for i, s in enumerate(sentences[:5]):
        if len(s) > 10:
            notes += f"- {s.strip()}.\n"
    return notes

def generate_quiz_questions(transcription, difficulty='medium'):
    questions = []
    if difficulty == 'easy':
        questions.append({
            'text': 'What is the main topic of this video?',
            'a': 'Technology', 'b': 'Cooking', 'c': 'Sports', 'd': 'Music',
            'correct': 'A'
        })
    elif difficulty == 'medium':
        questions.append({
            'text': 'Based on the transcription, which concept was explained first?',
            'a': 'Introduction', 'b': 'Core Logic', 'c': 'Conclusion', 'd': 'Example',
            'correct': 'A'
        })
    else: # hard
        questions.append({
            'text': 'What is a deep implication of the subject discussed?',
            'a': 'Complexity', 'b': 'Simplicity', 'c': 'Efficiency', 'd': 'None of the above',
            'correct': 'A'
        })
    return questions

def generate_quiz_prompt(text_content, difficulty, num_questions=3):
    prompt = f""" Jesteś ekspertem od edukacji. Na podstawie poniższej treści lekcji, wygeneruj quiz o poziomie trudności: {difficulty}. CEL: Skup się na kluczowych pojęciach, definicjach i umiejętnościach. Pytania powinny sprawdzać zrozumienie tematu merytorycznego. WYMAGANIE SPECJALNE: Niektóre pytania mogą być wielokrotnego wyboru (więcej niż jedna poprawna odpowiedź). W takim przypadku w polu "correct" podaj wszystkie poprawne litery bez spacji (np. "AB", "ACD"). Jeśli jest tylko jedna poprawna odpowiedź, podaj tylko jedną literę. Liczba pytań: {num_questions}. TREŚĆ: {text_content} Oczekiwany format odpowiedzi to WYŁĄCZNIE czysty JSON (lista obiektów), bez żadnego wstępu ani zakończenia. Struktura obiektu: {{ "question": "konkretne pytanie merytoryczne", "a": "Opcja A", "b": "Opcja B", "c": "Opcja C", "d": "Opcja D", "correct": "A" }} (Litera lub litery poprawnej odpowiedzi, np. "A", "BC", "ABD") """
    return prompt.strip()

def generate_lesson_details_prompt(text_content, transcription_with_timestamps=None):
    prompt = f""" Jesteś ekspertem od tworzenia materiałów edukacyjnych. Na podstawie poniższej treści przygotuj szczegółowe opracowanie lekcji. CEL: Przygotuj kompletne notatki, które zawierają wszystko, co użytkownik powinien wiedzieć i umieć po tej lekcji. Skup się na: 1. Główne zagadnienia (streszczenie merytoryczne). 2. Kluczowe pojęcia i ich definicje. 3. Praktyczne wskazówki lub kroki (jeśli dotyczy). 4. Podsumowanie "Czego się nauczyłeś?". Instrukcje specjalne: - Skup się na wiedzy merytorycznej. - Używaj formatowania Markdown (nagłówki, listy punktowe, pogrubienia). - Pisząc instrukcje, dbaj o to, by były uniwersalne. TREŚĆ: {text_content} Oczekiwany format: Czysty tekst w formacie Markdown, który można bezpośrednio wkleić jako opis/notatki do lekcji. """
    return prompt.strip()

def generate_flashcards_prompt(text_content):
    prompt = f""" Jesteś ekspertem od mnemotechniki i nauki. Na podstawie poniższej treści wygeneruj zestaw fiszek (flashcards). CEL: Stwórz pary: Pojęcie (front) oraz Definicja (back). 
    WYMAGANIA SPECJALNE: 
    1. Skup się na definiowaniu trudnych pojęć, terminów technicznych i kluczowych konceptów w sposób słownikowy. 
    2. Każdy "front" powinien być konkretnym pojęciem lub terminem.
    3. Każdy "back" powinien być zwięzłą, encyklopedyczną definicją tego pojęcia.
    4. Skup się WYŁĄCZNIE na wiedzy merytorycznej przekazywanej w materiale. 
    TREŚĆ: {text_content} 
    Oczekiwany format odpowiedzi to WYŁĄCZNIE czysty JSON (lista obiektów), bez żadnego wstępu ani zakończenia. Struktura obiektu: {{"front": "Pojęcie", "back": "Krótka, konkretna definicja"}} """
    return prompt.strip()

def generate_mindmap_prompt(text_content):
    prompt = f""" Jesteś ekspertem od wizualizacji wiedzy. Na podstawie poniższej treści przygotuj mapę myśli w formacie Mermaid (mindmap). CEL: Stwórz hierarchiczną strukturę pojęć omawianych w lekcji. Mapa powinna być czytelna i logicznie uporządkowana. WYMAGANIA TECHNICZNE: - Użyj WYŁĄCZNIE składni Mermaid dla mindmap (zaczynając od słowa kluczowego mindmap). - Nie używaj nawiasów okrągłych ani kwadratowych w nazwach węzłów. - Nie używaj znaków specjalnych, które mogłyby zepsuć składnię Mermaid. - Zachowaj odpowiednie wcięcia. TREŚĆ: {text_content} Oczekiwany format: WYŁĄCZNIE kod Mermaid mindmap, bez bloków kodu (```). Kod musi zaczynać się od słowa 'mindmap'. """
    return prompt.strip()

def generate_summary_prompt(text_content):
    prompt = f""" Jesteś ekspertem od syntezy informacji. Na podstawie poniższej treści przygotuj bardzo krótkie, esencjonalne podsumowanie najważniejszej wiedzy z tej lekcji. CEL: Użytkownik powinien móc w 30 sekund przeczytać to podsumowanie i przypomnieć sobie najważniejsze fakty. - Skup się na konkretach (tzw. "Key Takeaways"). - Używaj krótkich punktów (bullet points). - Maksymalnie 5-6 punktów. TREŚĆ: {text_content} Oczekiwany format: Czysty tekst w formacie Markdown (lista punktowa). """
    return prompt.strip()

def generate_all_in_one_prompt(text_content, difficulty='medium', num_questions=3):
    prompt = f""" Jesteś ekspertem od przygotowywania materiałów edukacyjnych. Na podstawie poniższej treści przygotuj KOMPLETNY zestaw materiałów dla lekcji. WYMAGANE ELEMENTY: 1. PODSUMOWANIE (krótkie, esencjonalne, 5-6 punktów). 2. SZCZEGÓŁOWE NOTATKI (format Markdown). 3. QUIZ ({num_questions} pytań, poziom {difficulty}, format JSON). 4. FISZKI (format JSON). 5. MAPA MYŚLI (format Mermaid mindmap). 
    TREŚĆ: {text_content} 
    WYMAGANIA DLA QUIZU: Niektóre pytania mogą być wielokrotnego wyboru (więcej niż jedna poprawna odpowiedź). W takim przypadku w polu "correct" podaj wszystkie poprawne litery bez spacji (np. "AB", "ACD"). Jeśli jest tylko jedna poprawna odpowiedź, podaj tylko jedną literę.
    OCZEKIWANY FORMAT ODPOWIEDZI: Odpowiedz w formacie JSON, który zawiera wszystkie te sekcje. To musi być czysty JSON bez żadnego dodatkowego tekstu ani bloków kodu (```). 
    STRUKTURA JSON: {{ "summary": "Tekst podsumowania w Markdown", "notes": "Tekst szczegółowych notatek w Markdown", "mindmap": "Kod Mermaid mindmap (bez ```, zaczyna się od 'mindmap')", "quiz": [ {{ "question": "Pytanie", "a": "Opcja A", "b": "Opcja B", "c": "Opcja C", "d": "Opcja D", "correct": "AB" }} ], "flashcards": [ {{"front": "Pojęcie", "back": "Definicja" }} ] }} """
    return prompt.strip()

def generate_course_plan_prompt(title, description):
    prompt = f""" Jesteś ekspertem od projektowania programów nauczania. Na podstawie poniższego tytułu i opisu kursu, przygotuj szczegółowy plan kursu podzielony na rozdziały i lekcje. CEL: Stwórz logiczną ścieżkę nauki, która przeprowadzi ucznia od podstaw do zaawansowanych zagadnień. WYMAGANIA: - Zaproponuj 3-5 rozdziałów. - W każdym rozdziale umieść 2-4 lekcje. - Dla każdej lekcji podaj krótki opis, co powinno się w niej znaleźć. TYTUŁ: {title} OPIS: {description} Oczekiwany format: Czysty Markdown. """
    return prompt.strip()

def calculate_sm2(quality, interval, ease_factor, repetitions):
    if quality >= 3:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = round(interval * ease_factor)
        repetitions += 1
    else:
        repetitions = 0
        interval = 1

    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ease_factor < 1.3:
        ease_factor = 1.3
        
    return interval, ease_factor, repetitions
