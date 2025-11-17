// Charts and analytics functionality

// Initialize all charts on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeCharts();
});

function initializeCharts() {
    // Attendance Distribution Chart
    initializeAttendanceChart();
    
    // Department Performance Chart
    initializeDepartmentChart();
    
    // Monthly Trends Chart
    initializeTrendsChart();
}

function initializeAttendanceChart() {
    const ctx = document.getElementById('attendanceChart');
    if (!ctx) return;

    // This would typically come from your backend API
    const chartData = {
        labels: ['Present', 'Absent', 'Late', 'Leave'],
        datasets: [{
            data: [65, 15, 10, 10],
            backgroundColor: [
                '#4361ee',
                '#f72585',
                '#f8961e',
                '#7209b7'
            ],
            borderWidth: 2,
            borderColor: '#fff'
        }]
    };

    new Chart(ctx, {
        type: 'doughnut',
        data: chartData,
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: 'Attendance Distribution'
                }
            }
        }
    });
}

function initializeDepartmentChart() {
    const ctx = document.getElementById('departmentChart');
    if (!ctx) return;

    const chartData = {
        labels: ['CSE', 'ECE', 'ME', 'CE', 'EE'],
        datasets: [{
            label: 'Attendance Percentage',
            data: [85, 78, 82, 79, 81],
            backgroundColor: 'rgba(67, 97, 238, 0.8)',
            borderColor: 'rgba(67, 97, 238, 1)',
            borderWidth: 2
        }]
    };

    new Chart(ctx, {
        type: 'bar',
        data: chartData,
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: 'Percentage (%)'
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Department-wise Attendance'
                }
            }
        }
    });
}

function initializeTrendsChart() {
    const ctx = document.getElementById('trendsChart');
    if (!ctx) return;

    const chartData = {
        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        datasets: [{
            label: 'Overall Attendance',
            data: [78, 82, 80, 85, 83, 87],
            borderColor: 'rgba(67, 97, 238, 1)',
            backgroundColor: 'rgba(67, 97, 238, 0.1)',
            tension: 0.4,
            fill: true
        }]
    };

    new Chart(ctx, {
        type: 'line',
        data: chartData,
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: 'Attendance (%)'
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Monthly Attendance Trends'
                }
            }
        }
    });
}

// Export data functionality
function exportData(format) {
    showNotification(`Exporting data in ${format.toUpperCase()} format...`, 'info');
    
    // Simulate export process
    setTimeout(() => {
        showNotification('Data exported successfully!', 'success');
        
        // Create and trigger download
        const data = 'Simulated export data';
        const blob = new Blob([data], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `attendance_export_${new Date().toISOString().split('T')[0]}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }, 2000);
}

// Real-time data updates
function updateRealTimeData() {
    // This would typically connect to WebSocket or make periodic API calls
    console.log('Updating real-time data...');
}

// Initialize real-time updates if on analytics page
if (window.location.pathname.includes('analytics')) {
    setInterval(updateRealTimeData, 30000); // Update every 30 seconds
}