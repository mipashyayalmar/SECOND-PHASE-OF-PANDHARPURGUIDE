
    document.addEventListener('DOMContentLoaded', function() {
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const checkInInput = document.getElementById('check-in');
        const checkInDisplay = document.getElementById('check-in-display');
        const checkOutInput = document.getElementById('check-out');
        const checkOutDisplay = document.getElementById('check-out-display');
        const capacityInput = document.getElementById('capacity');
        const minPriceInput = document.getElementById('min_price');
        const maxPriceInput = document.getElementById('max_price');
        const minRange = document.getElementById('min_range');
        const maxRange = document.getElementById('max_range');

        checkInDisplay.value = '{{ formatted_check_in|default:"" }}';
        checkOutDisplay.value = '{{ formatted_check_out|default:"" }}';
        minRange.value = '{{ min_price|default:"0" }}';
        maxRange.value = '{{ max_price|default:"10000" }}';

        function formatDateToLocalYYYYMMDD(date) {
            return date.getFullYear() + '-' +
                   String(date.getMonth() + 1).padStart(2, '0') + '-' +
                   String(date.getDate()).padStart(2, '0');
        }

        const checkInPicker = flatpickr('#check-in-display', {
            minDate: today,
            dateFormat: 'd F Y',
            defaultDate: checkInInput.value ? new Date(checkInInput.value) : null,
            onChange: function(selectedDates) {
                if (selectedDates.length > 0) {
                    const selectedDate = selectedDates[0];
                    checkInInput.value = formatDateToLocalYYYYMMDD(selectedDate);
                    updateCheckoutMinDate();
                    showDatePopup();
                    validateDates();
                    debounceSubmit();
                }
            }
        });

        const checkOutPicker = flatpickr('#check-out-display', {
            minDate: checkInInput.value ? new Date(new Date(checkInInput.value).setDate(new Date(checkInInput.value).getDate() + 1)) : new Date(today.setDate(today.getDate() + 1)),
            dateFormat: 'd F Y',
            defaultDate: checkOutInput.value ? new Date(checkOutInput.value) : null,
            onChange: function(selectedDates) {
                if (selectedDates.length > 0) {
                    const selectedDate = selectedDates[0];
                    checkOutInput.value = formatDateToLocalYYYYMMDD(selectedDate);
                    showDatePopup();
                    validateDates();
                    debounceSubmit();
                }
            }
        });

        function updateCheckoutMinDate() {
            if (checkInInput.value) {
                const checkInDate = new Date(checkInInput.value);
                const minCheckOutDate = new Date(checkInDate);
                minCheckOutDate.setDate(checkInDate.getDate() + 1);
                checkOutPicker.set('minDate', minCheckOutDate);

                const currentCheckOut = checkOutInput.value ? new Date(checkOutInput.value) : null;
                if (currentCheckOut && currentCheckOut <= checkInDate) {
                    checkOutInput.value = formatDateToLocalYYYYMMDD(minCheckOutDate);
                    checkOutDisplay.value = minCheckOutDate.toLocaleDateString('en-GB', {
                        day: 'numeric',
                        month: 'long',
                        year: 'numeric'
                    });
                    checkOutPicker.setDate(minCheckOutDate);
                }
            }
        }

        function showDatePopup() {
            Swal.fire({
                title: 'Dates Selected',
                html: `Check-in: ${checkInDisplay.value}<br>Check-out: ${checkOutDisplay.value}`,
                icon: 'info',
                confirmButtonText: 'OK'
            });
        }

        function validateDates() {
            const errorElement = document.getElementById('dateError');
            errorElement.style.display = 'none';
            errorElement.textContent = '';

            const checkInDate = checkInInput.value ? new Date(checkInInput.value) : null;
            if (checkInDate) {
                checkInDate.setHours(0, 0, 0, 0);
                if (checkInDate < today) {
                    errorElement.textContent = 'Check-in date cannot be in the past';
                    errorElement.style.display = 'block';
                    checkInDisplay.focus();
                    return false;
                }
            }

            const checkOutDate = checkOutInput.value ? new Date(checkOutInput.value) : null;
            if (checkOutDate && checkInDate) {
                checkOutDate.setHours(0, 0, 0, 0);
                if (checkOutDate <= checkInDate) {
                    errorElement.textContent = 'Check-out date must be after check-in date';
                    errorElement.style.display = 'block';
                    checkOutDisplay.focus();
                    return false;
                }
            }

            return true;
        }

        const updatePriceRange = () => {
            const minVal = parseInt(minPriceInput.value) || 0;
            const maxVal = parseInt(maxPriceInput.value) || 10000;
            if (minVal > maxVal) {
                maxPriceInput.value = minVal;
                maxRange.value = minVal;
            }
            if (maxVal < minVal) {
                minPriceInput.value = maxVal;
                minRange.value = maxVal;
            }
        };

        minRange.addEventListener('input', () => {
            minPriceInput.value = minRange.value;
            updatePriceRange();
            debounceSubmit();
        });

        maxRange.addEventListener('input', () => {
            maxPriceInput.value = maxRange.value;
            updatePriceRange();
            debounceSubmit();
        });

        minPriceInput.addEventListener('change', () => {
            minRange.value = minPriceInput.value;
            updatePriceRange();
            debounceSubmit();
        });

        maxPriceInput.addEventListener('change', () => {
            maxRange.value = maxPriceInput.value;
            updatePriceRange();
            debounceSubmit();
        });

        capacityInput.addEventListener('change', debounceSubmit);

        const amenityCheckboxes = document.querySelectorAll('.amenity-filter');
        amenityCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                this.value = this.checked ? '1' : '0';
                this.parentElement.classList.add('animate__animated', 'animate__pulse');
                setTimeout(() => {
                    this.parentElement.classList.remove('animate__animated', 'animate__pulse');
                }, 1000);
                Swal.fire({
                    title: 'Filter Applied',
                    text: `Amenity ${this.checked ? 'added' : 'removed'}: ${this.dataset.amenity}`,
                    icon: 'success',
                    timer: 1500,
                    showConfirmButton: false
                });
                debounceSubmit();
            });
        });

        let submitTimeout;
        function debounceSubmit() {
            clearTimeout(submitTimeout);
            submitTimeout = setTimeout(() => {
                if (validateDates()) {
                    document.getElementById('filterForm').submit();
                }
            }, 1000);
        }

        updateCheckoutMinDate();
    });