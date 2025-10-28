// Dashboard JavaScript
const socket = io();
let isRunning = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard loaded');
    fetchSystemStatus();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    const videoSource = document.getElementById('videoSource');
    videoSource.addEventListener('change', handleSourceChange);
}

// Handle video source change
function handleSourceChange() {
    const source = document.getElementById('videoSource').value;
    const videoPathGroup = document.getElementById('videoPathGroup');
    const esp32UrlGroup = document.getElementById('esp32UrlGroup');
    
    videoPathGroup.style.display = source === 'video' ? 'block' : 'none';
    esp32UrlGroup.style.display = source === 'esp32cam' ? 'block' : 'none';
}

// WebSocket: Connected
socket.on('connect', () => {
    console.log('✅ Connected to server');
    showNotification('Connected to server', 'success');
});

// WebSocket: Receive stats
socket.on('stats', (data) => {
    updateStats(data);
});

// WebSocket: Disconnected
socket.on('disconnect', () => {
    console.log('❌ Disconnected from server');
    showNotification('Disconnected from server', 'error');
});

// Start Detection
async function startDetection() {
    const source = document.getElementById('videoSource').value;
    const videoPath = document.getElementById('videoPath').value;
    const esp32Url = document.getElementById('esp32Url').value;
    
    const payload = {
        source_type: source,
        video_path: videoPath,
        esp32_url: esp32Url
    };
    
    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            console.log('Started:', data);
            isRunning = true;
            
            // Show video feed
            document.getElementById('videoFeed').src = '/video_feed?t=' + Date.now();
            document.getElementById('noVideoPlaceholder').style.display = 'none';
            document.getElementById('recordingIndicator').style.display = 'flex';
            
            // Update status
            updateStatusBadge('active');
            document.getElementById('systemStatus').textContent = 'Detecting';
            
            showNotification('Detection started', 'success');
        } else {
            throw new Error(data.error || 'Failed to start');
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('Failed to start: ' + error.message, 'error');
    }
}

// Stop Detection
async function stopDetection() {
    try {
        const response = await fetch('/api/stop', { method: 'POST' });
        const data = await response.json();
        
        console.log('Stopped:', data);
        isRunning = false;
        
        // Hide video feed
        document.getElementById('videoFeed').src = '';
        document.getElementById('noVideoPlaceholder').style.display = 'flex';
        document.getElementById('recordingIndicator').style.display = 'none';
        
        // Reset stats
        document.getElementById('fpsValue').textContent = '0';
        document.getElementById('personsValue').textContent = '0';
        
        // Update status
        updateStatusBadge('stopped');
        document.getElementById('systemStatus').textContent = 'Ready';
        
        // Clear detections
        showEmptyDetections();
        
        showNotification('Detection stopped', 'info');
    } catch (error) {
        console.error('Error:', error);
        showNotification('Failed to stop: ' + error.message, 'error');
    }
}

// Fetch system status
async function fetchSystemStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        document.getElementById('deviceInfo').textContent = 
            data.device ? data.device.toUpperCase() : 'N/A';
        
        if (data.is_running) {
            updateStatusBadge('active');
        }
    } catch (error) {
        console.error('Error fetching status:', error);
    }
}

// Update stats display
function updateStats(data) {
    document.getElementById('fpsValue').textContent = data.fps || 0;
    document.getElementById('personsValue').textContent = data.persons || 0;
    
    if (data.detections && data.detections.length > 0) {
        updateDetectionsList(data.detections);
    } else {
        showEmptyDetections();
    }
}

// Update detections list
function updateDetectionsList(detections) {
    const list = document.getElementById('detectionsList');
    
    list.innerHTML = detections.map((det, idx) => `
        <div class="detection-item">
            <strong>Person ${idx + 1}</strong>
            <small>
                Confidence: ${(det.confidence * 100).toFixed(1)}%<br>
                BBox: [${det.bbox.join(', ')}]
            </small>
        </div>
    `).join('');
}

// Show empty detections
function showEmptyDetections() {
    const list = document.getElementById('detectionsList');
    list.innerHTML = `
        <div class="empty-state">
            <span class="empty-icon">📭</span>
            <p>No detections in frame</p>
        </div>
    `;
}

// Update status badge
function updateStatusBadge(status) {
    const badge = document.getElementById('statusBadge');
    
    if (status === 'active') {
        badge.textContent = '● ACTIVE';
        badge.className = 'badge badge-active';
    } else {
        badge.textContent = '● STOPPED';
        badge.className = 'badge badge-stopped';
    }
}

// Show notification (simple console for now)
function showNotification(message, type) {
    console.log(`[${type.toUpperCase()}] ${message}`);
}
