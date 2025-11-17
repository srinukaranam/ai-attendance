from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Student, Faculty, Admin, AttendanceSession, Attendance
from face_utils import face_system
from config import Config
from datetime import datetime, date, timezone
import json
import cv2
import numpy as np
import base64
from PIL import Image
import io
import csv
import io
from datetime import datetime, timedelta
from utils import format_local_time, format_local_time_short, format_local_date, get_local_time

app = Flask(__name__)
app.config.from_object(Config)

# Make timezone functions available to templates
@app.context_processor
def utility_processor():
    return {
        'format_local_time': format_local_time,
        'format_local_time_short': format_local_time_short,
        'format_local_date': format_local_date,
        'get_local_time': get_local_time
    }

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_admin_user():
    with app.app_context():
        db.create_all()
        
        # First, load the face recognition model
        try:
            face_system.load_model(app)
            print("✅ Face recognition model loaded")
        except Exception as e:
            print(f"⚠️ Could not load face model: {e}")
        
        # Check if admin user already exists by email
        admin_email = 'admin@attendance.com'
        existing_admin = User.query.filter_by(email=admin_email).first()
        
        if existing_admin:
            print(f"✅ Admin user already exists: {admin_email}")
            # Ensure the existing admin has the correct type
            if existing_admin.user_type != 'admin':
                existing_admin.user_type = 'admin'
                db.session.commit()
                print("✅ Updated existing user to admin type")
            return
        
        # Create new admin user
        try:
            admin_user = User(
                email=admin_email,
                user_type='admin'
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            
            admin_profile = Admin(
                user_id=admin_user.id,
                name='System Administrator'
            )
            db.session.add(admin_profile)
            db.session.commit()
            print("✅ Admin user created: admin@attendance.com / admin123")
        except Exception as e:
            print(f"❌ Error creating admin user: {e}")


# ===== PUBLIC ROUTES =====
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.user_type == 'student':
            return redirect(url_for('student_dashboard'))
        elif current_user.user_type == 'faculty':
            return redirect(url_for('faculty_dashboard'))
        elif current_user.user_type == 'admin':
            return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        
        user = User.query.filter_by(email=email, user_type=user_type).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            flash('Login successful!', 'success')
            
            if user_type == 'student':
                return redirect(url_for('student_dashboard'))
            elif user_type == 'faculty':
                return redirect(url_for('faculty_dashboard'))
            elif user_type == 'admin':
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials or account not active', 'error')
    
    return render_template('auth/login.html')

@app.route('/register/<user_type>', methods=['GET', 'POST'])
def register(user_type):
    if user_type not in ['student', 'faculty']:
        flash('Invalid registration type', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template(f'auth/register_{user_type}.html')
        
        user = User(email=email, user_type=user_type)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        if user_type == 'student':
            student = Student(
                user_id=user.id,
                name=name,
                roll_number=request.form.get('roll_number'),
                branch=request.form.get('branch'),
                year=request.form.get('year')
            )
            db.session.add(student)
        elif user_type == 'faculty':
            faculty = Faculty(
                user_id=user.id,
                name=name,
                department=request.form.get('department'),
                employee_id=request.form.get('employee_id')
            )
            db.session.add(faculty)
        
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template(f'auth/register_{user_type}.html')

# ===== STUDENT ROUTES =====
@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.user_type != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found', 'error')
        return redirect(url_for('index'))
    
    # Get attendance statistics
    total_sessions = AttendanceSession.query.filter_by(
        branch=student.branch, 
        year=student.year
    ).count()
    
    present_count = Attendance.query.filter_by(
        student_id=student.id,
        status='Present'
    ).count()
    
    attendance_percentage = (present_count / total_sessions * 100) if total_sessions > 0 else 0
    
    # Recent attendance
    recent_attendance = db.session.query(Attendance, AttendanceSession).join(
        AttendanceSession, Attendance.session_id == AttendanceSession.id
    ).filter(
        Attendance.student_id == student.id
    ).order_by(AttendanceSession.session_date.desc()).limit(10).all()
    
    return render_template('student/dashboard.html',
                         student=student,
                         attendance_percentage=round(attendance_percentage, 2),
                         present_count=present_count,
                         total_sessions=total_sessions,
                         recent_attendance=recent_attendance)

@app.route('/student/face-registration', methods=['GET', 'POST'])
@login_required
def face_registration():
    if current_user.user_type != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        if request.content_type == 'application/json':
            image_data = request.json.get('image')
            success, message = face_system.register_face(image_data, student.id, student.name, app)
            return jsonify({'success': success, 'message': message})
    
    return render_template('student/face_registration.html', student=student)

@app.route('/student/analytics')
@login_required
def student_analytics():
    if current_user.user_type != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found', 'error')
        return redirect(url_for('index'))
    
    # Get attendance statistics
    total_sessions = AttendanceSession.query.filter_by(
        branch=student.branch, 
        year=student.year
    ).count()
    
    present_count = Attendance.query.filter_by(
        student_id=student.id,
        status='Present'
    ).count()
    
    attendance_percentage = (present_count / total_sessions * 100) if total_sessions > 0 else 0
    
    # Get all attendances for the student
    attendances = db.session.query(Attendance, AttendanceSession).join(
        AttendanceSession, Attendance.session_id == AttendanceSession.id
    ).filter(
        Attendance.student_id == student.id
    ).order_by(AttendanceSession.session_date.desc()).all()
    
    # Get simplified monthly data for demo
    months_data = [
        {'month': 'Jan 2024', 'present': 18, 'total': 20, 'percentage': 90},
        {'month': 'Feb 2024', 'present': 16, 'total': 18, 'percentage': 89},
        {'month': 'Mar 2024', 'present': 19, 'total': 20, 'percentage': 95},
        {'month': 'Apr 2024', 'present': 17, 'total': 20, 'percentage': 85},
        {'month': 'May 2024', 'present': 20, 'total': 20, 'percentage': 100},
        {'month': 'Jun 2024', 'present': 15, 'total': 18, 'percentage': 83}
    ]
    
    # Day-wise statistics
    day_stats = [
        {'day': 'Monday', 'percentage': 92},
        {'day': 'Tuesday', 'percentage': 88},
        {'day': 'Wednesday', 'percentage': 95},
        {'day': 'Thursday', 'percentage': 85},
        {'day': 'Friday', 'percentage': 90},
        {'day': 'Saturday', 'percentage': 78},
        {'day': 'Sunday', 'percentage': 65}
    ]
    
    return render_template('student/analytics.html',
                         student=student,
                         attendances=attendances,
                         months_data=months_data,
                         day_stats=day_stats,
                         total_sessions=total_sessions,
                         present_count=present_count,
                         attendance_percentage=round(attendance_percentage, 2))

@app.route('/student/download-report')
@login_required
def download_report():
    if current_user.user_type != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found', 'error')
        return redirect(url_for('index'))
    
    # Create CSV report
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Student Attendance Report'])
    writer.writerow(['Name:', student.name])
    writer.writerow(['Roll Number:', student.roll_number])
    writer.writerow(['Branch:', student.branch])
    writer.writerow(['Year:', student.year])
    writer.writerow(['Generated on:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow([])
    writer.writerow(['Date', 'Class', 'Status', 'Session Time'])
    
    # Write attendance data
    attendances = db.session.query(Attendance, AttendanceSession).join(
        AttendanceSession, Attendance.session_id == AttendanceSession.id
    ).filter(
        Attendance.student_id == student.id
    ).order_by(AttendanceSession.session_date.desc()).all()
    
    for attendance, session in attendances:
        writer.writerow([
            session.session_date.strftime('%Y-%m-%d'),
            session.class_name,
            attendance.status,
            session.start_time.strftime('%H:%M') if session.start_time else 'N/A'
        ])
    
    # Calculate summary
    total_sessions = AttendanceSession.query.filter_by(
        branch=student.branch, 
        year=student.year
    ).count()
    
    present_count = Attendance.query.filter_by(
        student_id=student.id,
        status='Present'
    ).count()
    
    attendance_percentage = (present_count / total_sessions * 100) if total_sessions > 0 else 0
    
    writer.writerow([])
    writer.writerow(['Summary'])
    writer.writerow(['Total Sessions:', total_sessions])
    writer.writerow(['Present:', present_count])
    writer.writerow(['Absent:', total_sessions - present_count])
    writer.writerow(['Attendance Percentage:', f"{attendance_percentage:.2f}%"])
    
    # Prepare response
    output.seek(0)
    response = app.response_class(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=attendance_report_{student.roll_number}.csv'}
    )
    
    return response

@app.route('/student/download-pdf-report')
@login_required
def download_pdf_report():
    if current_user.user_type != 'student':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found', 'error')
        return redirect(url_for('index'))
    
    # Get attendance data
    attendances = db.session.query(Attendance, AttendanceSession).join(
        AttendanceSession, Attendance.session_id == AttendanceSession.id
    ).filter(
        Attendance.student_id == student.id
    ).order_by(AttendanceSession.session_date.desc()).all()
    
    # Calculate statistics
    total_sessions = AttendanceSession.query.filter_by(
        branch=student.branch, 
        year=student.year
    ).count()
    
    present_count = Attendance.query.filter_by(
        student_id=student.id,
        status='Present'
    ).count()
    
    attendance_percentage = (present_count / total_sessions * 100) if total_sessions > 0 else 0
    
    return render_template('student/pdf_report.html',
                         student=student,
                         attendances=attendances,
                         total_sessions=total_sessions,
                         present_count=present_count,
                         attendance_percentage=attendance_percentage,
                         now=datetime.now())

# ===== FACULTY ROUTES =====
@app.route('/faculty/dashboard')
@login_required
def faculty_dashboard():
    if current_user.user_type != 'faculty':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    faculty = Faculty.query.filter_by(user_id=current_user.id).first()
    
    recent_sessions = AttendanceSession.query.filter_by(
        faculty_id=faculty.id
    ).order_by(AttendanceSession.start_time.desc()).limit(5).all()
    
    return render_template('faculty/dashboard.html',
                         faculty=faculty,
                         recent_sessions=recent_sessions)

# ===== FACULTY ANALYTICS & REPORTS =====
@app.route('/faculty/analytics')
@login_required
def faculty_analytics():
    if current_user.user_type != 'faculty':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    faculty = Faculty.query.filter_by(user_id=current_user.id).first()
    
    # Get session statistics
    total_sessions = AttendanceSession.query.filter_by(faculty_id=faculty.id).count()
    completed_sessions = AttendanceSession.query.filter_by(faculty_id=faculty.id, is_completed=True).count()
    active_sessions = AttendanceSession.query.filter_by(faculty_id=faculty.id, is_completed=False).count()
    
    # Get attendance statistics
    total_attendances = Attendance.query.join(AttendanceSession).filter(
        AttendanceSession.faculty_id == faculty.id
    ).count()
    
    present_count = Attendance.query.join(AttendanceSession).filter(
        AttendanceSession.faculty_id == faculty.id,
        Attendance.status == 'Present'
    ).count()
    
    overall_percentage = (present_count / total_attendances * 100) if total_attendances > 0 else 0
    
    # Get recent sessions with attendance counts
    recent_sessions = db.session.query(
        AttendanceSession,
        db.func.count(Attendance.id).filter(Attendance.status == 'Present').label('present_count'),
        db.func.count(Attendance.id).label('total_attendance')
    ).outerjoin(Attendance).filter(
        AttendanceSession.faculty_id == faculty.id
    ).group_by(AttendanceSession.id).order_by(AttendanceSession.start_time.desc()).limit(10).all()
    
    # Department statistics (simulated data for demo)
    dept_stats = [
        {'branch': 'CSE', 'sessions': 45, 'avg_attendance': 85},
        {'branch': 'ECE', 'sessions': 38, 'avg_attendance': 82},
        {'branch': 'ME', 'sessions': 32, 'avg_attendance': 78},
        {'branch': 'CE', 'sessions': 28, 'avg_attendance': 80},
        {'branch': 'EE', 'sessions': 35, 'avg_attendance': 83}
    ]
    
    return render_template('faculty/analytics.html',
                         faculty=faculty,
                         total_sessions=total_sessions,
                         completed_sessions=completed_sessions,
                         active_sessions=active_sessions,
                         overall_percentage=round(overall_percentage, 2),
                         recent_sessions=recent_sessions,
                         dept_stats=dept_stats)

@app.route('/faculty/download-report')
@login_required
def faculty_download_report():
    if current_user.user_type != 'faculty':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    faculty = Faculty.query.filter_by(user_id=current_user.id).first()
    
    # Create CSV report
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Faculty Attendance Report'])
    writer.writerow(['Name:', faculty.name])
    writer.writerow(['Employee ID:', faculty.employee_id])
    writer.writerow(['Department:', faculty.department])
    writer.writerow(['Generated on:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow([])
    writer.writerow(['Session Date', 'Class', 'Branch', 'Year', 'Total Students', 'Present', 'Absent', 'Attendance %'])
    
    # Get all sessions for this faculty
    sessions = AttendanceSession.query.filter_by(faculty_id=faculty.id).order_by(AttendanceSession.session_date.desc()).all()
    
    for session in sessions:
        # Calculate attendance for this session
        total_students = Student.query.filter_by(branch=session.branch, year=session.year).count()
        present_count = Attendance.query.filter_by(session_id=session.id, status='Present').count()
        absent_count = total_students - present_count
        attendance_percentage = (present_count / total_students * 100) if total_students > 0 else 0
        
        writer.writerow([
            session.session_date.strftime('%Y-%m-%d'),
            session.class_name,
            session.branch,
            session.year,
            total_students,
            present_count,
            absent_count,
            f"{attendance_percentage:.2f}%"
        ])
    
    # Calculate summary
    total_sessions = len(sessions)
    total_present = Attendance.query.join(AttendanceSession).filter(
        AttendanceSession.faculty_id == faculty.id,
        Attendance.status == 'Present'
    ).count()
    
    total_students_all = 0
    for session in sessions:
        total_students_all += Student.query.filter_by(branch=session.branch, year=session.year).count()
    
    overall_percentage = (total_present / total_students_all * 100) if total_students_all > 0 else 0
    
    writer.writerow([])
    writer.writerow(['Summary'])
    writer.writerow(['Total Sessions:', total_sessions])
    writer.writerow(['Total Present Records:', total_present])
    writer.writerow(['Overall Attendance Percentage:', f"{overall_percentage:.2f}%"])
    
    # Prepare response
    output.seek(0)
    response = app.response_class(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=faculty_report_{faculty.employee_id}.csv'}
    )
    
    return response

@app.route('/faculty/download-pdf-report')
@login_required
def faculty_download_pdf_report():
    if current_user.user_type != 'faculty':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    faculty = Faculty.query.filter_by(user_id=current_user.id).first()
    
    # Get all sessions for this faculty
    sessions = AttendanceSession.query.filter_by(faculty_id=faculty.id).order_by(AttendanceSession.session_date.desc()).all()
    
    # Calculate statistics
    total_sessions = len(sessions)
    completed_sessions = len([s for s in sessions if s.is_completed])
    active_sessions = total_sessions - completed_sessions
    
    total_present = Attendance.query.join(AttendanceSession).filter(
        AttendanceSession.faculty_id == faculty.id,
        Attendance.status == 'Present'
    ).count()
    
    total_students_all = 0
    session_details = []
    for session in sessions:
        total_students = Student.query.filter_by(branch=session.branch, year=session.year).count()
        total_students_all += total_students
        present_count = Attendance.query.filter_by(session_id=session.id, status='Present').count()
        attendance_percentage = (present_count / total_students * 100) if total_students > 0 else 0
        
        session_details.append({
            'date': session.session_date,
            'class_name': session.class_name,
            'branch': session.branch,
            'year': session.year,
            'total_students': total_students,
            'present_count': present_count,
            'attendance_percentage': attendance_percentage,
            'is_completed': session.is_completed
        })
    
    overall_percentage = (total_present / total_students_all * 100) if total_students_all > 0 else 0
    
    return render_template('faculty/pdf_report.html',
                         faculty=faculty,
                         sessions=session_details,
                         total_sessions=total_sessions,
                         completed_sessions=completed_sessions,
                         active_sessions=active_sessions,
                         total_present=total_present,
                         overall_percentage=overall_percentage,
                         now=datetime.now())

@app.route('/faculty/take-attendance', methods=['GET', 'POST'])
@login_required
def take_attendance():
    if current_user.user_type != 'faculty':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    faculty = Faculty.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        if request.content_type == 'application/json':
            data = request.get_json()
            
            if data.get('action') == 'process_frame':
                # Process frame for face recognition
                image_data = data.get('image')
                session_id = data.get('session_id')
                
                # Decode base64 image
                image_bytes = base64.b64decode(image_data.split(',')[1])
                image = Image.open(io.BytesIO(image_bytes))
                frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                
                # Recognize faces
                recognized_faces = face_system.recognize_face(frame)
                
                results = []
                for face in recognized_faces:
                    if face['face_id']:
                        student = face_system.get_student_by_face_id(face['face_id'], app)
                        if student:
                            # Check if already marked
                            existing = Attendance.query.filter_by(
                                student_id=student.id,
                                session_id=session_id
                            ).first()
                            
                            if not existing:
                                # Mark attendance
                                attendance = Attendance(
                                    student_id=student.id,
                                    session_id=session_id,
                                    status='Present'
                                )
                                db.session.add(attendance)
                                db.session.commit()
                            
                            results.append({
                                'success': True,
                                'student': {
                                    'id': student.id,
                                    'name': student.name,
                                    'roll_number': student.roll_number,
                                    'branch': student.branch,
                                    'year': student.year,
                                    'confidence': face['confidence']
                                }
                            })
                
                return jsonify({'faces': results})
            
            else:
                # Handle single face recognition (old format)
                face_id = data.get('face_id')
                session_id = data.get('session_id')
                
                if face_id and session_id:
                    student = face_system.get_student_by_face_id(face_id, app)
                    if student:
                        existing = Attendance.query.filter_by(
                            student_id=student.id,
                            session_id=session_id
                        ).first()
                        
                        if not existing:
                            attendance = Attendance(
                                student_id=student.id,
                                session_id=session_id,
                                status='Present'
                            )
                            db.session.add(attendance)
                            db.session.commit()
                        
                        return jsonify({
                            'success': True,
                            'student': {
                                'id': student.id,
                                'name': student.name,
                                'roll_number': student.roll_number,
                                'branch': student.branch,
                                'year': student.year
                            }
                        })
                
                return jsonify({'success': False, 'message': 'Student not recognized'})
        
        else:
            # Start new attendance session
            class_name = request.form.get('class_name')
            branch = request.form.get('branch')
            year = request.form.get('year')
            
            session = AttendanceSession(
                faculty_id=faculty.id,
                class_name=class_name,
                branch=branch,
                year=year,
                session_date=date.today()
            )
            db.session.add(session)
            db.session.commit()
            
            return render_template('faculty/take_attendance.html',
                                 faculty=faculty,
                                 session_id=session.id,
                                 class_name=class_name,
                                 branch=branch,
                                 year=year)
    
    return render_template('faculty/take_attendance.html', faculty=faculty)

@app.route('/faculty/complete-attendance/<int:session_id>', methods=['POST'])
@login_required
def complete_attendance(session_id):
    if current_user.user_type != 'faculty':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    session = AttendanceSession.query.get(session_id)
    if not session or session.faculty.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Invalid session'})
    
    session.is_completed = True
    session.end_time = datetime.now(timezone.utc)  # Use timezone-aware datetime
    
    students = Student.query.filter_by(
        branch=session.branch,
        year=session.year
    ).all()
    
    present_student_ids = [att.student_id for att in session.attendances]
    
    for student in students:
        if student.id not in present_student_ids:
            attendance = Attendance(
                student_id=student.id,
                session_id=session_id,
                status='Absent'
            )
            db.session.add(attendance)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Attendance completed successfully'})


# ===== ADMIN ROUTES =====
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.user_type != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    total_students = Student.query.count()
    total_faculty = Faculty.query.count()
    total_sessions = AttendanceSession.query.count()
    
    recent_sessions = AttendanceSession.query.order_by(
        AttendanceSession.start_time.desc()
    ).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         total_students=total_students,
                         total_faculty=total_faculty,
                         total_sessions=total_sessions,
                         recent_sessions=recent_sessions)

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.user_type != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    students = Student.query.all()
    faculty = Faculty.query.all()
    
    return render_template('admin/users.html',
                         students=students,
                         faculty=faculty)

@app.route('/admin/analytics')
@login_required
def admin_analytics():
    if current_user.user_type != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    return render_template('admin/analytics.html')

# ===== COMMON ROUTES =====
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    create_admin_user()
    app.run(debug=True, host='0.0.0.0', port=5000)