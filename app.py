from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Database setup
DATABASE = 'learning_app.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with the study_records table"""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS study_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            content TEXT NOT NULL,
            time INTEGER NOT NULL,
            could_not_do TEXT,
            understood TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def dashboard():
    """Display the dashboard with recent study records and memo highlights"""
    conn = get_db_connection()
    
    # Get recent study records (last 7 days)
    recent_records = conn.execute('''
        SELECT * FROM study_records 
        ORDER BY date DESC, created_at DESC 
        LIMIT 10
    ''').fetchall()
    
    # Get recent "understood" items
    understood_items = conn.execute('''
        SELECT id, date, content, understood FROM study_records 
        WHERE understood IS NOT NULL AND understood != ''
        ORDER BY date DESC, created_at DESC 
        LIMIT 5
    ''').fetchall()
    
    # Get recent "could not do" items
    could_not_do_items = conn.execute('''
        SELECT id, date, content, could_not_do FROM study_records 
        WHERE could_not_do IS NOT NULL AND could_not_do != ''
        ORDER BY date DESC, created_at DESC 
        LIMIT 5
    ''').fetchall()
    
    # Calculate total study time this week
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    total_time = conn.execute('''
        SELECT SUM(time) as total FROM study_records 
        WHERE date >= ?
    ''', (week_ago,)).fetchone()['total'] or 0
    
    conn.close()
    
    return render_template('dashboard.html', 
                         recent_records=recent_records,
                         understood_items=understood_items,
                         could_not_do_items=could_not_do_items,
                         total_time=total_time)

@app.route('/add_record', methods=['GET', 'POST'])
def add_record():
    """Add a new study record with memo functionality"""
    if request.method == 'POST':
        date = request.form['date']
        content = request.form['content']
        time = int(request.form['time'])
        could_not_do = request.form.get('could_not_do', '').strip()
        understood = request.form.get('understood', '').strip()
        
        if not date or not content or not time:
            flash('日付、内容、時間は必須項目です。', 'error')
            return render_template('add_record.html')
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO study_records (date, content, time, could_not_do, understood)
            VALUES (?, ?, ?, ?, ?)
        ''', (date, content, time, could_not_do or None, understood or None))
        conn.commit()
        conn.close()
        
        flash('学習記録が追加されました！', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('add_record.html')

@app.route('/records')
def records():
    """Display all study records"""
    conn = get_db_connection()
    all_records = conn.execute('''
        SELECT * FROM study_records 
        ORDER BY date DESC, created_at DESC
    ''').fetchall()
    conn.close()
    
    return render_template('records.html', records=all_records)

@app.route('/memo_insights')
def memo_insights():
    """Display memo insights - things understood and things to work on"""
    conn = get_db_connection()
    
    # Get all "understood" items
    understood_items = conn.execute('''
        SELECT id, date, content, understood FROM study_records 
        WHERE understood IS NOT NULL AND understood != ''
        ORDER BY date DESC, created_at DESC
    ''').fetchall()
    
    # Get all "could not do" items
    could_not_do_items = conn.execute('''
        SELECT id, date, content, could_not_do FROM study_records 
        WHERE could_not_do IS NOT NULL AND could_not_do != ''
        ORDER BY date DESC, created_at DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('memo_insights.html', 
                         understood_items=understood_items,
                         could_not_do_items=could_not_do_items)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)