document.addEventListener('DOMContentLoaded', () => {

    // --- 1. Profile Dropdown Logic ---
    const profileToggle = document.getElementById('profile-toggle');
    const profileMenu = document.getElementById('profile-menu');

    if (profileToggle && profileMenu) {
        profileToggle.addEventListener('click', (event) => {
            event.preventDefault(); // Prevent link navigation
            profileMenu.classList.toggle('show');
        });

        // Close the dropdown if clicking outside of it
        document.addEventListener('click', (event) => {
            if (!profileToggle.contains(event.target) && !profileMenu.contains(event.target)) {
                profileMenu.classList.remove('show');
            }
        });
    }


    // --- 2. Asynchronous Task Completion (AJAX/Fetch) ---
    document.querySelectorAll('.completion-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const taskId = this.dataset.taskId;
            const taskRow = this.closest('tr');

            fetch(`/api/toggle_task/${taskId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    taskRow.classList.toggle('completed', this.checked);
                } else {
                    // Revert the checkbox on failure
                    this.checked = !this.checked;
                    alert('Error: ' + (data.message || 'Could not update task.'));
                }
            })
            .catch(error => {
                console.error('Fetch error:', error);
                this.checked = !this.checked; // Revert on network error
                alert('An error occurred. Please try again.');
            });
        });
    });


    // --- 3. Client-Side Form Validation for Recurring Patterns ---
    const recurringTypeSelect = document.getElementById('recurring_type');
    const dayOfWeekField = document.getElementById('day_of_week_field');
    const dayOfMonthField = document.getElementById('day_of_month_field');

    function togglePatternFields() {
        if (!recurringTypeSelect) return; // Guard clause

        const selectedType = recurringTypeSelect.value;
        
        // Hide both fields by default
        if (dayOfWeekField) dayOfWeekField.style.display = 'none';
        if (dayOfMonthField) dayOfMonthField.style.display = 'none';

        // Show the relevant field based on selection
        if (selectedType === 'Weekly' && dayOfWeekField) {
            dayOfWeekField.style.display = 'block';
        } else if (selectedType === 'Monthly' && dayOfMonthField) {
            dayOfMonthField.style.display = 'block';
        }
    }

    // Add event listener and run on page load
    if (recurringTypeSelect) {
        recurringTypeSelect.addEventListener('change', togglePatternFields);
        togglePatternFields(); // Initial check
    }

});


document.addEventListener('DOMContentLoaded', () => {

    // --- 1. Profile Dropdown Logic ---
    const profileToggle = document.getElementById('profile-menu-toggle');
    const profileMenu = document.getElementById('profile-menu');

    if (profileToggle && profileMenu) {
        profileToggle.addEventListener('click', (event) => {
            event.preventDefault(); // Prevent the link from navigating
            profileMenu.classList.toggle('show');
        });

        // Close the dropdown if clicking outside of it
        document.addEventListener('click', (event) => {
            if (!profileToggle.contains(event.target) && !profileMenu.contains(event.target)) {
                profileMenu.classList.remove('show');
            }
        });
    }

    // --- 2. Asynchronous Task Completion (AJAX/Fetch) ---
    document.querySelectorAll('.completion-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const taskId = this.dataset.taskId;
            const taskRow = this.closest('tr');

            fetch(`/api/toggle_task/${taskId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    taskRow.classList.toggle('completed', this.checked);
                } else {
                    this.checked = !this.checked; // Revert on failure
                    alert('Error: ' + (data.message || 'Could not update task.'));
                }
            })
            .catch(error => {
                console.error('Fetch error:', error);
                this.checked = !this.checked; // Revert on network error
                alert('An error occurred. Please try again.');
            });
        });
    });

    // --- 3. Client-Side Form Validation for Recurring Patterns ---
    // (This section remains unchanged)
});