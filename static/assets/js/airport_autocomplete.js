  // Airport Autocomplete Enhancement
// This script converts existing select elements into searchable autocomplete inputs
// while maintaining all original functionality

(function() {
    'use strict';
    
    // Wait for DOM to be fully loaded
    document.addEventListener('DOMContentLoaded', function() {
        initializeAirportAutocomplete();
    });
    
    function initializeAirportAutocomplete() {
        const departureSelect = document.getElementById('departure_airport');
        const arrivalSelect = document.getElementById('arrival_airport');
        
        if (departureSelect) {
            createAutocomplete(departureSelect, 'departure');
        }
        
        if (arrivalSelect) {
            createAutocomplete(arrivalSelect, 'arrival');
        }
    }
    
    function createAutocomplete(originalSelect, type) {
        // Extract all airport options
        const airports = [];
        const options = originalSelect.querySelectorAll('option');
        
        options.forEach(option => {
            if (option.value) { // Skip the default "Select..." option
                airports.push({
                    value: option.value,
                    text: option.textContent.trim(),
                    iata: option.getAttribute('data-iata') || '',
                    city: option.getAttribute('data-city') || '',
                    country: option.getAttribute('data-country') || ''
                });
            }
        });
        
        // Create wrapper div
        const wrapper = document.createElement('div');
        wrapper.className = 'autocomplete-wrapper';
        wrapper.style.position = 'relative';
        wrapper.style.width = '100%';
        
        // Create input element
        const input = document.createElement('input');
        input.type = 'text';
        input.className = originalSelect.className;
        input.placeholder = type === 'departure' ? 'Type to search departure airport...' : 'Type to search destination airport...';
        input.style.width = '100%';
        input.style.padding = originalSelect.style.padding || '8px 12px';
        input.style.border = originalSelect.style.border || '1px solid #ddd';
        input.style.borderRadius = originalSelect.style.borderRadius || '4px';
        input.style.fontSize = originalSelect.style.fontSize || '14px';
        
        // Create dropdown container
        const dropdown = document.createElement('div');
        dropdown.className = 'autocomplete-dropdown';
        dropdown.style.cssText = `
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: white;
            border: 1px solid #ddd;
            border-top: none;
            border-radius: 0 0 4px 4px;
            max-height: 200px;
            overflow-y: auto;
            z-index: 1000;
            display: none;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        `;
        
        // Hide original select but keep it functional
        originalSelect.style.display = 'none';
        
        // Insert wrapper after original select
        originalSelect.parentNode.insertBefore(wrapper, originalSelect.nextSibling);
        wrapper.appendChild(input);
        wrapper.appendChild(dropdown);
        
        let selectedIndex = -1;
        let filteredAirports = [];
        
        // Input event handler
        input.addEventListener('input', function() {
            const query = this.value.toLowerCase().trim();
            
            if (query.length < 2) {
                hideDropdown();
                clearSelection();
                return;
            }
            
            // Filter airports based on query
            filteredAirports = airports.filter(airport => {
                return airport.text.toLowerCase().includes(query) ||
                       airport.city.toLowerCase().includes(query) ||
                       airport.country.toLowerCase().includes(query) ||
                       airport.value.toLowerCase().includes(query) ||
                       airport.iata.toLowerCase().includes(query);
            });
            
            showDropdown(filteredAirports);
            selectedIndex = -1;
        });
        
        // Keyboard navigation
        input.addEventListener('keydown', function(e) {
            if (!dropdown.style.display || dropdown.style.display === 'none') {
                return;
            }
            
            const items = dropdown.querySelectorAll('.autocomplete-item');
            
            switch(e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
                    updateSelection(items);
                    break;
                    
                case 'ArrowUp':
                    e.preventDefault();
                    selectedIndex = Math.max(selectedIndex - 1, -1);
                    updateSelection(items);
                    break;
                    
                case 'Enter':
                    e.preventDefault();
                    if (selectedIndex >= 0 && items[selectedIndex]) {
                        selectAirport(filteredAirports[selectedIndex]);
                    }
                    break;
                    
                case 'Escape':
                    hideDropdown();
                    break;
            }
        });
        
        // Click outside to close
        document.addEventListener('click', function(e) {
            if (!wrapper.contains(e.target)) {
                hideDropdown();
            }
        });
        
        function showDropdown(airports) {
            dropdown.innerHTML = '';
            
            if (airports.length === 0) {
                const noResults = document.createElement('div');
                noResults.className = 'autocomplete-item';
                noResults.style.cssText = `
                    padding: 12px;
                    color: #666;
                    font-style: italic;
                `;
                noResults.textContent = 'No airports found';
                dropdown.appendChild(noResults);
            } else {
                airports.forEach((airport, index) => {
                    const item = document.createElement('div');
                    item.className = 'autocomplete-item';
                    item.style.cssText = `
                        padding: 12px;
                        cursor: pointer;
                        border-bottom: 1px solid #f0f0f0;
                        transition: background-color 0.2s;
                    `;
                    
                    // Highlight matching text
                    const query = input.value.toLowerCase();
                    let displayText = airport.text;
                    const lowerText = displayText.toLowerCase();
                    const matchIndex = lowerText.indexOf(query);
                    
                    if (matchIndex !== -1) {
                        displayText = displayText.substring(0, matchIndex) +
                                    '<strong>' + displayText.substring(matchIndex, matchIndex + query.length) + '</strong>' +
                                    displayText.substring(matchIndex + query.length);
                    }
                    
                    item.innerHTML = displayText;
                    
                    // Hover effects
                    item.addEventListener('mouseenter', function() {
                        this.style.backgroundColor = '#f8f9fa';
                        selectedIndex = index;
                        updateSelection(dropdown.querySelectorAll('.autocomplete-item'));
                    });
                    
                    item.addEventListener('mouseleave', function() {
                        this.style.backgroundColor = '';
                    });
                    
                    // Click to select
                    item.addEventListener('click', function() {
                        selectAirport(airport);
                    });
                    
                    dropdown.appendChild(item);
                });
            }
            
            dropdown.style.display = 'block';
        }
        
        function updateSelection(items) {
            items.forEach((item, index) => {
                if (index === selectedIndex) {
                    item.style.backgroundColor = '#007bff';
                    item.style.color = 'white';
                } else {
                    item.style.backgroundColor = '';
                    item.style.color = '';
                }
            });
        }
        
        function selectAirport(airport) {
            input.value = airport.text;
            originalSelect.value = airport.value;
            
            // Trigger change event on original select to maintain functionality
            const changeEvent = new Event('change', { bubbles: true });
            originalSelect.dispatchEvent(changeEvent);
            
            hideDropdown();
        }
        
        function clearSelection() {
            originalSelect.value = '';
            const changeEvent = new Event('change', { bubbles: true });
            originalSelect.dispatchEvent(changeEvent);
        }
        
        function hideDropdown() {
            dropdown.style.display = 'none';
            selectedIndex = -1;
        }
        
        // Handle form reset
        const form = originalSelect.closest('form');
        if (form) {
            form.addEventListener('reset', function() {
                setTimeout(() => {
                    input.value = '';
                    hideDropdown();
                }, 0);
            });
        }
        
        // Validation support - only show validation errors when form is actually submitted
        let hasBeenSubmitted = false;
        
        const checkValidity = () => {
            if (hasBeenSubmitted && originalSelect.hasAttribute('required') && !originalSelect.value) {
                input.setCustomValidity('Please select an airport');
                return false;
            } else {
                input.setCustomValidity('');
                return true;
            }
        };
        
        // Only validate after first submit attempt
        if (form) {
            form.addEventListener('submit', function(e) {
                hasBeenSubmitted = true;
                if (!checkValidity()) {
                    e.preventDefault();
                    input.focus();
                }
            });
        }
        
        // Clear validation message when user starts typing or selects
        input.addEventListener('input', () => {
            if (hasBeenSubmitted) {
                checkValidity();
            }
        });
    }
})();