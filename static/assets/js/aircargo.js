document.addEventListener('DOMContentLoaded', function() {
    // Initialize modals
    const modals = document.querySelectorAll('.modal');
    M.Modal.init(modals);
    
    // Air Cargo Form Submission
    const cargoForm = document.getElementById('cargo-request-form');
    if (cargoForm) {
        cargoForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const data = {
                request_type: formData.get('request_type'),
                departure: formData.get('departure'),
                destination: formData.get('destination'),
                date: formData.get('date'),
                departure_time: formData.get('departure_time'),
                name: formData.get('name'),
                company: formData.get('company'),
                email: formData.get('email'),
                telephone: formData.get('telephone'),
                cargo_details: formData.get('cargo_details'),
                special_requirements: formData.get('special_requirements')
            };
            
            submitForm('/submit-cargo-request/', data, 'cargo-modal');
        });
    }
    
    // Aircraft Leasing Form Submission
    const leasingForm = document.getElementById('leasing-inquiry-form');
    if (leasingForm) {
        leasingForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const data = {
                leasing_type: formData.get('leasing_type'),
                name: formData.get('name'),
                company: formData.get('company'),
                email: formData.get('email'),
                telephone: formData.get('telephone'),
                requirements: formData.get('requirements'),
                duration: formData.get('duration')
            };
            
            submitForm('/submit-leasing-inquiry/', data, 'leasing-modal');
        });
    }
    
    // Generic form submission function
    function submitForm(url, data, modalId) {
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                M.toast({html: data.message, classes: 'green'});
                const modal = M.Modal.getInstance(document.getElementById(modalId));
                modal.close();
                document.getElementById(modalId.replace('-modal', '-form')).reset();
            } else {
                M.toast({html: data.message, classes: 'red'});
            }
        })
        .catch(error => {
            M.toast({html: 'Error: ' + error, classes: 'red'});
        });
    }
    
    // Helper function to get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});