/**
 * Tourist Registration System - JavaScript
 * Handles form submission, webcam capture, and DID generation
 */

let webcamStream = null;
let capturedImages = [];

// Start webcam
async function startWebcam() {
    try {
        const constraints = {
            video: {
                width: { ideal: 1280 },
                height: { ideal: 720 },
                facingMode: 'user'
            }
        };
        
        webcamStream = await navigator.mediaDevices.getUserMedia(constraints);
        const video = document.getElementById('webcamVideo');
        video.srcObject = webcamStream;
        
        // Enable capture button
        document.getElementById('captureBtn').disabled = false;
        
        console.log('✅ Webcam started');
        alert('📷 Camera started! Position yourself and click Capture Photo');
        
    } catch (error) {
        console.error('Webcam error:', error);
        alert('❌ Failed to access webcam. Please check permissions.');
    }
}

// Stop webcam
function stopWebcam() {
    if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
        webcamStream = null;
        
        const video = document.getElementById('webcamVideo');
        video.srcObject = null;
        
        document.getElementById('captureBtn').disabled = true;
        
        console.log('⏹️ Webcam stopped');
    }
}

// Capture photo from webcam
function capturePhoto() {
    const video = document.getElementById('webcamVideo');
    const canvas = document.createElement('canvas');
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);
    
    // Convert to base64
    const imageData = canvas.toDataURL('image/jpeg', 0.9);
    
    // Add to captured images
    capturedImages.push(imageData);
    
    // Display preview
    displayCapturedImage(imageData);
    
    console.log(`📸 Photo captured (${capturedImages.length} total)`);
    alert(`✅ Photo captured! (${capturedImages.length} photos)`);
}

// Display captured image
function displayCapturedImage(imageData) {
    const preview = document.getElementById('capturePreview');
    
    const img = document.createElement('img');
    img.src = imageData;
    img.className = 'captured-image';
    img.title = `Capture ${capturedImages.length}`;
    
    preview.appendChild(img);
}

// Reset form
function resetForm() {
    if (confirm('⚠️ Are you sure you want to reset the form? All data will be lost.')) {
        document.getElementById('registrationForm').reset();
        capturedImages = [];
        document.getElementById('capturePreview').innerHTML = '';
        stopWebcam();
        console.log('🔄 Form reset');
    }
}

// Parse itinerary text
function parseItinerary(itineraryText) {
    if (!itineraryText || itineraryText.trim() === '') {
        return [];
    }
    
    // Simple parser - format: "Place (Date1-Date2)"
    // Example: "Delhi (Nov 20-22) → Agra (Nov 23-24)"
    
    const itinerary = [];
    const segments = itineraryText.split('→').map(s => s.trim());
    
    for (const segment of segments) {
        const match = segment.match(/(.+?)\s*\((.+?)\)/);
        if (match) {
            itinerary.push({
                place: match[1].trim(),
                dates: match[2].trim(),
                hotel: ''  // Optional field
            });
        }
    }
    
    return itinerary;
}

// Handle form submission
document.getElementById('registrationForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Validate captured images
    if (capturedImages.length === 0) {
        alert('⚠️ Please capture at least one photo for biometric registration');
        return;
    }
    
    // Collect form data
    const formData = {
        name: document.getElementById('name').value.trim(),
        nationality: document.getElementById('nationality').value.trim(),
        id_type: document.getElementById('idType').value,
        id_number: document.getElementById('idNumber').value.trim(),
        phone: document.getElementById('phone').value.trim(),
        email: document.getElementById('email').value.trim(),
        entry_point: document.getElementById('entryPoint').value,
        visit_duration: document.getElementById('visitDuration').value,
        itinerary: parseItinerary(document.getElementById('itinerary').value),
        face_images: capturedImages
    };
    
    // Validate required fields
    if (!formData.name || !formData.id_type || !formData.id_number || 
        !formData.phone || !formData.entry_point) {
        alert('⚠️ Please fill in all required fields');
        return;
    }
    
    // Show loading
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '⏳ Registering...';
    
    try {
        console.log('📤 Submitting registration...');
        
        const response = await fetch('/api/register_tourist', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            console.log('✅ Registration successful:', result);
            
            // Show success modal with DID and QR code
            showSuccessModal(result);
            
            // Stop webcam
            stopWebcam();
            
        } else {
            throw new Error(result.error || 'Registration failed');
        }
        
    } catch (error) {
        console.error('❌ Registration error:', error);
        alert(`❌ Registration failed: ${error.message}`);
        
        // Restore button
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
});

// Show success modal
function showSuccessModal(result) {
    const modal = document.getElementById('successModal');
    const didDisplay = document.getElementById('displayDID');
    
    // Display DID
    didDisplay.textContent = result.did;
    
    // Generate QR code
    const qrContainer = document.getElementById('qrCode');
    qrContainer.innerHTML = ''; // Clear previous
    
    const qrData = JSON.stringify({
        did: result.did,
        name: document.getElementById('name').value,
        entry_point: document.getElementById('entryPoint').value,
        timestamp: new Date().toISOString()
    });
    
    new QRCode(qrContainer, {
        text: qrData,
        width: 250,
        height: 250,
        colorDark: '#667eea',
        colorLight: '#ffffff',
        correctLevel: QRCode.CorrectLevel.H
    });
    
    // Show modal
    modal.style.display = 'flex';
    
    console.log('✨ Success modal displayed');
}

// Close modal
function closeModal() {
    document.getElementById('successModal').style.display = 'none';
    
    // Reset form for next registration
    resetForm();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('📋 Registration page loaded');
    
    // Check webcam availability
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        console.log('✅ Webcam API available');
    } else {
        console.warn('⚠️ Webcam API not available');
        alert('⚠️ Webcam not supported in this browser. Please use Chrome, Firefox, or Edge.');
    }
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    stopWebcam();
});
