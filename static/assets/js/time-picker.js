// Custom Time Picker JavaScript with Professional Styling for Django Forms
(function() {
    // Add professional CSS styles for the time picker
    const styles = `
        <style id="time-picker-styles">
            /* Professional Time Picker Styles */
            .professional-time-select {
                width: 100%;
                padding: 12px 16px;
                border: 2px solid #e1e5e9;
                border-radius: 8px;
                font-size: 16px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background-color: #ffffff;
                background-image: url("data:image/svg+xml;charset=UTF-8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23666666' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='10'></circle><polyline points='12,6 12,12 16,14'></polyline></svg>");
                background-repeat: no-repeat;
                background-position: right 12px center;
                background-size: 20px;
                padding-right: 45px;
                color: #2d3748;
                transition: all 0.3s ease;
                cursor: pointer;
                appearance: none;
                -webkit-appearance: none;
                -moz-appearance: none;
            }

            .professional-time-select:hover {
                border-color: #3182ce;
                box-shadow: 0 0 0 3px rgba(49, 130, 206, 0.1);
            }

            .professional-time-select:focus {
                outline: none;
                border-color: #3182ce;
                box-shadow: 0 0 0 3px rgba(49, 130, 206, 0.2);
                background-color: #f7fafc;
            }

            .professional-time-select:invalid {
                border-color: #e53e3e;
            }

            .professional-time-select:invalid:focus {
                border-color: #e53e3e;
                box-shadow: 0 0 0 3px rgba(229, 62, 62, 0.2);
            }

            /* Option styling */
            .professional-time-select option {
                padding: 10px 16px;
                font-size: 16px;
                color: #2d3748;
                background-color: #ffffff;
            }

            .professional-time-select option:hover {
                background-color: #edf2f7;
            }

            .professional-time-select option:disabled {
                color: #a0aec0;
                background-color: #f7fafc;
            }

            /* Custom dropdown arrow for better cross-browser compatibility */
            .time-select-wrapper {
                position: relative;
                display: inline-block;
                width: 100%;
            }

            .time-select-wrapper::after {
                content: '';
                position: absolute;
                top: 50%;
                right: 16px;
                transform: translateY(-50%);
                width: 0;
                height: 0;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #718096;
                pointer-events: none;
                z-index: 1;
            }

            .professional-time-select:focus + .time-select-wrapper::after {
                border-top-color: #3182ce;
            }

            /* Loading state */
            .professional-time-select.loading {
                background-image: url("data:image/svg+xml;charset=UTF-8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23666666' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='3'></circle><path d='M12 1v6m0 6v6m11-7h-6m-6 0H1'></path></svg>");
                animation: spin 1s linear infinite;
            }

            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }

            /* Dark mode support */
            @media (prefers-color-scheme: dark) {
                .professional-time-select {
                    background-color: #2d3748;
                    border-color: #4a5568;
                    color: #e2e8f0;
                }

                .professional-time-select:hover {
                    border-color: #63b3ed;
                    box-shadow: 0 0 0 3px rgba(99, 179, 237, 0.1);
                }

                .professional-time-select:focus {
                    border-color: #63b3ed;
                    box-shadow: 0 0 0 3px rgba(99, 179, 237, 0.2);
                    background-color: #1a202c;
                }

                .professional-time-select option {
                    background-color: #2d3748;
                    color: #e2e8f0;
                }
            }

            /* Responsive design */
            @media (max-width: 768px) {
                .professional-time-select {
                    font-size: 16px; /* Prevents zoom on iOS */
                    padding: 14px 16px;
                }
            }
        </style>
    `;

    // Insert styles into the document head
    document.head.insertAdjacentHTML('beforeend', styles);

    // Define your specific time intervals
    const timeIntervals = [
        '8:00 AM',
        '8:30 AM', 
        '9:00 AM',
        '9:30 AM',
        '10:00 AM',
        '10:30 AM',
        '11:00 AM',
        '12:00 PM',
        '1:00 PM',
        '2:00 PM',
        '2:30 PM',
        '3:00 PM',
        '4:00 PM',
        '4:30 PM',
        '5:30 PM',
        '6:00 PM',
        '6:30 PM',
        '7:00 PM',
        '8:00 PM',
        '9:00 PM',
        '9:30 PM'
    ];

    // Function to convert 12-hour format to 24-hour format for form submission
    function convertTo24Hour(time12h) {
        const [time, modifier] = time12h.split(' ');
        let [hours, minutes] = time.split(':');
        
        if (hours === '12') {
            hours = '00';
        }
        
        if (modifier === 'PM') {
            hours = parseInt(hours, 10) + 12;
        }
        
        return `${hours.toString().padStart(2, '0')}:${minutes}`;
    }

    // Function to create professional wrapper
    function createSelectWrapper(select) {
        const wrapper = document.createElement('div');
        wrapper.className = 'time-select-wrapper';
        return wrapper;
    }

    // Function to replace time input with professional select dropdown
    function replaceTimeInput(inputId) {
        const originalInput = document.getElementById(inputId);
        if (!originalInput) return;

        // Create select element
        const select = document.createElement('select');
        select.id = inputId;
        select.name = originalInput.name;
        select.className = 'professional-time-select';
        select.required = originalInput.required;

        // Add loading state temporarily
        select.classList.add('loading');

        // Add default option
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Select departure time...';
        defaultOption.disabled = true;
        defaultOption.selected = true;
        select.appendChild(defaultOption);

        // Add time interval options
        timeIntervals.forEach((time, index) => {
            const option = document.createElement('option');
            option.value = convertTo24Hour(time); // Store as 24-hour for Django
            option.textContent = time; // Display as 12-hour
            
            // Add some visual grouping for better UX
            if (time === '12:00 PM') {
                option.style.borderTop = '1px solid #e2e8f0';
                option.style.marginTop = '2px';
            }
            
            select.appendChild(option);
        });

        // Create wrapper for better styling control
        const wrapper = createSelectWrapper(select);
        
        // Replace the original input with wrapped select
        originalInput.parentNode.replaceChild(select, originalInput);
        
        // Remove loading state after a short delay
        setTimeout(() => {
            select.classList.remove('loading');
        }, 300);

        // Add change event for better UX
        select.addEventListener('change', function() {
            if (this.value) {
                this.style.borderColor = '#38a169';
                this.style.boxShadow = '0 0 0 3px rgba(56, 161, 105, 0.1)';
                
                // Reset after 1 second
                setTimeout(() => {
                    this.style.borderColor = '';
                    this.style.boxShadow = '';
                }, 1000);
            }
        });

        // Customize placeholder text based on field
        if (inputId === 'return_time') {
            defaultOption.textContent = 'Select return time...';
        }
    }

    // Function to initialize time pickers
    function initializeTimePickers() {
        // Replace departure time input
        replaceTimeInput('departure_time');
        
        // Replace return time input
        replaceTimeInput('return_time');
    }

    // Initialize when DOM is loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeTimePickers);
    } else {
        initializeTimePickers();
    }

    // Handle trip type changes to show/hide return fields
    document.addEventListener('DOMContentLoaded', function() {
        const tripTypeInputs = document.querySelectorAll('input[name="trip_type"]');
        tripTypeInputs.forEach(input => {
            input.addEventListener('change', function() {
                const returnFields = document.getElementById('return_fields');
                const returnDate = document.getElementById('return_date');
                const returnTime = document.getElementById('return_time');
                
                if (this.value === 'round_trip') {
                    returnFields.style.display = 'flex';
                    if (returnDate) returnDate.required = true;
                    if (returnTime) returnTime.required = true;
                } else {
                    returnFields.style.display = 'none';
                    if (returnDate) {
                        returnDate.required = false;
                        returnDate.value = '';
                    }
                    if (returnTime) {
                        returnTime.required = false;
                        returnTime.value = '';
                    }
                }
            });
        });
    });

})();