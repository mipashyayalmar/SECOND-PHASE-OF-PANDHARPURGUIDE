// Open full-screen image modal
function openFullScreen(src) {
    const modal = document.getElementById("imageModal");
    const fullImage = document.getElementById("fullImage");

    // Prevent scrolling on body
    document.body.style.overflow = 'hidden';

    // Set the source of the modal image to the clicked image
    fullImage.src = src;

    // Display the modal with fade-in animation
    modal.style.display = "block";
    modal.classList.add('show');
}

// Close full-screen image modal
function closeFullScreen() {
    const modal = document.getElementById("imageModal");

    // Restore scrolling
    document.body.style.overflow = 'auto';

    // Remove show class and hide modal
    modal.classList.remove('show');
    modal.style.display = "none";
}

// Event listener for closing modal on Escape key press
document.addEventListener('keydown', function (event) {
    if (event.key === "Escape") {
        closeFullScreen();
    }
});

// Event listener for closing modal when clicking outside the image
document.getElementById("imageModal").addEventListener('click', function (event) {
    if (event.target === this) {
        closeFullScreen();
    }
});

// Update header and sub-header after a delay
document.addEventListener('DOMContentLoaded', function () {
    const header = document.querySelector('.header');
    const subHeader = document.querySelector('.sub-header');

    setTimeout(() => {
        header.textContent = '{{ room.hotel.name }}{% if room.heading is not None %}{{ room.heading|upper }}{% endif %}';
        subHeader.textContent = 'WE PROVIDE PICKUP AND DROP SERVICE WITH GUIDE';
    }, 4000); // Change text after 4 seconds
});

// Change the main image source
function changeImage(src) {
    document.getElementById('mainImage').src = src;
}

// Highlight past and current bookings in the table
document.addEventListener('DOMContentLoaded', function () {
    const table = document.getElementById('bookingsTable');
    if (table) {
        const rows = table.getElementsByTagName('tbody')[0].rows;
        const today = new Date(); // Today's date

        Array.from(rows).forEach(row => {
            const checkInDate = new Date(row.cells[2].textContent.trim()); // Check-in date
            const checkOutDate = new Date(row.cells[3].textContent.trim()); // Check-out date

            // Add appropriate class based on date comparison
            if (checkOutDate < today) {
                row.classList.add('passed-booking'); // Red color for past bookings
            } else {
                row.classList.add('current-booking'); // Green color for current bookings
            }
        });
    }
});
