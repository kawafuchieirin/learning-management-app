from flask import Flask, render_template, request, redirect, url_for, flash, Response
import boto3
from datetime import datetime, timedelta
import os
import uuid
from botocore.exceptions import ClientError
import csv
import io

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
DEFAULT_USER_ID = 'default_user'  # For now, using single user

def get_table():
    """Get the DynamoDB table"""
    return dynamodb.Table(TABLE_NAME)

def init_db():
    """Initialize the DynamoDB table"""
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
            int(record.get('time', 0)) for record in records 
            if record.get('date', '') >= week_ago
        )
        
        # Calculate all-time total study time
        all_time_total = sum(int(record.get('time', 0)) for record in records)
        
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
        could_not_do = request.form.get('could_not_do', '').strip()
        understood = request.form.get('understood', '').strip()
        
        if not date or not content or not time:
            flash('日付、内容、時間は必須項目です。', 'error')
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
                'time': time,
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
        total_time = sum(int(record.get('time', 0)) for record in all_records)
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True)