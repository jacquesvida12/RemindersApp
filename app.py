import os
import pyodbc
from dotenv import load_dotenv
from datetime import datetime, timedelta
from flask import (Flask, request, render_template, redirect, url_for, 
                   session, g,  flash, get_flashed_messages, Response)
from dateutil.relativedelta import relativedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import csv
import io

# Load environment variables from files
load_dotenv('sqlcon.env')
load_dotenv('app-sec.env')

# Initialize the Flask application
app = Flask(__name__)

# Set the secret key for session management
app.secret_key = os.getenv('SECRET')

# Access the database connection string from the environment
connection_string = os.getenv('CONNECTION_STRING')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'csv'} # Add 'csv' to allowed extensions
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1 MB max file size for security

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Helper Functions ---
def login_required(view):
    """Decorator to protect routes from unauthenticated users."""
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

@app.before_request
def load_logged_in_user():
    """Loads the user object from the session before each request."""
    user_id = session.get('user_id')
    g.user = None
    if user_id is not None:
        try:
            cnxn = pyodbc.connect(connection_string)
            cursor = cnxn.cursor()
            # Correct the SQL query to select all necessary user attributes
            cursor.execute('SELECT Id, Username, ProfilePictureUrl FROM dbo.Users WHERE Id = ?', (user_id,))
            g.user = cursor.fetchone()
            cursor.close()
            cnxn.close()
        except pyodbc.Error as ex:
            print(f"Database error in before_request: {ex}")
            g.user = None

# --- User Authentication Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = generate_password_hash(password)
        default_avatar = '/static/images/default_avatar.png' # Add a default image to your static folder

        try:
            cnxn = pyodbc.connect(connection_string)
            cursor = cnxn.cursor()
            sql_statement = 'INSERT INTO dbo.Users (Username, PasswordHash, ProfilePictureUrl) VALUES (?,?,?)'
            cursor.execute(sql_statement, (username, password_hash, default_avatar))
            cnxn.commit()
            # ...
            return redirect(url_for('login'))
        except pyodbc.Error as ex:
            return f"Database Error: {ex}", 500
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            cnxn = pyodbc.connect(connection_string)
            cursor = cnxn.cursor()
            sql_query = 'SELECT Id, PasswordHash, Username FROM dbo.Users WHERE Username = ?'
            cursor.execute(sql_query, (username,))
            user = cursor.fetchone()
            cursor.close()
            cnxn.close()
            if user and check_password_hash(user.PasswordHash, password):
                session['user_id'] = user.Id
                flash(f"Welcome back, {user.Username}!", 'success')
                return redirect(url_for('home'))
            else:
                flash("Invalid username or password.", 'error')
                return "Invalid username or password"
        except pyodbc.Error as ex:
            return f"Database Error: {ex}", 500
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logs out the user."""
    session.clear()
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Check if a file was uploaded
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        file = request.files['file']
        # If user does not select a file, the browser submits an empty part
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # Update the user's avatar URL in the database
            user_id = g.user.Id
            new_avatar_url = f'/static/uploads/{filename}'
            try:
                cnxn = pyodbc.connect(connection_string)
                cursor = cnxn.cursor()
                sql_update = 'UPDATE dbo.Users SET ProfilePictureUrl = ? WHERE Id = ?'
                cursor.execute(sql_update, (new_avatar_url, user_id))
                cnxn.commit()
                cursor.close()
                cnxn.close()
                flash('Avatar updated successfully!', 'success')
            except pyodbc.Error as ex:
                flash(f"Database Error: {ex}", 'error')
            return redirect(url_for('profile'))
    return render_template('profile.html', user=g.user)

# --- Task Management Routes (Protected) ---
@app.route('/')
@login_required
def home():
    """Renders the homepage."""
    return render_template('home.html')

@app.route('/create')
@login_required
def create_task_form():
    """Renders the form to create a new task with a list of recurring patterns."""
    patterns = []
    try:
        cnxn = pyodbc.connect(connection_string)
        cursor = cnxn.cursor()
        sql_query = 'SELECT Id, RecurringType, SeparationCount FROM dbo.RecurringPatterns'
        cursor.execute(sql_query)
        patterns = cursor.fetchall()
        cursor.close()
        cnxn.close()
    except pyodbc.Error as ex:
        return f"Database Error: {ex}", 500
    return render_template('create_task.html', patterns=patterns)

@app.route('/create_task', methods=['POST'])
@login_required
def create_task():
    """Creates a new task and, if it's recurring, creates the next occurrences."""
    try:
        task_title = request.form['title']
        due_date_str = request.form['due_date']
        recurring_pattern_id = request.form.get('recurring_pattern_id')
        user_id = g.user.Id
        due_date_obj = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        
        cnxn = pyodbc.connect(connection_string)
        cursor = cnxn.cursor()
        sql_statement = 'INSERT INTO dbo.Tasks (Title, DueDate, IsCompleted, RecurringPatternId, UserId) VALUES (?,?,?,?,?)'
        cursor.execute(sql_statement, (task_title, due_date_obj, False, recurring_pattern_id or None, user_id))

        if recurring_pattern_id:
            cursor.execute('SELECT RecurringType, SeparationCount FROM dbo.RecurringPatterns WHERE Id = ?', (recurring_pattern_id,))
            pattern = cursor.fetchone()
            if pattern:
                recurring_type = pattern.RecurringType
                separation_count = int(pattern.SeparationCount)
                current_due_date = due_date_obj
                for i in range(1, 15):
                    if recurring_type == 'Daily':
                        current_due_date += timedelta(days=separation_count)
                    elif recurring_type == 'Weekly':
                        current_due_date += timedelta(weeks=separation_count)
                    elif recurring_type == 'Monthly':
                        current_due_date += relativedelta(months=separation_count)
                    cursor.execute(sql_statement, (task_title, current_due_date, False, recurring_pattern_id, user_id))

        cnxn.commit()
        cursor.close()
        cnxn.close()
        flash('Task created successfully!', 'success')
        return redirect(url_for('get_tasks'))
    except pyodbc.Error as ex:
        return f"Database Error: {ex}", 500

@app.route('/tasks')
@login_required
def get_tasks():
    tasks = []
    # Get filter criteria from URL query parameters
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'active') 
    start_date_filter = request.args.get('start_date', '')
    end_date_filter = request.args.get('end_date', '')

    try:
        cnxn = pyodbc.connect(connection_string)
        cursor = cnxn.cursor()

        # Start building the dynamic SQL query and parameters
        sql_query = 'SELECT Id, Title, DueDate, IsCompleted, RecurringPatternId FROM dbo.Tasks WHERE UserId = ?'
        params = [g.user.Id]

        # Add search filter for task title
        if search_query:
            sql_query += ' AND Title LIKE ?'
            params.append(f'%{search_query}%')
        
        # Add filter for completion status
        if status_filter == 'active':
            sql_query += ' AND IsCompleted = 0'
        elif status_filter == 'completed':
            sql_query += ' AND IsCompleted = 1'

        # Add filter for date range
        if start_date_filter:
            sql_query += ' AND DueDate >= ?'
            params.append(start_date_filter)
        
        if end_date_filter:
            # To include all tasks on the end date, we check for dates less than the next day
            end_date_obj = datetime.strptime(end_date_filter, '%Y-%m-%d') + timedelta(days=1)
            sql_query += ' AND DueDate < ?'
            params.append(end_date_obj.strftime('%Y-%m-%d'))
            
        sql_query += ' ORDER BY DueDate ASC' # Order results by due date

        cursor.execute(sql_query, tuple(params))
        tasks = cursor.fetchall()

        cursor.close()
        cnxn.close()
    except (pyodbc.Error, ValueError) as ex:
        flash(f"Database or input error: {ex}", 'error')

    # Pass the filter values back to the template
    return render_template('tasks.html', 
                           tasks=tasks, 
                           search_query=search_query,
                           status_filter=status_filter,
                           start_date_filter=start_date_filter,
                           end_date_filter=end_date_filter)


@app.route('/update_task', methods=['POST'])
@login_required
def update_task():
    """Updates an existing task."""
    try:
        task_id = request.form['id']
        new_title = request.form['title']
        new_due_date_str = request.form['due_date']
        new_is_completed = 'is_completed' in request.form
        new_due_date_obj = datetime.strptime(new_due_date_str, '%Y-%m-%dT%H:%M')
        sql_new_due_date = new_due_date_obj.strftime('%Y-%m-%d %H:%M:%S')

        cnxn = pyodbc.connect(connection_string)
        cursor = cnxn.cursor()
        sql_update = 'UPDATE dbo.Tasks SET Title=?, DueDate=?, IsCompleted=? WHERE Id=? AND UserId=?'
        cursor.execute(sql_update, (new_title, sql_new_due_date, new_is_completed, task_id, g.user.Id))
        cnxn.commit()
        cursor.close()
        cnxn.close()
        flash('Task updated successfully!', 'success')
        return redirect(url_for('get_tasks'))
    except pyodbc.Error as ex:
        return f"Database Error: {ex}", 500

@app.route('/delete_task', methods=['POST'])
@login_required
def delete_task():
    """Deletes a task."""
    try:
        task_id = request.form['id']
        cnxn = pyodbc.connect(connection_string)
        cursor = cnxn.cursor()
        sql_delete = 'DELETE FROM dbo.Tasks WHERE Id =? AND UserId=?'
        cursor.execute(sql_delete, (task_id, g.user.Id))
        cnxn.commit()
        cursor.close()
        cnxn.close()
        flash('Task deleted successfully!', 'success')
        return redirect(url_for('get_tasks'))
    except pyodbc.Error as ex:
        return f"Database Error: {ex}", 500

@app.route('/recurring_patterns')
@login_required
def get_recurring_patterns():
    """Fetches and displays all recurring patterns from the database."""
    patterns = []
    try:
        cnxn = pyodbc.connect(connection_string)
        cursor = cnxn.cursor()
        sql_query = 'SELECT Id, RecurringType, SeparationCount, DayOfWeek, DayOfMonth, StartDate FROM dbo.RecurringPatterns'
        cursor.execute(sql_query)
        patterns = cursor.fetchall()
        cursor.close()
        cnxn.close()
    except pyodbc.Error as ex:
        print(f"Database Error: {ex}")
        return f"A database error occurred.", 500
    return render_template('patterns.html', patterns=patterns)

@app.route('/create_pattern')
@login_required
def create_pattern_form():
    """Renders the form to create a new recurring pattern."""
    return render_template('create_pattern.html')

@app.route('/create_pattern', methods=['POST'])
@login_required
def create_pattern():
    """Creates a new recurring pattern in the database."""
    try:
        recurring_type = request.form['recurring_type']
        separation_count = request.form['separation_count']
        day_of_week = request.form.get('day_of_week') or None
        day_of_month_str = request.form.get('day_of_month')
        day_of_month = int(day_of_month_str) if day_of_month_str else None
        start_date_str = request.form['start_date']
        start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d')

        cnxn = pyodbc.connect(connection_string)
        cursor = cnxn.cursor()
        sql_statement = '''
            INSERT INTO dbo.RecurringPatterns
            (RecurringType, SeparationCount, DayOfWeek, DayOfMonth, StartDate)
            VALUES (?, ?, ?, ?, ?)
        '''
        cursor.execute(sql_statement, (recurring_type, separation_count, day_of_week, day_of_month, start_date_obj))
        cnxn.commit()
        cursor.close()
        cnxn.close()
        flash('Recurring pattern created successfully!', 'success')
        return redirect(url_for('get_recurring_patterns'))
    except (pyodbc.Error, ValueError) as ex:
        return f"Error: {ex}", 500
        
@app.route('/delete_pattern/<int:pattern_id>', methods=['POST'])
@login_required
def delete_pattern(pattern_id):
    """Deletes a recurring pattern and its associated future tasks."""
    try:
        cnxn = pyodbc.connect(connection_string)
        cursor = cnxn.cursor()

        # Step 1: Delete associated future, uncompleted tasks for the user
        sql_delete_tasks = """
            DELETE FROM dbo.Tasks 
            WHERE RecurringPatternId = ? 
            AND UserId = ? 
            AND IsCompleted = 0 
            AND DueDate > GETDATE()
        """
        cursor.execute(sql_delete_tasks, (pattern_id, g.user.Id))

        # Step 2: Delete the recurring pattern itself
        sql_delete_pattern = 'DELETE FROM dbo.RecurringPatterns WHERE Id = ?'
        cursor.execute(sql_delete_pattern, (pattern_id,))
        
        cnxn.commit()
        cursor.close()
        cnxn.close()
        
        flash('Recurring pattern and its future tasks have been deleted.', 'success')
    except pyodbc.Error as ex:
        flash(f'Database error: {ex}', 'error')

    return redirect(url_for('get_recurring_patterns'))
    
@app.route('/export')
@login_required
def export_tasks():
    """Exports the currently filtered tasks to a CSV file."""
    tasks = []
    # This logic is duplicated from get_tasks to ensure the export matches the view
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'active')
    start_date_filter = request.args.get('start_date', '')
    end_date_filter = request.args.get('end_date', '')

    try:
        cnxn = pyodbc.connect(connection_string)
        cursor = cnxn.cursor()
        sql_query = 'SELECT Title, DueDate, IsCompleted FROM dbo.Tasks WHERE UserId = ?'
        params = [g.user.Id]

        if search_query:
            sql_query += ' AND Title LIKE ?'
            params.append(f'%{search_query}%')
        if status_filter == 'active':
            sql_query += ' AND IsCompleted = 0'
        elif status_filter == 'completed':
            sql_query += ' AND IsCompleted = 1'
        if start_date_filter:
            sql_query += ' AND DueDate >= ?'
            params.append(start_date_filter)
        if end_date_filter:
            end_date_obj = datetime.strptime(end_date_filter, '%Y-%m-%d') + timedelta(days=1)
            sql_query += ' AND DueDate < ?'
            params.append(end_date_obj.strftime('%Y-%m-%d'))
        
        sql_query += ' ORDER BY DueDate ASC'
        cursor.execute(sql_query, tuple(params))
        tasks = cursor.fetchall()
        cursor.close()
        cnxn.close()

        # Create a CSV in memory
        si = io.StringIO()
        cw = csv.writer(si)
        # Write headers
        cw.writerow(['Title', 'DueDate', 'IsCompleted'])
        # Write task data
        cw.writerows(tasks)
        
        output = si.getvalue()
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=tasks.csv"})

    except (pyodbc.Error, ValueError) as ex:
        flash(f"Error exporting tasks: {ex}", 'error')
        return redirect(url_for('get_tasks'))

@app.route('/import', methods=['POST'])
@login_required
def import_tasks():
    """Imports tasks from an uploaded CSV file."""
    # 1. --- Security Check ---
    if 'file' not in request.files:
        flash('No file part in the request.', 'error')
        return redirect(url_for('get_tasks'))
    
    file = request.files['file']

    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('get_tasks'))

    if not file or file.mimetype != 'text/csv':
        flash('Invalid file type. Please upload a CSV file.', 'error')
        return redirect(url_for('get_tasks'))

    # 2. --- Data Processing ---
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        reader = csv.reader(stream)
        next(reader, None)  # Skip header row
        
        tasks_to_add = []
        for row in reader:
            # 3. --- Data Validation ---
            if len(row) != 2:
                flash(f'Skipping invalid row: {",".join(row)}', 'error')
                continue
            title, due_date_str = row
            try:
                # Validate and format date
                due_date_obj = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M:%S')
                tasks_to_add.append((title, due_date_obj, False, None, g.user.Id))
            except ValueError:
                flash(f'Skipping row with invalid date format: {",".join(row)}', 'error')
                continue
        
        # 4. --- Database Insertion ---
        if tasks_to_add:
            cnxn = pyodbc.connect(connection_string)
            cursor = cnxn.cursor()
            sql = 'INSERT INTO dbo.Tasks (Title, DueDate, IsCompleted, RecurringPatternId, UserId) VALUES (?, ?, ?, ?, ?)'
            cursor.executemany(sql, tasks_to_add)
            cnxn.commit()
            cursor.close()
            cnxn.close()
            flash(f'Successfully imported {len(tasks_to_add)} tasks!', 'success')
        else:
            flash('No valid tasks to import.', 'warning')

    except Exception as e:
        flash(f'An error occurred during import: {e}', 'error')

    return redirect(url_for('get_tasks'))

if __name__ == '__main__':
    app.run(debug=True)