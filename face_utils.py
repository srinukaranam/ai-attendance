import cv2
import numpy as np
import os
import pickle
import base64
from PIL import Image
import io
from datetime import datetime

class FaceRecognitionSystem:
    def __init__(self):
        self.face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.known_face_ids = []
        self.known_face_names = {}
        self.model_trained = False
        self.model_file = 'face_model.yml'
        # Don't load model during initialization - will be loaded when needed
    
    def load_model(self, app):
        """Load trained face recognition model with app context"""
        with app.app_context():
            try:
                if os.path.exists(self.model_file):
                    self.recognizer.read(self.model_file)
                    self.model_trained = True
                    print("✅ Face recognition model loaded successfully")
                
                # Load face IDs and names from database
                from models import Student
                students = Student.query.filter_by(face_registered=True).all()
                
                self.known_face_ids = []
                self.known_face_names = {}
                
                for student in students:
                    self.known_face_ids.append(student.id)
                    self.known_face_names[student.id] = student.name
                
                print(f"✅ Loaded {len(self.known_face_ids)} registered faces")
                
            except Exception as e:
                print(f"❌ Error loading model: {e}")
                self.model_trained = False
    
    def detect_faces(self, image_np):
        """Detect faces in image"""
        gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
        faces = self.face_detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        return faces, gray
    
    def register_face(self, image_data, student_id, student_name, app):
        """Register a new face with app context"""
        with app.app_context():
            try:
                # Decode base64 image
                if isinstance(image_data, str) and ',' in image_data:
                    image_data = image_data.split(',')[1]
                
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))
                
                # Convert to numpy array
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                image_np = np.array(image)
                
                # Detect faces
                faces, gray = self.detect_faces(image_np)
                
                if len(faces) == 0:
                    return False, "No face detected in the image"
                
                if len(faces) > 1:
                    return False, "Multiple faces detected. Please upload image with only one face."
                
                # Extract face region
                (x, y, w, h) = faces[0]
                face_roi = gray[y:y+h, x:x+w]
                
                # Save face image for training
                face_dir = 'face_data'
                if not os.path.exists(face_dir):
                    os.makedirs(face_dir)
                
                # Save multiple samples for better recognition
                face_filename = f"{face_dir}/student_{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                cv2.imwrite(face_filename, face_roi)
                
                # Update database
                from models import Student, db
                student = Student.query.get(student_id)
                if student:
                    student.face_registered = True
                    db.session.commit()
                    
                    # Add to known faces
                    if student_id not in self.known_face_ids:
                        self.known_face_ids.append(student_id)
                        self.known_face_names[student_id] = student_name
                    
                    # Retrain model with new face
                    self.train_model()
                    
                    return True, "Face registered successfully!"
                else:
                    return False, "Student not found"
                    
            except Exception as e:
                return False, f"Error registering face: {str(e)}"
    
    def train_model(self):
        """Train the face recognition model"""
        try:
            face_dir = 'face_data'
            if not os.path.exists(face_dir):
                return False
            
            faces = []
            labels = []
            
            # Load all face images
            for filename in os.listdir(face_dir):
                if filename.startswith('student_') and filename.endswith('.jpg'):
                    # Extract student ID from filename
                    parts = filename.split('_')
                    if len(parts) >= 2:
                        student_id = int(parts[1])
                        
                        # Load face image
                        img_path = os.path.join(face_dir, filename)
                        face_img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                        
                        if face_img is not None:
                            faces.append(face_img)
                            labels.append(student_id)
            
            if len(faces) > 0:
                self.recognizer.train(faces, np.array(labels))
                self.recognizer.save(self.model_file)
                self.model_trained = True
                print(f"✅ Model trained with {len(faces)} face samples")
                return True
            else:
                return False
                
        except Exception as e:
            print(f"❌ Error training model: {e}")
            return False
    
    def recognize_face(self, frame):
        """Recognize faces in frame"""
        recognized_faces = []
        
        if not self.model_trained:
            return recognized_faces
        
        try:
            # Detect faces
            faces, gray = self.detect_faces(frame)
            
            for (x, y, w, h) in faces:
                face_roi = gray[y:y+h, x:x+w]
                
                # Recognize face
                label, confidence = self.recognizer.predict(face_roi)
                
                # LBPH returns lower confidence for better matches
                # Confidence < 50 is generally good, > 80 is poor
                if confidence < 80:  # Adjust threshold as needed
                    face_id = label
                    recognized_faces.append({
                        'face_id': face_id,
                        'location': (x, y, w, h),
                        'confidence': 100 - confidence,  # Convert to percentage
                        'name': self.known_face_names.get(face_id, 'Unknown')
                    })
                else:
                    recognized_faces.append({
                        'face_id': None,
                        'location': (x, y, w, h),
                        'confidence': 0,
                        'name': 'Unknown'
                    })
            
        except Exception as e:
            print(f"❌ Error in face recognition: {e}")
        
        return recognized_faces
    
    def get_student_by_face_id(self, face_id, app):
        """Get student details by face ID with app context"""
        with app.app_context():
            from models import Student
            return Student.query.get(face_id)

# Global instance - will be initialized properly in app.py
face_system = FaceRecognitionSystem()