from flask import Flask, render_template, request, redirect, url_for, flash, Response
import boto3
from datetime import datetime, timedelta
import os
import uuid
from botocore.exceptions import ClientError
import csv
import io
from decimal import Decimal

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# DynamoDB setup
dynamodb = boto3.resource(
    'dynamodb',
    endpoint_url="http://localhost:8002",
    region_name="ap-northeast-1",
    aws_access_key_id="fakeMyKeyId",
    aws_secret_access_key="fakeSecretAccessKey"
)

TABLE_NAME = 'study_records'
ROADMAP_TABLE_NAME = 'learning_roadmaps'
DEFAULT_USER_ID = 'default_user'  # For now, using single user

def get_time_value(record):
    """Safely extract time value from record and convert to int"""
    time_value = record.get('time', 0)
    if isinstance(time_value, Decimal):
        return int(time_value)
    elif isinstance(time_value, (int, float)):
        return int(time_value)
    else:
        try:
            return int(time_value)
        except (ValueError, TypeError):
            print(f"Warning: Invalid time value: {time_value} (type: {type(time_value)}) for record {record.get('record_id')}")
            return 0

def get_table():
    """Get the DynamoDB table"""
    return dynamodb.Table(TABLE_NAME)

def get_roadmap_table():
    """Get the roadmap DynamoDB table"""
    return dynamodb.Table(ROADMAP_TABLE_NAME)

def init_db():
    """Initialize the DynamoDB tables"""
    # Create study_records table
    try:
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {
                    'AttributeName': 'user_id',
                    'KeyType': 'HASH'  # Partition key
                },
                {
                    'AttributeName': 'record_id',
                    'KeyType': 'RANGE'  # Sort key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'record_id',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print(f"Table {TABLE_NAME} created successfully!")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"Table {TABLE_NAME} already exists.")
        else:
            print(f"Error creating table: {e}")
            raise
    
    # Create learning_roadmaps table
    try:
        roadmap_table = dynamodb.create_table(
            TableName=ROADMAP_TABLE_NAME,
            KeySchema=[
                {
                    'AttributeName': 'user_id',
                    'KeyType': 'HASH'  # Partition key
                },
                {
                    'AttributeName': 'roadmap_id',
                    'KeyType': 'RANGE'  # Sort key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'roadmap_id',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print(f"Table {ROADMAP_TABLE_NAME} created successfully!")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"Table {ROADMAP_TABLE_NAME} already exists.")
        else:
            print(f"Error creating roadmap table: {e}")
            raise

@app.route('/')
def dashboard():
    """Display the dashboard with recent study records and memo highlights"""
    table = get_table()
    
    try:
        # Get all records for the user
        response = table.query(
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': DEFAULT_USER_ID}
        )
        
        records = response.get('Items', [])
        
        # Sort by date descending, then by created_at descending
        records.sort(key=lambda x: (x.get('date', ''), x.get('created_at', '')), reverse=True)
        
        # Get recent study records (last 10)
        recent_records = records[:10]
        
        # Get recent "understood" items
        understood_items = [
            record for record in records 
            if record.get('understood') and record.get('understood').strip()
        ][:5]
        
        # Get recent "could not do" items
        could_not_do_items = [
            record for record in records 
            if record.get('could_not_do') and record.get('could_not_do').strip()
        ][:5]
        
        # Calculate total study time this week
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        week_total_time = sum(
            get_time_value(record) for record in records 
            if record.get('date', '') >= week_ago
        )
        
        # Calculate all-time total study time
        all_time_total = sum(get_time_value(record) for record in records)
        
        # Calculate total days studied
        unique_dates = set(record.get('date', '') for record in records if record.get('date'))
        total_days = len(unique_dates)
        
        # Calculate average time per day (for days with records)
        avg_time_per_day = all_time_total / total_days if total_days > 0 else 0
        
        return render_template('dashboard.html', 
                             recent_records=recent_records,
                             understood_items=understood_items,
                             could_not_do_items=could_not_do_items,
                             week_total_time=week_total_time,
                             all_time_total=all_time_total,
                             total_days=total_days,
                             avg_time_per_day=round(avg_time_per_day, 1))
    
    except ClientError as e:
        print(f"Error querying DynamoDB: {e}")
        flash('データベースエラーが発生しました。', 'error')
        return render_template('dashboard.html', 
                             recent_records=[],
                             understood_items=[],
                             could_not_do_items=[],
                             week_total_time=0,
                             all_time_total=0,
                             total_days=0,
                             avg_time_per_day=0)

@app.route('/add_record', methods=['GET', 'POST'])
def add_record():
    """Add a new study record with memo functionality"""
    if request.method == 'POST':
        date = request.form['date']
        content = request.form['content']
        time = int(request.form['time'])
        category = request.form.get('category', 'その他').strip()
        could_not_do = request.form.get('could_not_do', '').strip()
        understood = request.form.get('understood', '').strip()
        
        if not date or not content or not time or not category:
            flash('日付、内容、時間、カテゴリーは必須項目です。', 'error')
            return render_template('add_record.html')
        
        # Create a unique record ID using timestamp + UUID
        record_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        created_at = datetime.now().isoformat()
        
        table = get_table()
        
        try:
            # Prepare item for DynamoDB
            item = {
                'user_id': DEFAULT_USER_ID,
                'record_id': record_id,
                'date': date,
                'content': content,
                'time': int(time),  # Ensure it's stored as int
                'category': category,
                'created_at': created_at
            }
            
            # Add optional fields only if they have values
            if could_not_do:
                item['could_not_do'] = could_not_do
            if understood:
                item['understood'] = understood
            
            table.put_item(Item=item)
            
            flash('学習記録が追加されました！', 'success')
            return redirect(url_for('dashboard'))
            
        except ClientError as e:
            print(f"Error adding record to DynamoDB: {e}")
            flash('データベースエラーが発生しました。', 'error')
            return render_template('add_record.html')
    
    return render_template('add_record.html')

@app.route('/records')
def records():
    """Display all study records"""
    table = get_table()
    
    try:
        # Get all records for the user
        response = table.query(
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': DEFAULT_USER_ID}
        )
        
        all_records = response.get('Items', [])
        
        # Sort by date descending, then by created_at descending
        all_records.sort(key=lambda x: (x.get('date', ''), x.get('created_at', '')), reverse=True)
        
        # Calculate statistics
        total_time = sum(get_time_value(record) for record in all_records)
        total_records = len(all_records)
        unique_dates = set(record.get('date', '') for record in all_records if record.get('date'))
        total_days = len(unique_dates)
        avg_time_per_session = total_time / total_records if total_records > 0 else 0
        avg_time_per_day = total_time / total_days if total_days > 0 else 0
        
        # Count memos
        with_understood = sum(1 for r in all_records if r.get('understood', '').strip())
        with_could_not_do = sum(1 for r in all_records if r.get('could_not_do', '').strip())
        total_memos = with_understood + with_could_not_do
        
        return render_template('records.html', 
                             records=all_records,
                             total_time=total_time,
                             total_records=total_records,
                             total_days=total_days,
                             avg_time_per_session=round(avg_time_per_session, 1),
                             avg_time_per_day=round(avg_time_per_day, 1),
                             total_memos=total_memos)
    
    except ClientError as e:
        print(f"Error querying records from DynamoDB: {e}")
        flash('データベースエラーが発生しました。', 'error')
        return render_template('records.html', records=[])

@app.route('/memo_insights')
def memo_insights():
    """Display memo insights - things understood and things to work on"""
    table = get_table()
    
    try:
        # Get all records for the user
        response = table.query(
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': DEFAULT_USER_ID}
        )
        
        records = response.get('Items', [])
        
        # Sort by date descending, then by created_at descending
        records.sort(key=lambda x: (x.get('date', ''), x.get('created_at', '')), reverse=True)
        
        # Get all "understood" items
        understood_items = [
            record for record in records 
            if record.get('understood') and record.get('understood').strip()
        ]
        
        # Get all "could not do" items
        could_not_do_items = [
            record for record in records 
            if record.get('could_not_do') and record.get('could_not_do').strip()
        ]
        
        return render_template('memo_insights.html', 
                             understood_items=understood_items,
                             could_not_do_items=could_not_do_items)
    
    except ClientError as e:
        print(f"Error querying memo insights from DynamoDB: {e}")
        flash('データベースエラーが発生しました。', 'error')
        return render_template('memo_insights.html', 
                             understood_items=[],
                             could_not_do_items=[])

@app.route('/export_csv')
def export_csv():
    """Export all study records to CSV"""
    table = get_table()
    
    try:
        # Get all records for the user
        response = table.query(
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': DEFAULT_USER_ID}
        )
        
        records = response.get('Items', [])
        
        # Sort by date ascending (oldest first for CSV)
        records.sort(key=lambda x: (x.get('date', ''), x.get('created_at', '')))
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['日付', '学習内容', '時間（分）', '理解できたこと', 'できなかったこと', '作成日時'])
        
        # Write data
        for record in records:
            writer.writerow([
                record.get('date', ''),
                record.get('content', ''),
                record.get('time', 0),
                record.get('understood', ''),
                record.get('could_not_do', ''),
                record.get('created_at', '')
            ])
        
        # Create response
        output.seek(0)
        csv_data = output.getvalue()
        
        # Create response with proper headers
        response = Response(
            csv_data.encode('utf-8-sig'),  # UTF-8 with BOM for Excel
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=study_records_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                'Content-Type': 'text/csv; charset=utf-8-sig'
            }
        )
        
        return response
        
    except ClientError as e:
        print(f"Error exporting CSV from DynamoDB: {e}")
        flash('CSVエクスポート中にエラーが発生しました。', 'error')
        return redirect(url_for('records'))

@app.route('/roadmaps')
def roadmaps():
    """Display all learning roadmaps"""
    table = get_roadmap_table()
    
    try:
        response = table.query(
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': DEFAULT_USER_ID}
        )
        
        all_roadmaps = response.get('Items', [])
        all_roadmaps.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Calculate progress for each roadmap
        for roadmap in all_roadmaps:
            milestones = roadmap.get('milestones', [])
            if milestones:
                completed = sum(1 for m in milestones if m.get('completed', False))
                roadmap['progress'] = int((completed / len(milestones)) * 100)
            else:
                roadmap['progress'] = 0
        
        return render_template('roadmaps.html', roadmaps=all_roadmaps)
        
    except ClientError as e:
        print(f"Error querying roadmaps: {e}")
        flash('データベースエラーが発生しました。', 'error')
        return render_template('roadmaps.html', roadmaps=[])

@app.route('/roadmap/<roadmap_id>')
def view_roadmap(roadmap_id):
    """View a specific roadmap"""
    table = get_roadmap_table()
    
    try:
        response = table.get_item(
            Key={
                'user_id': DEFAULT_USER_ID,
                'roadmap_id': roadmap_id
            }
        )
        
        roadmap = response.get('Item')
        if not roadmap:
            flash('ロードマップが見つかりません。', 'error')
            return redirect(url_for('roadmaps'))
        
        # Calculate progress
        milestones = roadmap.get('milestones', [])
        if milestones:
            completed = sum(1 for m in milestones if m.get('completed', False))
            roadmap['progress'] = int((completed / len(milestones)) * 100)
        else:
            roadmap['progress'] = 0
        
        return render_template('roadmap_detail.html', roadmap=roadmap)
        
    except ClientError as e:
        print(f"Error getting roadmap: {e}")
        flash('ロードマップの取得中にエラーが発生しました。', 'error')
        return redirect(url_for('roadmaps'))

@app.route('/add_roadmap', methods=['GET', 'POST'])
def add_roadmap():
    """Add a new learning roadmap"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        goal = request.form.get('goal', '').strip()
        
        if not title:
            flash('タイトルは必須項目です。', 'error')
            return render_template('add_roadmap.html')
        
        # Create roadmap ID
        roadmap_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        created_at = datetime.now().isoformat()
        
        # Parse milestones
        milestones = []
        milestone_titles = request.form.getlist('milestone_title[]')
        milestone_descriptions = request.form.getlist('milestone_description[]')
        milestone_durations = request.form.getlist('milestone_duration[]')
        
        for i in range(len(milestone_titles)):
            if milestone_titles[i].strip():
                milestones.append({
                    'id': str(uuid.uuid4())[:8],
                    'title': milestone_titles[i].strip(),
                    'description': milestone_descriptions[i].strip() if i < len(milestone_descriptions) else '',
                    'estimated_days': int(milestone_durations[i]) if i < len(milestone_durations) and milestone_durations[i].isdigit() else 7,
                    'completed': False,
                    'completed_date': None
                })
        
        table = get_roadmap_table()
        
        try:
            item = {
                'user_id': DEFAULT_USER_ID,
                'roadmap_id': roadmap_id,
                'title': title,
                'description': description,
                'goal': goal,
                'milestones': milestones,
                'created_at': created_at,
                'status': 'active'
            }
            
            table.put_item(Item=item)
            flash('ロードマップが作成されました！', 'success')
            return redirect(url_for('view_roadmap', roadmap_id=roadmap_id))
            
        except ClientError as e:
            print(f"Error adding roadmap: {e}")
            flash('ロードマップの作成中にエラーが発生しました。', 'error')
            return render_template('add_roadmap.html')
    
    return render_template('add_roadmap.html')

@app.route('/update_milestone/<roadmap_id>/<milestone_id>', methods=['POST'])
def update_milestone(roadmap_id, milestone_id):
    """Update milestone completion status"""
    table = get_roadmap_table()
    
    try:
        # Get current roadmap
        response = table.get_item(
            Key={
                'user_id': DEFAULT_USER_ID,
                'roadmap_id': roadmap_id
            }
        )
        
        roadmap = response.get('Item')
        if not roadmap:
            return {'error': 'Roadmap not found'}, 404
        
        # Update milestone
        milestones = roadmap.get('milestones', [])
        for milestone in milestones:
            if milestone['id'] == milestone_id:
                milestone['completed'] = request.json.get('completed', False)
                if milestone['completed']:
                    milestone['completed_date'] = datetime.now().isoformat()
                else:
                    milestone['completed_date'] = None
                break
        
        # Save updated roadmap
        roadmap['milestones'] = milestones
        table.put_item(Item=roadmap)
        
        return {'success': True}
        
    except ClientError as e:
        print(f"Error updating milestone: {e}")
        return {'error': 'Database error'}, 500

@app.route('/edit_roadmap/<roadmap_id>', methods=['GET', 'POST'])
def edit_roadmap(roadmap_id):
    """Edit an existing roadmap"""
    table = get_roadmap_table()
    
    if request.method == 'GET':
        try:
            response = table.get_item(
                Key={
                    'user_id': DEFAULT_USER_ID,
                    'roadmap_id': roadmap_id
                }
            )
            
            roadmap = response.get('Item')
            if not roadmap:
                flash('ロードマップが見つかりません。', 'error')
                return redirect(url_for('roadmaps'))
            
            return render_template('edit_roadmap.html', roadmap=roadmap)
            
        except ClientError as e:
            print(f"Error getting roadmap: {e}")
            flash('ロードマップの取得中にエラーが発生しました。', 'error')
            return redirect(url_for('roadmaps'))
    
    # POST request - update roadmap
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    goal = request.form.get('goal', '').strip()
    
    if not title:
        flash('タイトルは必須項目です。', 'error')
        return redirect(url_for('edit_roadmap', roadmap_id=roadmap_id))
    
    try:
        # Get current roadmap
        response = table.get_item(
            Key={
                'user_id': DEFAULT_USER_ID,
                'roadmap_id': roadmap_id
            }
        )
        
        roadmap = response.get('Item')
        if not roadmap:
            flash('ロードマップが見つかりません。', 'error')
            return redirect(url_for('roadmaps'))
        
        # Parse milestones
        milestones = []
        milestone_ids = request.form.getlist('milestone_id[]')
        milestone_titles = request.form.getlist('milestone_title[]')
        milestone_descriptions = request.form.getlist('milestone_description[]')
        milestone_durations = request.form.getlist('milestone_duration[]')
        
        for i in range(len(milestone_titles)):
            if milestone_titles[i].strip():
                milestone_id = milestone_ids[i] if i < len(milestone_ids) and milestone_ids[i] else str(uuid.uuid4())[:8]
                
                # Find existing milestone to preserve completion data
                existing_milestone = None
                for existing in roadmap.get('milestones', []):
                    if existing.get('id') == milestone_id:
                        existing_milestone = existing
                        break
                
                milestones.append({
                    'id': milestone_id,
                    'title': milestone_titles[i].strip(),
                    'description': milestone_descriptions[i].strip() if i < len(milestone_descriptions) else '',
                    'estimated_days': int(milestone_durations[i]) if i < len(milestone_durations) and milestone_durations[i].isdigit() else 7,
                    'completed': existing_milestone.get('completed', False) if existing_milestone else False,
                    'completed_date': existing_milestone.get('completed_date') if existing_milestone else None
                })
        
        # Update roadmap
        roadmap.update({
            'title': title,
            'description': description,
            'goal': goal,
            'milestones': milestones,
            'updated_at': datetime.now().isoformat()
        })
        
        table.put_item(Item=roadmap)
        flash('ロードマップが更新されました！', 'success')
        return redirect(url_for('view_roadmap', roadmap_id=roadmap_id))
        
    except ClientError as e:
        print(f"Error updating roadmap: {e}")
        flash('ロードマップの更新中にエラーが発生しました。', 'error')
        return redirect(url_for('edit_roadmap', roadmap_id=roadmap_id))

@app.route('/delete_roadmap/<roadmap_id>', methods=['POST'])
def delete_roadmap(roadmap_id):
    """Delete a roadmap"""
    table = get_roadmap_table()
    
    try:
        # Check if roadmap exists
        response = table.get_item(
            Key={
                'user_id': DEFAULT_USER_ID,
                'roadmap_id': roadmap_id
            }
        )
        
        if not response.get('Item'):
            flash('ロードマップが見つかりません。', 'error')
            return redirect(url_for('roadmaps'))
        
        # Delete roadmap
        table.delete_item(
            Key={
                'user_id': DEFAULT_USER_ID,
                'roadmap_id': roadmap_id
            }
        )
        
        flash('ロードマップが削除されました。', 'success')
        return redirect(url_for('roadmaps'))
        
    except ClientError as e:
        print(f"Error deleting roadmap: {e}")
        flash('ロードマップの削除中にエラーが発生しました。', 'error')
        return redirect(url_for('roadmaps'))

@app.route('/timer')
def timer():
    """Study timer page"""
    return render_template('timer.html')

@app.route('/save_timer_session', methods=['POST'])
def save_timer_session():
    """Save a study session from timer"""
    try:
        data = request.get_json()
        print(f"Received data: {data}")  # Debug log
        
        content = data.get('content', '').strip() if data else ''
        category = data.get('category', 'その他').strip() if data else 'その他'
        time_minutes = data.get('time_minutes', 0) if data else 0
        understood = data.get('understood', '').strip() if data else ''
        could_not_do = data.get('could_not_do', '').strip() if data else ''
        
        print(f"Parsed - content: '{content}', time: {time_minutes}")  # Debug log
        
        if not content or time_minutes <= 0:
            return {'error': f'Invalid data - content: "{content}", time: {time_minutes}'}, 400
        
        # Create a unique record ID using timestamp + UUID
        record_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        created_at = datetime.now().isoformat()
        date = datetime.now().strftime('%Y-%m-%d')
        
        table = get_table()
        
        # Prepare item for DynamoDB
        item = {
            'user_id': DEFAULT_USER_ID,
            'record_id': record_id,
            'date': date,
            'content': content,
            'category': category,
            'time': int(time_minutes),  # Ensure it's stored as int
            'created_at': created_at,
            'source': 'timer'  # Mark as timer-generated record
        }
        
        # Add optional fields only if they have values
        if could_not_do:
            item['could_not_do'] = could_not_do
        if understood:
            item['understood'] = understood
        
        table.put_item(Item=item)
        print(f"Successfully saved timer session: {record_id}")
        
        return {'success': True, 'record_id': record_id}
        
    except ClientError as e:
        print(f"Error saving timer session: {e}")
        return {'error': 'Database error'}, 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {'error': 'Unexpected error'}, 500

@app.route('/api/today_stats')
def today_stats():
    """Get today's study statistics"""
    table = get_table()
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        response = table.query(
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': DEFAULT_USER_ID}
        )
        
        records = response.get('Items', [])
        today_records = [r for r in records if r.get('date') == today]
        total_time = sum(get_time_value(r) for r in today_records)
        
        return {
            'total_time_minutes': total_time,
            'session_count': len(today_records)
        }
        
    except ClientError as e:
        print(f"Error getting today's stats: {e}")
        return {'total_time_minutes': 0, 'session_count': 0}

@app.route('/category_stats')
def category_stats():
    """Display category-wise statistics"""
    table = get_table()
    
    try:
        response = table.query(
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': DEFAULT_USER_ID}
        )
        
        all_records = response.get('Items', [])
        
        # Category statistics
        category_data = {}
        for record in all_records:
            category = record.get('category', 'その他')
            if category not in category_data:
                category_data[category] = {
                    'total_time': 0,
                    'count': 0,
                    'records': []
                }
            category_data[category]['total_time'] += get_time_value(record)
            category_data[category]['count'] += 1
            category_data[category]['records'].append(record)
        
        # Calculate percentages and sort by total time
        total_time = sum(data['total_time'] for data in category_data.values())
        for category, data in category_data.items():
            data['percentage'] = round((data['total_time'] / total_time * 100) if total_time > 0 else 0, 1)
            data['avg_time'] = round(data['total_time'] / data['count'] if data['count'] > 0 else 0, 1)
        
        # Sort categories by total time
        sorted_categories = sorted(category_data.items(), key=lambda x: x[1]['total_time'], reverse=True)
        
        # Get weekly statistics by category
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        weekly_category_data = {}
        
        for record in all_records:
            if record.get('date', '') >= week_ago:
                category = record.get('category', 'その他')
                if category not in weekly_category_data:
                    weekly_category_data[category] = {
                        'total_time': 0,
                        'count': 0
                    }
                weekly_category_data[category]['total_time'] += get_time_value(record)
                weekly_category_data[category]['count'] += 1
        
        return render_template('category_stats.html', 
                             categories=sorted_categories,
                             total_time=total_time,
                             weekly_data=weekly_category_data)
        
    except ClientError as e:
        print(f"Error querying category stats: {e}")
        flash('データベースエラーが発生しました。', 'error')
        return render_template('category_stats.html', 
                             categories=[],
                             total_time=0,
                             weekly_data={})

@app.route('/edit_record/<record_id>', methods=['GET', 'POST'])
def edit_record(record_id):
    """Edit an existing study record"""
    table = get_table()
    
    if request.method == 'GET':
        try:
            response = table.get_item(
                Key={
                    'user_id': DEFAULT_USER_ID,
                    'record_id': record_id
                }
            )
            
            record = response.get('Item')
            if not record:
                flash('記録が見つかりません。', 'error')
                return redirect(url_for('records'))
            
            return render_template('edit_record.html', record=record)
            
        except ClientError as e:
            print(f"Error getting record: {e}")
            flash('記録の取得中にエラーが発生しました。', 'error')
            return redirect(url_for('records'))
    
    # POST request - update record
    date = request.form['date']
    content = request.form['content']
    time = int(request.form['time'])
    category = request.form.get('category', 'その他').strip()
    could_not_do = request.form.get('could_not_do', '').strip()
    understood = request.form.get('understood', '').strip()
    
    if not date or not content or not time or not category:
        flash('日付、内容、時間、カテゴリーは必須項目です。', 'error')
        return redirect(url_for('edit_record', record_id=record_id))
    
    try:
        # Get current record
        response = table.get_item(
            Key={
                'user_id': DEFAULT_USER_ID,
                'record_id': record_id
            }
        )
        
        record = response.get('Item')
        if not record:
            flash('記録が見つかりません。', 'error')
            return redirect(url_for('records'))
        
        # Update record
        updated_item = {
            'user_id': DEFAULT_USER_ID,
            'record_id': record_id,
            'date': date,
            'content': content,
            'time': int(time),  # Ensure it's stored as int
            'category': category,
            'created_at': record.get('created_at'),  # Keep original creation time
            'updated_at': datetime.now().isoformat(),
            'source': record.get('source', 'manual')  # Keep original source
        }
        
        # Add optional fields only if they have values
        if could_not_do:
            updated_item['could_not_do'] = could_not_do
        if understood:
            updated_item['understood'] = understood
        
        table.put_item(Item=updated_item)
        flash('記録が更新されました！', 'success')
        return redirect(url_for('records'))
        
    except ClientError as e:
        print(f"Error updating record: {e}")
        flash('記録の更新中にエラーが発生しました。', 'error')
        return redirect(url_for('edit_record', record_id=record_id))

@app.route('/delete_record/<record_id>', methods=['POST'])
def delete_record(record_id):
    """Delete a study record"""
    table = get_table()
    
    try:
        # Check if record exists
        response = table.get_item(
            Key={
                'user_id': DEFAULT_USER_ID,
                'record_id': record_id
            }
        )
        
        if not response.get('Item'):
            flash('記録が見つかりません。', 'error')
            return redirect(url_for('records'))
        
        # Delete record
        table.delete_item(
            Key={
                'user_id': DEFAULT_USER_ID,
                'record_id': record_id
            }
        )
        
        flash('記録が削除されました。', 'success')
        return redirect(url_for('records'))
        
    except ClientError as e:
        print(f"Error deleting record: {e}")
        flash('記録の削除中にエラーが発生しました。', 'error')
        return redirect(url_for('records'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)