import os
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager
from datetime import datetime

# Załaduj zmienne środowiskowe z pliku .env
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_1234')

# Konfiguracja MySQL (XAMPP domyślnie)
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASS = os.environ.get('DB_PASS', '')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'learnplatform')

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    enrollments = db.relationship('Enrollment', backref='student', lazy=True, cascade="all, delete-orphan")

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    chapters = db.relationship('Chapter', backref='course', lazy=True, order_by='Chapter.order')
    lessons = db.relationship('Lesson', backref='course', lazy=True, order_by='Lesson.order')
    enrollments = db.relationship('Enrollment', backref='enrolled_course', lazy=True, cascade="all, delete-orphan")

class Chapter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, default=0)
    lessons = db.relationship('Lesson', backref='chapter', lazy=True, order_by='Lesson.order')

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapter.id'), nullable=True)
    title = db.Column(db.String(100), nullable=False)
    youtube_url = db.Column(db.String(200), nullable=True)
    content = db.Column(db.Text, nullable=True)
    transcription = db.Column(db.Text)
    notes = db.Column(db.Text)
    summary = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)
    quizzes = db.relationship('Quiz', backref='lesson', lazy=True)
    flashcards = db.relationship('Flashcard', backref='lesson', lazy=True)
    mindmap = db.Column(db.Text)

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False) # easy, medium, hard
    questions = db.relationship('Question', backref='quiz', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct_option = db.Column(db.String(10), nullable=False) # A, B, C, D or combinations like AB
    order = db.Column(db.Integer, default=0)

class LessonProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    
class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_completed = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    front = db.Column(db.Text, nullable=False)
    back = db.Column(db.Text, nullable=False)
    progress = db.relationship('FlashcardProgress', backref='flashcard', lazy=True, cascade="all, delete-orphan")

class FlashcardProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    flashcard_id = db.Column(db.Integer, db.ForeignKey('flashcard.id'), nullable=False)
    
    # Parametry algorytmu SM-2
    next_review = db.Column(db.DateTime, default=datetime.utcnow) # Kiedy uczeń ma znów zobaczyć fiszkę
    interval = db.Column(db.Integer, default=0)        # Aktualna przerwa w dniach
    ease_factor = db.Column(db.Float, default=2.5)      # Współczynnik łatwości (od 1.3 wzwyż)
    repetitions = db.Column(db.Integer, default=0)      # Liczba udanych powtórek pod rząd

if __name__ == '__main__':
    # Próba automatycznego stworzenia bazy danych
    import sqlalchemy
    
    # Połączenie bez określania bazy danych, aby ją stworzyć
    engine_no_db = sqlalchemy.create_engine(f'mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}/?charset=utf8mb4')
    with engine_no_db.connect() as conn:
        conn.execute(sqlalchemy.text(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        print(f"Database '{DB_NAME}' ensured.")

    with app.app_context():
        db.create_all()
    print("Database models created.")
