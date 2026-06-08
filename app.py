from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import app, db, User, Course, Chapter, Lesson, Quiz, Question, LessonProgress, QuizAttempt, Flashcard, FlashcardProgress, Enrollment
from utils import get_video_id, get_transcription, generate_notes, generate_quiz_questions, generate_quiz_prompt, generate_lesson_details_prompt, generate_flashcards_prompt, get_transcription_with_timestamps, generate_summary_prompt, generate_mindmap_prompt, generate_all_in_one_prompt, calculate_sm2
import json
import markdown
from datetime import datetime, timedelta

@app.route('/')
def index():
    courses = Course.query.all()
    srs_count = 0
    course_progress = {}
    course_srs_counts = {}
    my_courses = []
    other_courses = []
    
    if current_user.is_authenticated:
        now = datetime.utcnow()
        # Pobranie identyfikatorów ukończonych lekcji
        user_progress_all = LessonProgress.query.filter_by(user_id=current_user.id, completed=True).all()
        completed_lesson_ids = [p.lesson_id for p in user_progress_all]

        # Fiszki do powtórki (next_review <= now)
        reviews_query = db.session.query(FlashcardProgress).filter(
            FlashcardProgress.user_id == current_user.id,
            FlashcardProgress.next_review <= now
        )
        reviews_count = reviews_query.count()
        
        # Nowe fiszki (brak rekordu w FlashcardProgress) - tylko z ukończonych lekcji
        seen_flashcard_ids = db.session.query(FlashcardProgress.flashcard_id).filter_by(user_id=current_user.id).all()
        seen_flashcard_ids = [r[0] for r in seen_flashcard_ids]
        
        new_cards_query = Flashcard.query.filter(Flashcard.lesson_id.in_(completed_lesson_ids)) if completed_lesson_ids else Flashcard.query.filter(False)
        if seen_flashcard_ids:
            new_cards_query = new_cards_query.filter(~Flashcard.id.in_(seen_flashcard_ids))
        
        new_cards_count = new_cards_query.count()
        srs_count = reviews_count + new_cards_count

        # Obliczanie postępu i SRS dla każdego kursu
        completed_lesson_ids_set = set(completed_lesson_ids)
        
        enrolled_course_ids = {e.course_id for e in current_user.enrollments}
        
        for course in courses:
            if course.id in enrolled_course_ids:
                my_courses.append(course)
            else:
                other_courses.append(course)

            # Postęp
            total_lessons = len(course.lessons)
            if total_lessons > 0:
                completed_count = sum(1 for l in course.lessons if l.id in completed_lesson_ids_set)
                course_progress[course.id] = int((completed_count / total_lessons) * 100)
            else:
                course_progress[course.id] = 0
            
            # SRS dla kursu
            course_lesson_ids = [l.id for l in course.lessons]
            # Tylko te z kursu, które są ukończone
            completed_course_lesson_ids = [lid for lid in course_lesson_ids if lid in completed_lesson_ids_set]

            if completed_course_lesson_ids:
                c_reviews = db.session.query(FlashcardProgress).join(Flashcard).filter(
                    FlashcardProgress.user_id == current_user.id,
                    FlashcardProgress.next_review <= now,
                    Flashcard.lesson_id.in_(completed_course_lesson_ids)
                ).count()
                
                c_new = Flashcard.query.filter(Flashcard.lesson_id.in_(completed_course_lesson_ids))
                if seen_flashcard_ids:
                    c_new = c_new.filter(~Flashcard.id.in_(seen_flashcard_ids))
                c_new = c_new.count()
                
                course_srs_counts[course.id] = c_reviews + c_new
            else:
                course_srs_counts[course.id] = 0
    else:
        other_courses = courses

    return render_template('index.html', 
                           courses=courses, 
                           my_courses=my_courses,
                           other_courses=other_courses,
                           srs_count=srs_count, 
                           course_progress=course_progress, 
                           course_srs_counts=course_srs_counts)

@app.route('/reviews')
@app.route('/reviews/course/<int:course_id>')
@login_required
def global_flashcards(course_id=None):
    now = datetime.utcnow()
    
    # Pobranie identyfikatorów ukończonych lekcji
    completed_lesson_ids = [p.lesson_id for p in LessonProgress.query.filter_by(user_id=current_user.id, completed=True).all()]

    # Podstawowe filtry dla powtórek
    reviews_query = db.session.query(Flashcard).join(FlashcardProgress).filter(
        FlashcardProgress.user_id == current_user.id,
        FlashcardProgress.next_review <= now
    )
    
    # Podstawowe filtry dla nowych fiszek - tylko z ukończonych lekcji
    seen_flashcard_ids = db.session.query(FlashcardProgress.flashcard_id).filter_by(user_id=current_user.id).all()
    seen_flashcard_ids = [r[0] for r in seen_flashcard_ids]
    
    new_cards_query = Flashcard.query.filter(Flashcard.lesson_id.in_(completed_lesson_ids)) if completed_lesson_ids else Flashcard.query.filter(False)
    if seen_flashcard_ids:
        new_cards_query = new_cards_query.filter(~Flashcard.id.in_(seen_flashcard_ids))

    course = None
    if course_id:
        course = Course.query.get_or_404(course_id)
        course_lesson_ids = [l.id for l in course.lessons]
        # Tylko ukończone lekcje z tego kursu
        valid_lesson_ids = [lid for lid in course_lesson_ids if lid in completed_lesson_ids]
        reviews_query = reviews_query.filter(Flashcard.lesson_id.in_(valid_lesson_ids))
        new_cards_query = new_cards_query.filter(Flashcard.lesson_id.in_(valid_lesson_ids))
    
    reviews = reviews_query.all()
    new_cards = new_cards_query.all()
    all_to_review = reviews + new_cards
    
    return render_template('flashcards.html', lesson=None, course=course, flashcards=all_to_review, is_global=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        is_admin = True if request.form.get('is_admin') else False
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        new_user = User(
            username=username, 
            password=generate_password_hash(password),
            is_admin=is_admin
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/api/lesson/<int:lesson_id>/complete', methods=['POST'])
@login_required
def complete_lesson(lesson_id):
    progress = LessonProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson_id).first()
    if not progress:
        progress = LessonProgress(user_id=current_user.id, lesson_id=lesson_id, completed=True)
        db.session.add(progress)
    else:
        progress.completed = True
    db.session.commit()
    return {"status": "success"}

@app.route('/api/quiz/<int:quiz_id>/submit', methods=['POST'])
@login_required
def submit_quiz_api(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    data = request.json
    score = 0
    results = []
    for question in quiz.questions:
        user_answers = data.get(f'question_{question.id}', [])
        user_answer_str = "".join(sorted(user_answers)).upper()
        correct_str = question.correct_option.upper()
        is_correct = user_answer_str == correct_str
        if is_correct:
            score += 1
        
        results.append({
            "question_id": question.id,
            "correct": is_correct,
            "correct_option": correct_str,
            "user_answer": user_answer_str
        })
    
    attempt = QuizAttempt.query.filter_by(user_id=current_user.id, quiz_id=quiz.id).first()
    if attempt:
        if score > attempt.score:
            attempt.score = score
            attempt.total = len(quiz.questions)
    else:
        attempt = QuizAttempt(user_id=current_user.id, quiz_id=quiz.id, score=score, total=len(quiz.questions))
        db.session.add(attempt)
    db.session.commit()
    
    return {
        "status": "success",
        "score": score,
        "total": len(quiz.questions),
        "results": results,
        "message": f"Twój wynik: {score}/{len(quiz.questions)}"
    }

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    course_progress = 0
    chapter_progress = {}
    completed_lesson_ids = set()
    srs_count = 0
    is_enrolled = False

    if current_user.is_authenticated:
        enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course.id).first()
        is_enrolled = enrollment is not None
        
        user_progress = LessonProgress.query.filter_by(user_id=current_user.id, completed=True).all()
        completed_lesson_ids = {p.lesson_id for p in user_progress}
        
        total_lessons = len(course.lessons)
        if total_lessons > 0:
            completed_count = sum(1 for l in course.lessons if l.id in completed_lesson_ids)
            course_progress = int((completed_count / total_lessons) * 100)
        
        for chapter in course.chapters:
            total_chapter_lessons = len(chapter.lessons)
            if total_chapter_lessons > 0:
                completed_chapter_count = sum(1 for l in chapter.lessons if l.id in completed_lesson_ids)
                chapter_progress[chapter.id] = int((completed_chapter_count / total_chapter_lessons) * 100)
            else:
                chapter_progress[chapter.id] = 0

        # Oblicz SRS dla tego kursu
        now = datetime.utcnow()
        course_lesson_ids = [l.id for l in course.lessons]
        # Tylko te z kursu, które są ukończone
        completed_course_lesson_ids = [lid for lid in course_lesson_ids if lid in completed_lesson_ids]

        if completed_course_lesson_ids:
            reviews = db.session.query(FlashcardProgress).join(Flashcard).filter(
                FlashcardProgress.user_id == current_user.id,
                FlashcardProgress.next_review <= now,
                Flashcard.lesson_id.in_(completed_course_lesson_ids)
            ).count()
            
            seen_flashcard_ids = db.session.query(FlashcardProgress.flashcard_id).filter_by(user_id=current_user.id).all()
            seen_flashcard_ids = [r[0] for r in seen_flashcard_ids]
            
            new_cards = Flashcard.query.filter(Flashcard.lesson_id.in_(completed_course_lesson_ids))
            if seen_flashcard_ids:
                new_cards = new_cards.filter(~Flashcard.id.in_(seen_flashcard_ids))
            new_cards = new_cards.count()
            
            srs_count = reviews + new_cards

    return render_template('course_detail.html', 
                           course=course, 
                           course_progress=course_progress,
                           chapter_progress=chapter_progress,
                           completed_lesson_ids=completed_lesson_ids,
                           srs_count=srs_count,
                           is_enrolled=is_enrolled)

@app.route('/course/<int:course_id>/join')
@login_required
def join_course(course_id):
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course.id).first()
    
    if not enrollment:
        enrollment = Enrollment(user_id=current_user.id, course_id=course.id)
        db.session.add(enrollment)
        db.session.commit()
        flash(f'Dołączyłeś do kursu: {course.title}!')
    else:
        flash('Jesteś już zapisany na ten kurs.')
        
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/course/<int:course_id>/leave')
@login_required
def leave_course(course_id):
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course.id).first()
    
    if enrollment:
        db.session.delete(enrollment)
        db.session.commit()
        flash(f'Zrezygnowałeś z kursu: {course.title}.')
    else:
        flash('Nie jesteś zapisany na ten kurs.')
        
    return redirect(url_for('index'))

@app.route('/lesson/<int:lesson_id>')
@login_required
def lesson_detail(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # Check enrollment
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=lesson.course_id).first()
    if not enrollment and not current_user.is_admin:
        flash('Musisz dołączyć do kursu, aby zobaczyć tę lekcję.')
        return redirect(url_for('course_detail', course_id=lesson.course_id))

    video_id = get_video_id(lesson.youtube_url) if lesson.youtube_url else None
    
    # Get all lessons in course for the sidebar
    course_lessons = Lesson.query.filter_by(course_id=lesson.course_id).order_by(Lesson.order).all()
    
    # Find prev and next lessons
    prev_lesson = None
    next_lesson = None
    for i, l in enumerate(course_lessons):
        if l.id == lesson.id:
            if i > 0:
                prev_lesson = course_lessons[i-1]
            if i < len(course_lessons) - 1:
                next_lesson = course_lessons[i+1]
            break
            
    # Completion status for all lessons in sidebar
    lesson_statuses = {}
    user_progress = LessonProgress.query.filter_by(user_id=current_user.id).all()
    completed_lesson_ids = {p.lesson_id for p in user_progress if p.completed}
    
    # Quiz scores
    quiz_attempts = QuizAttempt.query.filter_by(user_id=current_user.id).all()
    quiz_scores = {a.quiz_id: f"{a.score}/{a.total}" for a in quiz_attempts}

    return render_template('lesson_detail.html', 
                           lesson=lesson, 
                           video_id=video_id if video_id else None, 
                           course_lessons=course_lessons,
                           prev_lesson=prev_lesson,
                           next_lesson=next_lesson,
                           completed_lesson_ids=completed_lesson_ids,
                           quiz_scores=quiz_scores)

@app.route('/quiz/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def take_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if request.method == 'POST':
        score = 0
        for question in quiz.questions:
            # Handle multiple choice
            user_answers = request.form.getlist(f'question_{question.id}')
            user_answer_str = "".join(sorted(user_answers)).upper()
            correct_str = question.correct_option.upper()
            
            if user_answer_str == correct_str:
                score += 1
        
        # Save attempt
        attempt = QuizAttempt.query.filter_by(user_id=current_user.id, quiz_id=quiz.id).first()
        if attempt:
            if score > attempt.score:
                attempt.score = score
                attempt.total = len(quiz.questions)
        else:
            attempt = QuizAttempt(user_id=current_user.id, quiz_id=quiz.id, score=score, total=len(quiz.questions))
            db.session.add(attempt)
        db.session.commit()
        
        flash(f'You scored {score}/{len(quiz.questions)}')
        return redirect(url_for('lesson_detail', lesson_id=quiz.lesson_id))
    return render_template('quiz.html', quiz=quiz)

# Admin Routes
@app.route('/admin/course/add', methods=['GET', 'POST'])
@login_required
def add_course():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        new_course = Course(title=title, description=description)
        db.session.add(new_course)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('admin/add_course.html')

@app.route('/admin/course/<int:course_id>/lesson/add', methods=['GET', 'POST'])
@login_required
def add_lesson(course_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        title = request.form.get('title')
        chapter_id = request.form.get('chapter_id')
        if chapter_id == "":
            chapter_id = None
        url = request.form.get('youtube_url')
        content = request.form.get('content')
        
        transcription = ""
        if url:
            video_id = get_video_id(url)
            if video_id:
                transcription = get_transcription(video_id)
                if transcription.startswith("Could not get transcript:"):
                    flash(transcription)
                    # Jeśli nie udało się pobrać transkrypcji, a mamy treść ręczną, kontynuujemy
                    if not content:
                        return redirect(url_for('course_detail', course_id=course.id))
            else:
                flash("Niepoprawny URL YouTube.")
                if not content:
                    return redirect(url_for('course_detail', course_id=course.id))

        # Priorytet ma ręcznie wpisana treść, jeśli istnieje
        source_content = content if content else transcription
        if not source_content:
            flash("Musisz podać URL YouTube lub treść lekcji.")
            return redirect(url_for('course_detail', course_id=course.id))

        notes = generate_notes(source_content)
        
        new_lesson = Lesson(
            course_id=course.id,
            chapter_id=chapter_id,
            title=title,
            youtube_url=url if url else None,
            content=content if content else None,
            transcription=transcription if transcription else None,
            notes=notes
        )
        db.session.add(new_lesson)
        db.session.commit()
        
        return redirect(url_for('edit_lesson', lesson_id=new_lesson.id, is_new=1))
    return render_template('admin/add_lesson.html', course=course, chapters=Chapter.query.filter_by(course_id=course_id).order_by(Chapter.order).all())

@app.route('/api/admin/lesson/<int:lesson_id>/prompts')
@login_required
def get_prompts_api(lesson_id):
    if not current_user.is_admin:
        return {"error": "Unauthorized"}, 403
    lesson = Lesson.query.get_or_404(lesson_id)
    difficulty = request.args.get('difficulty', 'medium')
    num_questions = request.args.get('num_questions', 3, type=int)
    
    return {
        "quiz_prompt": generate_quiz_prompt(lesson.transcription, difficulty, num_questions),
        "notes_prompt": generate_lesson_details_prompt(lesson.transcription, transcription_with_timestamps=True),
        "flashcards_prompt": generate_flashcards_prompt(lesson.transcription),
        "summary_prompt": generate_summary_prompt(lesson.transcription),
        "mindmap_prompt": generate_mindmap_prompt(lesson.transcription),
        "all_in_one_prompt": generate_all_in_one_prompt(lesson.transcription, difficulty, num_questions)
    }

@app.route('/admin/course/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        course.title = request.form.get('title')
        course.description = request.form.get('description')
        db.session.commit()
        flash('Course updated')
        return redirect(url_for('course_detail', course_id=course.id))
    return render_template('admin/edit_course.html', course=course)

@app.route('/admin/course/<int:course_id>/chapter/add', methods=['POST'])
@login_required
def add_chapter(course_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    title = request.form.get('title')
    order = Chapter.query.filter_by(course_id=course_id).count()
    new_chapter = Chapter(course_id=course_id, title=title, order=order)
    db.session.add(new_chapter)
    db.session.commit()
    flash('Chapter added')
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/admin/chapter/<int:chapter_id>/edit', methods=['POST'])
@login_required
def edit_chapter(chapter_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    chapter = Chapter.query.get_or_404(chapter_id)
    chapter.title = request.form.get('title')
    db.session.commit()
    return redirect(url_for('course_detail', course_id=chapter.course_id))

@app.route('/admin/chapter/<int:chapter_id>/delete', methods=['POST'])
@login_required
def delete_chapter(chapter_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    chapter = Chapter.query.get_or_404(chapter_id)
    course_id = chapter.course_id
    # Unlink lessons
    for lesson in chapter.lessons:
        lesson.chapter_id = None
    db.session.delete(chapter)
    db.session.commit()
    flash('Chapter deleted')
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/admin/lesson/<int:lesson_id>/flashcard/add', methods=['POST'])
@login_required
def add_flashcard(lesson_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    front = request.form.get('front')
    back = request.form.get('back')
    new_card = Flashcard(lesson_id=lesson_id, front=front, back=back)
    db.session.add(new_card)
    db.session.commit()
    flash('Flashcard added')
    return redirect(url_for('edit_lesson', lesson_id=lesson_id))

@app.route('/admin/flashcard/<int:flashcard_id>/edit', methods=['POST'])
@login_required
def edit_flashcard(flashcard_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    card = Flashcard.query.get_or_404(flashcard_id)
    card.front = request.form.get('front')
    card.back = request.form.get('back')
    db.session.commit()
    flash('Flashcard updated')
    return redirect(url_for('edit_lesson', lesson_id=card.lesson_id))

@app.route('/admin/flashcard/<int:flashcard_id>/delete', methods=['POST'])
@login_required
def delete_flashcard(flashcard_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    card = Flashcard.query.get_or_404(flashcard_id)
    lesson_id = card.lesson_id
    db.session.delete(card)
    db.session.commit()
    flash('Flashcard deleted')
    return redirect(url_for('edit_lesson', lesson_id=lesson_id))

@app.route('/admin/lesson/<int:lesson_id>/flashcards/delete_all', methods=['POST'])
@login_required
def delete_all_flashcards(lesson_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    Flashcard.query.filter_by(lesson_id=lesson_id).delete()
    db.session.commit()
    flash('All flashcards deleted')
    return redirect(url_for('edit_lesson', lesson_id=lesson_id))

@app.route('/api/admin/reorder-questions', methods=['POST'])
@login_required
def reorder_questions():
    if not current_user.is_admin:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    data = request.json
    order = data.get('order', [])
    
    for index, q_id in enumerate(order):
        question = Question.query.get(q_id)
        if question:
            question.order = index
            
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/admin/reorder-lessons', methods=['POST'])
@login_required
def reorder_lessons():
    if not current_user.is_admin:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    data = request.json
    order = data.get('order', [])
    chapter_id = data.get('chapter_id')
    
    if chapter_id == "unassigned":
        chapter_id = None

    for index, l_id in enumerate(order):
        lesson = Lesson.query.get(l_id)
        if lesson:
            lesson.order = index
            if 'chapter_id' in data: # Only update chapter if explicitly provided
                lesson.chapter_id = chapter_id
            
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/admin/lesson/<int:lesson_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_lesson(lesson_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    lesson = Lesson.query.get_or_404(lesson_id)
    questions = Question.query.filter_by(quiz_id=None).all() # This looks wrong in original, let's check
    # Original code was probably using Quiz.query.filter_by(lesson_id=lesson.id).first()
    quiz = Quiz.query.filter_by(lesson_id=lesson.id).first()
    questions = quiz.questions if quiz else []
    chapters = Chapter.query.filter_by(course_id=lesson.course_id).all()
    
    # Prompt generation for UI
    selected_difficulty = request.args.get('difficulty', 'medium')
    selected_num_questions = request.args.get('num_questions', 3, type=int)
    
    source_content = lesson.content or lesson.transcription or ""
    
    quiz_prompt = generate_quiz_prompt(source_content, selected_difficulty, selected_num_questions)
    notes_prompt = generate_lesson_details_prompt(source_content, transcription_with_timestamps=True)
    flashcards_prompt = generate_flashcards_prompt(source_content)
    summary_prompt = generate_summary_prompt(source_content)
    mindmap_prompt = generate_mindmap_prompt(source_content)
    all_in_one_prompt = generate_all_in_one_prompt(source_content, selected_difficulty, selected_num_questions)

    if request.method == 'POST':
        if 'update_lesson' in request.form:
            lesson.title = request.form.get('title')
            lesson.content = request.form.get('content')
            lesson.youtube_url = request.form.get('youtube_url')
            lesson.notes = request.form.get('notes')
            lesson.summary = request.form.get('summary')
            mindmap_code = request.form.get('mindmap', '')
            # Usuń bloki kodu markdown
            import re
            mindmap_code = re.sub(r'^```mermaid\s*', '', mindmap_code, flags=re.MULTILINE | re.IGNORECASE)
            mindmap_code = re.sub(r'```$', '', mindmap_code.strip(), flags=re.MULTILINE)
            # Usuń wiodące puste linie i spacje, które mogłyby psuć Mermaid
            mindmap_code = "\n".join([line for line in mindmap_code.splitlines() if line.strip()])
            lesson.mindmap = mindmap_code.strip()
            lesson.chapter_id = request.form.get('chapter_id') if request.form.get('chapter_id') else None
            db.session.commit()
            flash('Lesson updated')
        
        elif 'add_quiz_json' in request.form:
            difficulty = request.form.get('difficulty')
            quiz_json = request.form.get('quiz_json')
            try:
                questions_data = json.loads(quiz_json)
                # Ensure only one quiz per lesson for now, or just add to existing if preferred.
                # The requirement says "Quiz should be one per lesson".
                quiz = Quiz.query.filter_by(lesson_id=lesson.id).first()
                if not quiz:
                    quiz = Quiz(lesson_id=lesson.id, difficulty=difficulty)
                    db.session.add(quiz)
                    db.session.flush()
                
                # We will mark these as "pending" if we had a status, but for now we just add them.
                # Actually, the user wants to "preview and review" them.
                # I'll store them in session temporarily for preview? 
                # Or just add them and let the admin delete/edit them.
                # Let's add them.
                for q in questions_data:
                    question = Question(
                        quiz_id=quiz.id,
                        text=q['text'],
                        option_a=q['a'],
                        option_b=q['b'],
                        option_c=q['c'],
                        option_d=q['d'],
                        correct_option=q['correct'],
                        order=Question.query.filter_by(quiz_id=quiz.id).count()
                    )
                    db.session.add(question)
                db.session.commit()
                flash(f'Questions added to quiz!')
            except Exception as e:
                flash(f'Error parsing JSON or saving questions: {str(e)}')

        elif 'add_flashcards_json' in request.form:
            flashcards_json = request.form.get('flashcards_json')
            try:
                flashcards_data = json.loads(flashcards_json)
                for f in flashcards_data:
                    flashcard = Flashcard(
                        lesson_id=lesson.id,
                        front=f['front'],
                        back=f['back']
                    )
                    db.session.add(flashcard)
                db.session.commit()
                flash('Flashcards added!')
            except Exception as e:
                flash(f'Error parsing flashcards JSON: {str(e)}')
        
        elif 'edit_question' in request.form:
            q_id = request.form.get('question_id')
            question = Question.query.get(q_id)
            if question:
                question.text = request.form.get('text')
                question.option_a = request.form.get('option_a')
                question.option_b = request.form.get('option_b')
                question.option_c = request.form.get('option_c')
                question.option_d = request.form.get('option_d')
                question.correct_option = request.form.get('correct_option').upper()
                db.session.commit()
                flash('Question updated')

        elif 'delete_question' in request.form:
            q_id = request.form.get('question_id')
            question = Question.query.get(q_id)
            if question:
                db.session.delete(question)
                db.session.commit()
                flash('Question deleted')

        elif 'move_question' in request.form:
            q_id = request.form.get('question_id')
            direction = request.form.get('direction')
            question = Question.query.get(q_id)
            if question:
                all_questions = Question.query.filter_by(quiz_id=question.quiz_id).order_by(Question.order).all()
                idx = all_questions.index(question)
                if direction == 'up' and idx > 0:
                    other = all_questions[idx-1]
                    question.order, other.order = other.order, question.order
                elif direction == 'down' and idx < len(all_questions) - 1:
                    other = all_questions[idx+1]
                    question.order, other.order = other.order, question.order
                db.session.commit()

        elif 'add_all_in_one_json' in request.form:
            all_in_one_json = request.form.get('all_in_one_json')
            try:
                # Remove triple backticks if present
                if all_in_one_json.strip().startswith("```"):
                    lines = all_in_one_json.strip().splitlines()
                    if lines[0].startswith("```json"):
                        all_in_one_json = "\n".join(lines[1:-1])
                    else:
                        all_in_one_json = "\n".join(lines[1:-1])

                data = json.loads(all_in_one_json)
                if 'summary' in data:
                    lesson.summary = data['summary']
                if 'notes' in data:
                    lesson.notes = data['notes']
                
                if 'quiz' in data:
                    difficulty = request.form.get('difficulty', selected_difficulty)
                    quiz = Quiz.query.filter_by(lesson_id=lesson.id).first()
                    if not quiz:
                        quiz = Quiz(lesson_id=lesson.id, difficulty=difficulty)
                        db.session.add(quiz)
                        db.session.flush()
                    
                    # Optional: clear existing questions if re-generating? 
                    # For now, let's append as per current logic, but maybe user wants to replace.
                    # Given "Aktualizuj wszystko", maybe we should clear them.
                    Question.query.filter_by(quiz_id=quiz.id).delete()

                    for q in data['quiz']:
                        question_text = q.get('question') or q.get('text') or q.get('t')
                        if not question_text:
                            continue
                        
                        question = Question(
                            quiz_id=quiz.id,
                            text=question_text,
                            option_a=q['a'],
                            option_b=q['b'],
                            option_c=q['c'],
                            option_d=q['d'],
                            correct_option=q['correct'].upper(),
                            order=Question.query.filter_by(quiz_id=quiz.id).count()
                        )
                        db.session.add(question)
                
                if 'flashcards' in data:
                    # Clear existing flashcards for "Aktualizuj wszystko"
                    Flashcard.query.filter_by(lesson_id=lesson.id).delete()
                    for f in data['flashcards']:
                        flashcard = Flashcard(
                            lesson_id=lesson.id,
                            front=f['front'],
                            back=f['back']
                        )
                        db.session.add(flashcard)
                
                if 'mindmap' in data:
                    mindmap_code = data['mindmap']
                    # Usuń ewentualne bloki kodu markdown
                    import re
                    mindmap_code = re.sub(r'^```mermaid\s*', '', mindmap_code, flags=re.MULTILINE | re.IGNORECASE)
                    mindmap_code = re.sub(r'```$', '', mindmap_code.strip(), flags=re.MULTILINE)
                    # Usuń wiodące puste linie i spacje, które mogłyby psuć Mermaid
                    mindmap_code = "\n".join([line for line in mindmap_code.splitlines() if line.strip()])
                    lesson.mindmap = mindmap_code.strip()
                
                db.session.commit()
                flash('Wszystkie materiały zostały zaktualizowane na podstawie zbiorczej odpowiedzi!')
            except Exception as e:
                db.session.rollback()
                flash(f'Błąd podczas przetwarzania zbiorczego JSON: {str(e)}')

        return redirect(url_for('edit_lesson', lesson_id=lesson.id, difficulty=selected_difficulty, is_new=request.args.get('is_new')))

    # Get existing quiz and questions
    quiz = Quiz.query.filter_by(lesson_id=lesson.id).first()
    questions = Question.query.filter_by(quiz_id=quiz.id).order_by(Question.order).all() if quiz else []

    is_new = request.args.get('is_new')

    return render_template('admin/edit_lesson.html', 
                           lesson=lesson, 
                           quiz_prompt=quiz_prompt, 
                           notes_prompt=notes_prompt, 
                           summary_prompt=summary_prompt,
                           mindmap_prompt=mindmap_prompt,
                           difficulty=selected_difficulty,
                           flashcards_prompt=flashcards_prompt,
                           all_in_one_prompt=all_in_one_prompt,
                           quiz=quiz,
                           questions=questions,
                           is_new=is_new,
                           chapters=Chapter.query.filter_by(course_id=lesson.course_id).order_by(Chapter.order).all())


@app.route('/lesson/<int:lesson_id>/flashcards')
@login_required
def lesson_flashcards(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # Sprawdzenie, czy lekcja jest ukończona
    progress = LessonProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson_id, completed=True).first()
    if not progress:
        flash('Ukończ lekcję, aby odblokować fiszki.')
        return redirect(url_for('lesson_detail', lesson_id=lesson_id))

    # Pobierz fiszki, które są gotowe do powtórki (next_review <= now) lub nowe (brak progressu)
    flashcards = Flashcard.query.filter_by(lesson_id=lesson_id).all()
    now = datetime.utcnow()
    
    cards_to_review = []
    for f in flashcards:
        f_progress = FlashcardProgress.query.filter_by(user_id=current_user.id, flashcard_id=f.id).first()
        if not f_progress or f_progress.next_review <= now:
            cards_to_review.append(f)
            
    return render_template('flashcards.html', lesson=lesson, flashcards=cards_to_review)

@app.route('/api/flashcard/<int:flashcard_id>/review', methods=['POST'])
@login_required
def review_flashcard(flashcard_id):
    quality = request.json.get('quality') # 0-5
    if quality is None or not (0 <= quality <= 5):
        return jsonify({"error": "Invalid quality"}), 400
        
    progress = FlashcardProgress.query.filter_by(
        user_id=current_user.id, 
        flashcard_id=flashcard_id
    ).first()
    
    if not progress:
        progress = FlashcardProgress(
            user_id=current_user.id, 
            flashcard_id=flashcard_id,
            interval=0,
            ease_factor=2.5,
            repetitions=0
        )
        db.session.add(progress)
    
    new_interval, new_ease_factor, new_repetitions = calculate_sm2(
        quality, 
        progress.interval, 
        progress.ease_factor, 
        progress.repetitions
    )
    
    progress.interval = new_interval
    progress.ease_factor = new_ease_factor
    progress.repetitions = new_repetitions
    progress.next_review = datetime.utcnow() + timedelta(days=new_interval)
    
    db.session.commit()
    
    return jsonify({
        "status": "success",
        "next_review": progress.next_review.isoformat(),
        "interval": progress.interval
    })

@app.template_filter('markdown')
def markdown_filter(text):
    return markdown.markdown(text, extensions=['extra', 'codehilite'])

@app.route('/course/<int:course_id>/glossary')
@login_required
def course_glossary(course_id):
    course = Course.query.get_or_404(course_id)
    # Pobranie wszystkich lekcji kursu
    lesson_ids = [lesson.id for lesson in course.lessons]
    # Pobranie wszystkich fiszek (pojęć) z tych lekcji
    glossary_terms = Flashcard.query.filter(Flashcard.lesson_id.in_(lesson_ids)).all()
    # Sortowanie alfabetyczne według pojęcia (front)
    glossary_terms.sort(key=lambda x: x.front.lower())
    
    return render_template('glossary.html', course=course, terms=glossary_terms)

if __name__ == '__main__':
    app.run(debug=True)
