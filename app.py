from flask import Flask, render_template, request, redirect, url_for,jsonify, flash, session
from flask_mail import Mail, Message
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash
import re
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import check_password_hash
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)
app.secret_key = '1234567'
# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'florenceforwork08@gmail.com'  # Your Gmail address
app.config['MAIL_PASSWORD'] = 'uynm wmzb vrdb czzx'  # Your password or App Password
app.config['MAIL_DEFAULT_SENDER'] = 'florenceforwork08@gmail.com'

mail = Mail(app)

serializer = URLSafeTimedSerializer(app.secret_key)

def get_db_connection():
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),        # The RDS endpoint
        user=os.getenv("DB_USER"),        # The master username
        password=os.getenv("DB_PASSWORD"),# The master password
        database=os.getenv("DB_NAME"),    # The database name
        port=3306                         # Default MySQL port
    )
    return connection

def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def validate_password(password):
    # At least 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special character
    return re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$", password)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        branch_name = request.form['branch']
        username = request.form['user']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        email = request.form['email']

        # Basic validation
        if not branch_name or not username or not password or not email:
            flash('All fields are required!')
            return "All fields are required", 400

        if not validate_email(email):
            return "Invalid email format", 400
        
        if not validate_password(password):
            flash('Password must be at least 8 characters long and include one uppercase, one lowercase letter, one digit, and one special character.')
            return redirect(url_for('signup'))

        if password != confirm_password:
            flash('Passwords do not match.')
            return redirect(url_for('signup'))

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("SELECT id FROM pawnshopaccount WHERE email = %s", (email,))
            existing_email = cursor.fetchone()
            if existing_email:
                flash('Email already exists. Please use a different email.', 'error')
                return redirect(url_for('signup'))

            # Check if the branch already exists
            cursor.execute("SELECT id FROM branch WHERE name = %s", (branch_name,))
            branch = cursor.fetchone()

            if branch:
                branch_id = branch[0]  # Use existing branch_id
            else:
                # Insert new branch and get the newly created branch_id
                cursor.execute("INSERT INTO branch (name) VALUES (%s)", (branch_name,))
                connection.commit()
                branch_id = cursor.lastrowid  # Get the id of the newly created branch

            # Insert into database
            cursor.execute("INSERT INTO pawnshopaccount (username, password, email, branch, branch_id, is_confirmed) VALUES (%s, %s, %s, %s, %s, FALSE)",
               (username, generate_password_hash(password), email, branch_name, branch_id))

            connection.commit()
            flash('Registration successful! Check your email to confirm.', 'success')
       
            token = serializer.dumps(email, salt='email-confirm')
            confirm_link = url_for('confirm_email', token=token, _external=True)

            # Send confirmation email
            msg = Message('Registration Confirmation', recipients=[email])
            msg.body = f'Thank you for registering, {username}! Please confirm your email by clicking this link: {confirm_link}'
            mail.send(msg)
            flash('Registration successful! Check your email to confirm.')
            return redirect(url_for('login'))

        except Error as e:
            print(f"Error during database operation: {e}")
            flash('An error occurred. Please try again.')
            return "Database connection error", 500
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    return render_template('signup.html')

@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = serializer.loads(token, salt='email-confirm', max_age=3600)  # Token expires after 1 hour
    except:
        return "The confirmation link is invalid or has expired."
    # Update the database to set the email as confirmed
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Update the user's confirmation status
        cursor.execute("UPDATE pawnshopaccount SET is_confirmed = TRUE WHERE email = %s", (email,))
        connection.commit()

        flash("Your email has been confirmed!")
        return redirect(url_for('login'))

    except Error as e:
        print(f"Error during database operation: {e}")
        return "Database connection error", 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
@app.route('/login', methods=['GET', 'POST'])
def login():
    cursor = None  # Initialize the cursor variable
    if request.method == 'POST':
        branch = request.form['branch']
        username = request.form['username']
        password = request.form['password']
        full_username = f"{username}"

        print(f"Attempting login for username: {full_username}, Branch: {branch}")

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute("SELECT * FROM pawnshopaccount WHERE username = %s AND branch = %s", (full_username, branch))
            user = cursor.fetchone()

            print(f"Fetched user: {user}")

            if user:
                if user['is_confirmed'] == 1:  # Check as integer
                    if check_password_hash(user['password'], password):  # Verify password
                        session['username'] = full_username
                        session['branch_id'] = user['branch_id']
                        session['branch'] = branch
                        flash('Login successful!', 'success')
                        return redirect(url_for('home'))
                    else:
                        flash('Incorrect password. Please try again.', 'danger')
                else:
                    flash('You must confirm your email before logging in.', 'warning')
            else:
                flash('Username or branch is incorrect. Please try again.', 'danger')

        except Error as e:
            print(f"Error during database operation: {e}")
            flash('Database connection error. Please try again.', 'danger')
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    return render_template('loginform.html')

@app.route('/customerinfo', methods=['GET', 'POST'])
def customerinfo():
    return render_template('customerinfo.html')
@app.route('/')
def home():
   if 'username' not in session:  # Check if user is logged in
        return redirect(url_for('login'))  # Redirect to login page if not logged in
   
   branch =  session.get('branch', '')   # Get branch from query parameters
   return render_template('form.html', branch=branch)  # Render the form if logged in
@app.route('/submit', methods=['GET', 'POST'])
def submit():
    action = request.form.get('action')
    if action =='logout':
      session.pop('username', None)
      return redirect(url_for("login"))
    username = session['username']
    branch = request.form['branch']
    name = request.form['name']
    age = request.form['age']
    loan = request.form['loan']
    birthday = request.form['birthday']
    address = request.form['address']
    occupation = request.form['occupation']
    income_source = request.form['incomeSource']
    purpose_of_transaction = request.form['purpose']
    transaction_date = request.form['firstTransaction']
    amount = request.form['amount']
    status = request.form['customerType']
    discover = request.form['discover']  # Fix typo: 'dicover' to 'discover'

    transaction_date = datetime.strptime(request.form['firstTransaction'], '%Y-%m-%d').strftime('%m/%d/%Y')
    birthday = datetime.strptime(request.form['birthday'], '%Y-%m-%d').strftime('%m/%d/%Y')
    loan = datetime.strptime(request.form['birthday'], '%Y-%m-%d').strftime('%m/%d/%Y')
    # Database connection and insert logic
    connection = get_db_connection()
    cursor = connection.cursor()
    
    if status == 'new customer':
        
        # Insert into Customerinfo table for new customers
        cursor.execute("""INSERT INTO customerinfo 
        (username, branch, name, LoanDate, age, birthday, address, customer_work, source_income, purpose, firsttransaction, amount, status, discover_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
        (username, branch, name, loan, age, birthday, address, occupation, income_source, purpose_of_transaction, transaction_date, amount, status, discover))
        
        # Insert into firsttransaction table
        cursor.execute("""INSERT INTO firsttrasaction 
      (username, branch, name, LoanDate, age, birthday, address, customer_work, source_income, purpose, firsttransaction, amount, status, discover_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
        (username, branch, name, loan, age, birthday, address, occupation, income_source, purpose_of_transaction, transaction_date, amount, status, discover))

    else:
        # Insert into Customerinfo for existing customers (adjust as needed)
        cursor.execute("""INSERT INTO customerinfo 
        (username, branch, name, LoanDate, age, birthday, address, customer_work, source_income, purpose, firsttransaction, amount, status, discover_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
        (username, branch, name, loan, age, birthday, address, occupation, income_source, purpose_of_transaction, transaction_date, amount, status, discover))

    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for('home'))
 # This is the Survey form where Username is display
@app.route('/check_name', methods=['POST'])
def check_name():
    data = request.get_json()
    name = data.get('name')
    branch = session.get('branch')

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Update the query to correctly select and alias the MIN(loanDate)
        cursor.execute("""
            SELECT 
                Age, 
                Birthday, 
                Customer_Work, 
                Source_Income, 
                Address, 
                MIN(loanDate) AS FirstTransaction 
            FROM 
                customerinfo 
            WHERE 
                Name = %s AND branch = %s 
            GROUP BY 
                Age, Birthday, Customer_Work, Source_Income, Address 
            ORDER BY 
                FirstTransaction ASC
        """, (name, branch))

        customer = cursor.fetchone()
        if customer:
            return jsonify({
                'age': customer['Age'],
                'birthday': customer['Birthday'],
                'occupation': customer['Customer_Work'],
                'incomeSource': customer['Source_Income'],
                'address': customer['Address'],
                'firstTransaction': customer['FirstTransaction'],
                'customerType': 'existing'
            })
        else:
            return jsonify({})  # Return an empty JSON if not found
    except mysql.connector.Error as err:
        print("Database error:", err)
        return jsonify({"error": "Database error occurred"}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

#Endd
#Survey form existing name
@app.route('/get_existing_names', methods=['GET'])
def get_existing_names():
   if 'branch' not in session:  # Check if the user is logged in
        return jsonify({"names": []})  # Return an empty list if not logged in
   
   branch = session['branch']  # Get the current user's username
   names = fetch_names_from_database(branch)  # Pass the username
   return jsonify({"names": names})

def fetch_names_from_database(branch):
    names = []
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Modify the query to include a WHERE clause for the username
        cursor.execute("SELECT DISTINCT Name FROM customerinfo WHERE branch = %s", (branch,))
        results = cursor.fetchall()

        for row in results:
            names.append(row[0])  # Assuming Name is the first column
        
    except Error as e:
        print(f"Error fetching names: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return names

#enddd
#FORM.HTML TABLE
@app.route('/get_customer_info', methods=['POST'])
def get_customer_info():
    name = request.json.get('name')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT Name
            FROM customerinfo 
            WHERE Name = %s
        """, (name,))
        customer = cursor.fetchone()
        # Ensure that the result is completely read before closing the cursor
        cursor.fetchall()  # This can prevent the unread result issue
        
        return jsonify(customer) if customer else jsonify({})
    except Exception as e:
        print(f"Error fetching customer info: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        cursor.close()
        conn.close()

#FORM.HTML TABLE

@app.route('/get_customer_transactions', methods=['POST'])
def get_customer_transactions():
    name = request.json.get('name')
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT Branch, LoanDate, Birthday, Purpose
        FROM customerinfo 
        WHERE Name = %s
    """, (name,))
    transactions = cursor.fetchall()
    cursor.close()
    connection.close()
    return jsonify(transactions) if transactions else jsonify({"message": "No transactions found."})

#fORM.HTML END

#fORM.HTML SUGGESTIONSS
@app.route('/get_global_names', methods=['GET'])
def get_global_names():
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT Name FROM customerinfo")
        results = cursor.fetchall()
        names = [row[0] for row in results]
        return jsonify({"names": names})
    except Exception as e:
        print(f"Error fetching global names: {e}")
        return jsonify({"names": []})
    finally:
        cursor.close()
        connection.close()
@app.route('/surveyform')
def surveyform():
    branch = request.args.get('branch', '')
    name = request.args.get('name', '')
    customer_info = {}
    if name:
        customer_info = get_customer_info(name)  # Fetch customer info based on the name

    return render_template('surveyform.html', branch=branch, customer_info=customer_info)
#CUSTOMERINFO SEARCH FUNCTION
def format_date_to_mmddyyyy(date_string):
    # Converts YYYY-MM-DD to MM/DD/YYYY if date_string is not empty
    return datetime.strptime(date_string, "%Y-%m-%d").strftime("%m/%d/%Y") if date_string else None

@app.route('/search-customers', methods=['GET'])
def search_customers():
    search_name = request.args.get('Searchcustomer', '')
    search_date = request.args.get('Searchdate', '')
    branch = request.args.get('branch', '')
    start_date = request.args.get('SearchdateStart')
    end_date = request.args.get('SearchdateEnd')
    
    if search_date:
        search_date = format_date_to_mmddyyyy(search_date)
    if start_date and end_date:
        start_date = format_date_to_mmddyyyy(start_date)
        end_date = format_date_to_mmddyyyy(end_date)


    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

 
    query = "SELECT name, branch, LoanDate, Age, Birthday, Address, Customer_Work, Source_Income, Purpose, Amount, FirstTransaction, Status, discover_by, created_at, comment FROM customerinfo WHERE 1=1"
    params = []
   
    if search_name:
        query += " AND name LIKE %s"
        params.append(f"%{search_name}%")
    if search_date:
        query += " AND LoanDate = %s"
        params.append(search_date)
    if start_date and end_date:
        query += " AND LoanDate BETWEEN %s AND %s"
        params.append(start_date)
        params.append(end_date)
    if branch:
        query += " AND branch = %s"
        params.append(branch)

    cursor.execute(query, tuple(params))
    results = cursor.fetchall()

    cursor.close()
    connection.close()

    # Return the results as JSON
    return jsonify(results)  # Change to return jsonify

#CUSTOMERINFO SEARCH FUNCTION
   
   #sUGGESTION BOX IN CUSTOMERINFO
@app.route('/suggest-customers', methods=['GET'])
def suggest_customers():
    search_term = request.args.get('term', '')  # Get the search term from the query parameters
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Fetch customers whose names match the search term
    query = "SELECT name FROM customerinfo WHERE name LIKE %s LIMIT 10"
    cursor.execute(query, ('%' + search_term + '%',))
    results = cursor.fetchall()
    
    cursor.close()
    connection.close()
    
    # Return the names as a JSON response
    return jsonify([customer['name'] for customer in results])
def get_customer_info(name):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM customerinfo WHERE Name = %s", (name,))
    customer = cursor.fetchone()
    cursor.close()
    connection.close()
    return customer or {}

 #sUGGESTION BOX IN CUSTOMERINFO


#FEEDBACK CUSTOMERINFO
@app.route('/')
def index():
    cursor = get_db_connection()
    cursor.execute("SELECT id, name FROM branch")
    branches = cursor.fetchall()
    print("Branches fetched:", branches)  # Debugging line to confirm data
    cursor.close()
    return render_template('customerinfo.html', branches=branches) 


@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    data = request.json
    customer_name = data['name']
    feedback = data['feedback']

    # Create a cursor
    connection = get_db_connection()
    cursor = connection.cursor()

    # Update the customer's feedback
    cursor.execute("UPDATE customerinfo SET comment = %s WHERE name = %s", (feedback, customer_name))

    # Commit the transaction
    connection.commit()
    cursor.close()

    return jsonify({'message': 'Feedback updated successfully'}), 200


@app.route('/get-feedback', methods=['GET'])
def get_feedback():
    connection = get_db_connection()
    cursor = connection.cursor()
    
    cursor.execute("SELECT * FROM customerinfo")
    feedbacks = cursor.fetchall()
    
    cursor.close()
    return jsonify(feedbacks), 200

#FEEDBACK CUSTOMERINFO

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

