// Enhanced camera functionality with real-time face recognition

let videoStream = null;
let isCameraActive = false;
let recognitionInterval = null;
let currentSessionId = null;

// Initialize face registration
function initializeFaceRegistration() {
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const captureBtn = document.getElementById('capture-btn');
    const retakeBtn = document.getElementById('retake-btn');
    const registerBtn = document.getElementById('register-btn');
    const previewSection = document.querySelector('.preview-section');
    const previewImage = document.getElementById('preview-image');

    // Start camera
    startCamera(video);

    captureBtn.addEventListener('click', function() {
        captureImage(video, canvas, previewImage);
        previewSection.style.display = 'block';
        captureBtn.style.display = 'none';
        retakeBtn.style.display = 'inline-block';
        registerBtn.style.display = 'inline-block';
    });

    retakeBtn.addEventListener('click', function() {
        previewSection.style.display = 'none';
        captureBtn.style.display = 'inline-block';
        retakeBtn.style.display = 'none';
        registerBtn.style.display = 'none';
        startCamera(video);
    });

    registerBtn.addEventListener('click', function() {
        registerFace(canvas);
    });
}

// Initialize attendance session with real-time recognition
function initializeAttendanceSession(sessionId) {
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const faceIndicator = document.getElementById('face-indicator');
    const studentsList = document.getElementById('students-list');
    const completeBtn = document.getElementById('complete-session');
    const stopBtn = document.getElementById('stop-camera');

    currentSessionId = sessionId;
    let recognizedStudents = new Set();

    // Start camera
    startCamera(video);

    // Start real-time face recognition
    recognitionInterval = setInterval(() => {
        if (isCameraActive && video.readyState === video.HAVE_ENOUGH_DATA) {
            processVideoFrame(video, canvas, sessionId, faceIndicator, studentsList, recognizedStudents);
        }
    }, 1000); // Process every second

    completeBtn.addEventListener('click', function() {
        completeAttendanceSession(sessionId);
    });

    stopBtn.addEventListener('click', function() {
        stopCamera();
    });
}

// Process video frame for face recognition
function processVideoFrame(video, canvas, sessionId, faceIndicator, studentsList, recognizedStudents) {
    const context = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Convert canvas to base64
    const imageData = canvas.toDataURL('image/jpeg', 0.8);
    
    // Send to server for face recognition
    fetch('/faculty/take-attendance', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            action: 'process_frame',
            image: imageData,
            session_id: sessionId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.faces && data.faces.length > 0) {
            data.faces.forEach(faceData => {
                if (faceData.success && !recognizedStudents.has(faceData.student.id)) {
                    recognizedStudents.add(faceData.student.id);
                    
                    // Update UI
                    faceIndicator.innerHTML = `
                        <i class="fas fa-check-circle success"></i>
                        <span>Recognized: ${faceData.student.name}</span>
                        <small>Confidence: ${faceData.student.confidence.toFixed(1)}%</small>
                    `;
                    faceIndicator.className = 'face-indicator success';
                    
                    // Add to students list
                    addStudentToList(faceData.student, studentsList);
                    
                    // Reset indicator after 3 seconds
                    setTimeout(() => {
                        faceIndicator.innerHTML = `
                            <i class="fas fa-user"></i>
                            <span>Ready for face detection...</span>
                        `;
                        faceIndicator.className = 'face-indicator';
                    }, 3000);
                }
            });
        }
    })
    .catch(error => {
        console.error('Error processing frame:', error);
    });
}

// Start camera
async function startCamera(videoElement) {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { 
                width: 640, 
                height: 480,
                facingMode: 'user'
            } 
        });
        
        videoElement.srcObject = stream;
        videoStream = stream;
        isCameraActive = true;
        
        videoElement.onloadedmetadata = function() {
            videoElement.play();
        };
    } catch (error) {
        console.error('Error accessing camera:', error);
        showNotification('Unable to access camera. Please check permissions.', 'error');
    }
}

// Stop camera
function stopCamera() {
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
        isCameraActive = false;
    }
    
    if (recognitionInterval) {
        clearInterval(recognitionInterval);
        recognitionInterval = null;
    }
}

// Capture image
function captureImage(video, canvas, previewImage) {
    const context = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    previewImage.src = canvas.toDataURL('image/png');
    stopCamera();
}

// Register face
function registerFace(canvas) {
    const imageData = canvas.toDataURL('image/png');
    const registerBtn = document.getElementById('register-btn');
    
    registerBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Registering...';
    registerBtn.disabled = true;

    fetch('/student/face-registration', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ image: imageData })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Face registered successfully!', 'success');
            updateRegistrationSteps(3);
            setTimeout(() => {
                window.location.href = '/student/dashboard';
            }, 2000);
        } else {
            showNotification(data.message, 'error');
            registerBtn.innerHTML = '<i class="fas fa-check"></i> Register Face';
            registerBtn.disabled = false;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error registering face', 'error');
        registerBtn.innerHTML = '<i class="fas fa-check"></i> Register Face';
        registerBtn.disabled = false;
    });
}

// Add student to detected list
function addStudentToList(student, studentsList) {
    const studentElement = document.createElement('div');
    studentElement.className = 'student-item slide-in-right';
    studentElement.innerHTML = `
        <div class="student-avatar">
            <i class="fas fa-user-graduate"></i>
        </div>
        <div class="student-info">
            <strong>${student.name}</strong>
            <small>${student.roll_number} • ${student.branch} • ${student.year}</small>
            <div class="confidence">Confidence: ${student.confidence.toFixed(1)}%</div>
        </div>
        <div class="attendance-status success">
            <i class="fas fa-check"></i>
        </div>
    `;
    
    studentsList.insertBefore(studentElement, studentsList.firstChild);
    
    // Limit to 10 recent students
    if (studentsList.children.length > 10) {
        studentsList.removeChild(studentsList.lastChild);
    }
}

// Complete attendance session
function completeAttendanceSession(sessionId) {
    fetch(`/faculty/complete-attendance/${sessionId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Attendance session completed successfully!', 'success');
            stopCamera();
            setTimeout(() => {
                window.location.href = '/faculty/dashboard';
            }, 2000);
        } else {
            showNotification(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error completing attendance session', 'error');
    });
}

// Update registration steps
function updateRegistrationSteps(stepNumber) {
    const steps = document.querySelectorAll('.registration-steps .step');
    steps.forEach((step, index) => {
        if (index < stepNumber) {
            step.classList.add('active');
        } else {
            step.classList.remove('active');
        }
    });
}

// Utility function to show notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `flash-message ${type} slide-in`;
    notification.innerHTML = `
        <span class="flash-icon">
            ${type === 'success' ? '<i class="fas fa-check-circle"></i>' : 
              type === 'error' ? '<i class="fas fa-exclamation-circle"></i>' : 
              '<i class="fas fa-info-circle"></i>'}
        </span>
        ${message}
        <button class="flash-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    const container = document.querySelector('.flash-messages') || createFlashContainer();
    container.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

function createFlashContainer() {
    const container = document.createElement('div');
    container.className = 'flash-messages';
    document.querySelector('.container').insertBefore(container, document.querySelector('.main-content'));
    return container;
}

// Clean up when page is unloaded
window.addEventListener('beforeunload', function() {
    stopCamera();
});