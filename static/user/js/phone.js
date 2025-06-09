function validatePhoneNumber(input, isSubmit) {
    const phoneNumber = input.value;
    const errorMessage = document.getElementById('phone-error');
    
    // Remove any existing error message element
    if (errorMessage) {
        errorMessage.remove();
    }
    
    // Check if the field is empty (handled by required attribute)
    if (phoneNumber === '') {
        if (isSubmit) {
            alert("Phone number is required!");
            input.focus();
        }
        return false;
    }
    
    // Check for exactly 10 digits
    if (!/^\d{10}$/.test(phoneNumber)) {
        const msg = "Please enter exactly 10 digits";
        showError(input, msg, isSubmit);
        return false;
    }
    
    // Check if all digits are the same
    if (/^(\d)\1{9}$/.test(phoneNumber)) {
        const msg = "All digits cannot be the same";
        showError(input, msg, isSubmit);
        return false;
    }
    
    return true;
}

function showError(input, message, showPopup) {
    // Create error message element
    const errorElement = document.createElement('div');
    errorElement.id = 'phone-error';
    errorElement.style.color = 'red';
    errorElement.style.marginTop = '5px';
    errorElement.textContent = message;
    
    // Insert after the input field
    input.parentNode.appendChild(errorElement);
    
    // Focus on the input field
    input.focus();
    
    // Show popup alert if requested (during submission)
    if (showPopup) {
        alert(message);
        // Clear the invalid input only at submission time
        input.value = '';
    }
}

// Form submission handler
document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(event) {
            const phoneInput = document.getElementById('id_phone');
            if (!validatePhoneNumber(phoneInput, true)) {
                event.preventDefault(); // Prevent form submission
            }
        });
    }
});


 // Animate counting for stat numbers
 document.addEventListener('DOMContentLoaded', function() {
    const numberElements = document.querySelectorAll('.number');
    
    numberElements.forEach(function(element) {
        const target = parseInt(element.getAttribute('data-count'), 10);
        let count = 0;
        const duration = 1000; // ms
        const interval = 50; // ms
        const step = Math.max(1, Math.floor(target / (duration / interval)));
        
        const timer = setInterval(function() {
            count += step;
            if (count > target) {
                element.textContent = target;
                clearInterval(timer);
            } else {
                element.textContent = count;
            }
        }, interval);
    });
    
    // Add rotation animation to the processing icon
    const processingIcon = document.querySelector('.stat-card:nth-child(3) .stat-icon i');
    processingIcon.style.animation = 'spin 2s linear infinite';
});

// Add spinning animation
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);


function openImage(element) {
    const src = element.src;
    const fullscreenDiv = document.createElement('div');
    fullscreenDiv.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.9);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    `;
    
    const img = document.createElement('img');
    img.src = src;
    img.style.cssText = `
        max-width: 90%;
        max-height: 90%;
        object-fit: contain;
    `;
    
    fullscreenDiv.appendChild(img);
    document.body.appendChild(fullscreenDiv);
    
    fullscreenDiv.onclick = () => {
        document.body.removeChild(fullscreenDiv);
    };
}