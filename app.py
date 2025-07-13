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
# 環境変数からエンドポイントを取得（本番環境では未設定にする）
dynamodb_endpoint = os.environ.get('DYNAMODB_ENDPOINT_URL')
dynamodb_config = {
    'region_name': os.environ.get('AWS_REGION', 'ap-northeast-1')
}

# ローカル開発環境の場合のみエンドポイントと認証情報を設定
if dynamodb_endpoint:
    dynamodb_config['endpoint_url'] = dynamodb_endpoint
    dynamodb_config['aws_access_key_id'] = os.environ.get('AWS_ACCESS_KEY_ID', 'fakeMyKeyId')
    dynamodb_config['aws_secret_access_key'] = os.environ.get('AWS_SECRET_ACCESS_KEY', 'fakeSecretAccessKey')

dynamodb = boto3.resource('dynamodb', **dynamodb_config)

# テーブル名の設定（環境変数からプレフィックスを取得）
table_prefix = os.environ.get('TABLE_NAME_PREFIX', '')
TABLE_NAME = f'{table_prefix}-study_records' if table_prefix else 'study_records'
ROADMAP_TABLE_NAME = f'{table_prefix}-learning_roadmaps' if table_prefix else 'learning_roadmaps'
DEFAULT_USER_ID = 'default_user'  # For now, using single user

def get_time_value(record):
    """Safely extract time value from record and convert to float"""
    time_value = record.get('time', 0)
    try:
        # Convert to float to handle both int and Decimal types
        return float(time_value)
    except (ValueError, TypeError):
        return 0.0

def query_user_records(table, user_id=DEFAULT_USER_ID):
    """Common function to query user records with error handling"""
    def query_operation():
        response = table.query(
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': user_id}
        )
        return response.get('Items', [])
    
    return safe_db_operation(query_operation, "レコード取得", [])

def calculate_stats(records):
    """Calculate common statistics from records"""
    total_time = sum(get_time_value(r) for r in records)
    unique_dates = set(r.get('date', '') for r in records if r.get('date'))
    total_days = len(unique_dates)
    return {
        'total_time': total_time,
        'total_records': len(records),
        'total_days': total_days,
        'avg_time_per_session': total_time / len(records) if records else 0,
        'avg_time_per_day': total_time / total_days if total_days > 0 else 0
    }

def safe_render_template(template, error_context=None, **kwargs):
    """Safely render template with error fallback"""
    if error_context:
        for key, default_value in error_context.items():
            kwargs.setdefault(key, default_value)
    return render_template(template, **kwargs)

def get_roadmap_by_id(roadmap_id):
    """Get roadmap by ID with error handling"""
    def get_operation():
        response = get_roadmap_table().get_item(
            Key={'user_id': DEFAULT_USER_ID, 'roadmap_id': roadmap_id}
        )
        return response.get('Item')
    
    return safe_db_operation(get_operation, "ロードマップ取得", None)

def calculate_milestone_stats(roadmap, related_records):
    """Calculate statistics for each milestone"""
    milestones = roadmap.get('milestones', [])
    milestone_stats = {}
    
    for milestone in milestones:
        milestone_id = milestone['id']
        milestone_records = [r for r in related_records if r.get('milestone_id') == milestone_id]
        milestone_time = sum(get_time_value(r) for r in milestone_records)
        estimated_hours = milestone.get('estimated_hours', 0)
        
        # Convert to float to ensure compatibility
        milestone_time_float = float(milestone_time)
        estimated_hours_float = float(estimated_hours) if estimated_hours else 0
        
        # Calculate time analysis
        actual_hours = milestone_time_float / 60
        time_efficiency = (estimated_hours_float / actual_hours * 100) if actual_hours > 0 else 0
        time_variance = actual_hours - estimated_hours_float
        is_on_schedule = actual_hours <= estimated_hours_float
        
        # Calculate progress based on completion status and time
        if milestone.get('completed', False):
            # If marked as completed, progress is 100%
            progress_rate = 100
        else:
            # If not completed, calculate based on time but cap at 100%
            if estimated_hours_float > 0:
                progress_rate = min(int((milestone_time_float / 60) / estimated_hours_float * 100), 100)
            else:
                progress_rate = 0
        
        milestone_stats[milestone_id] = {
            'time_spent': milestone_time,
            'estimated_hours': estimated_hours,
            'actual_hours': actual_hours,
            'time_efficiency': time_efficiency,
            'time_variance': time_variance,
            'is_on_schedule': is_on_schedule,
            'progress_by_time': progress_rate,  # Updated to use new logic
            'record_count': len(milestone_records),
            'recent_records': sorted(milestone_records, key=lambda x: x.get('date', ''), reverse=True)[:3]
        }
    
    return milestone_stats

def calculate_roadmap_progress(roadmap, related_records):
    """Calculate overall roadmap progress"""
    milestones = roadmap.get('milestones', [])
    if not milestones:
        return {'progress': 0, 'time_progress': 0, 'total_time_spent': 0, 
                'total_estimated_hours': 0, 'total_time_hours': 0}
    
    total_time_spent = sum(get_time_value(r) for r in related_records)
    total_estimated_hours = sum(float(m.get('estimated_hours', 0)) for m in milestones)
    total_time_hours = float(total_time_spent) / 60
    
    completed_milestones = sum(1 for m in milestones if m.get('completed', False))
    completion_progress = int((completed_milestones / len(milestones)) * 100)
    
    # Calculate time progress with cap at 100%
    time_progress = min(int((total_time_hours / total_estimated_hours) * 100), 100) if total_estimated_hours > 0 else 0
    
    # Calculate overall time efficiency
    overall_efficiency = (total_estimated_hours / total_time_hours * 100) if total_time_hours > 0 else 0
    time_variance = total_time_hours - total_estimated_hours
    is_ahead_of_schedule = total_time_hours < total_estimated_hours
    is_on_schedule = abs(time_variance) <= (total_estimated_hours * 0.1)  # Within 10%
    
    return {
        'progress': completion_progress,
        'time_progress': time_progress,
        'total_time_spent': total_time_spent,
        'total_estimated_hours': total_estimated_hours,
        'total_time_hours': total_time_hours,
        'overall_efficiency': overall_efficiency,
        'time_variance': time_variance,
        'is_ahead_of_schedule': is_ahead_of_schedule,
        'is_on_schedule': is_on_schedule
    }

def parse_milestone_form_data():
    """Parse milestone data from form"""
    milestones = []
    titles = request.form.getlist('milestone_title[]')
    descriptions = request.form.getlist('milestone_description[]')
    durations = request.form.getlist('milestone_duration[]')
    
    for i, title in enumerate(titles):
        if title.strip():
            milestones.append({
                'id': str(uuid.uuid4())[:8],
                'title': title.strip(),
                'description': descriptions[i].strip() if i < len(descriptions) else '',
                'estimated_hours': int(durations[i]) if i < len(durations) and durations[i].isdigit() else 8,
                'completed': False,
                'completed_date': None
            })
    
    return milestones

def create_record_item(content, time, category, **optional_fields):
    """Create a standardized study record item"""
    record_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    item = {
        'user_id': DEFAULT_USER_ID,
        'record_id': record_id,
        'date': optional_fields.get('date', datetime.now().strftime('%Y-%m-%d')),
        'content': content,
        'time': int(time),
        'category': category,
        'created_at': datetime.now().isoformat()
    }
    
    # Add optional fields
    for field in ['could_not_do', 'understood', 'roadmap_id', 'milestone_id', 'source']:
        if field in optional_fields and optional_fields[field]:
            item[field] = optional_fields[field]
    
    return item, record_id

def handle_db_error(error, operation="database operation", return_value=None):
    """Unified error handling for database operations"""
    print(f"Error during {operation}: {error}")
    flash(f'{operation}中にエラーが発生しました。', 'error')
    return return_value

def safe_db_operation(operation_func, error_message="データベース操作", default_return=None):
    """Safely execute database operations with unified error handling"""
    try:
        return operation_func()
    except ClientError as e:
        return handle_db_error(e, error_message, default_return)
    except Exception as e:
        return handle_db_error(e, error_message, default_return)

def calculate_learning_streak(records):
    """Calculate current learning streak in days"""
    if not records:
        return 0
    
    # Get unique dates and sort them
    dates = sorted(set(r.get('date', '') for r in records if r.get('date')))
    if not dates:
        return 0
    
    # Calculate streak from most recent date backwards
    from datetime import datetime, timedelta
    today = datetime.now().strftime('%Y-%m-%d')
    current_date = datetime.strptime(today, '%Y-%m-%d')
    streak = 0
    
    # Check if studied today or yesterday (allow 1 day gap)
    latest_study = datetime.strptime(dates[-1], '%Y-%m-%d')
    days_since_last = (current_date - latest_study).days
    
    if days_since_last > 1:
        return 0  # Streak broken
    
    # Count consecutive days backwards
    for i in range(len(dates) - 1, -1, -1):
        expected_date = current_date - timedelta(days=streak)
        study_date = datetime.strptime(dates[i], '%Y-%m-%d')
        
        if study_date.date() == expected_date.date() or (streak == 0 and days_since_last <= 1):
            streak += 1
        else:
            break
    
    return streak

def calculate_experience_and_level(records):
    """Calculate experience points and level based on study records"""
    total_time = sum(get_time_value(r) for r in records)
    experience = total_time  # 1 minute = 1 XP
    
    # Level calculation: each level requires more XP
    # Level 1: 0-59 XP, Level 2: 60-179 XP, Level 3: 180-359 XP, etc.
    level = 1
    xp_for_next = 60
    remaining_xp = experience
    
    while remaining_xp >= xp_for_next:
        remaining_xp -= xp_for_next
        level += 1
        xp_for_next = level * 60  # Each level requires 60 more XP than the previous
    
    return {
        'level': level,
        'experience': experience,
        'xp_current_level': remaining_xp,
        'xp_for_next_level': xp_for_next,
        'progress_percent': int((remaining_xp / xp_for_next) * 100)
    }

def get_achievement_badges(records, roadmaps):
    """Calculate earned achievement badges"""
    badges = []
    total_time = sum(get_time_value(r) for r in records)
    total_records = len(records)
    streak = calculate_learning_streak(records)
    
    # Time-based badges
    if total_time >= 60:  # 1 hour
        badges.append({'name': '初心者', 'icon': '🌱', 'description': '1時間の学習を達成'})
    if total_time >= 300:  # 5 hours
        badges.append({'name': '学習者', 'icon': '📚', 'description': '5時間の学習を達成'})
    if total_time >= 1200:  # 20 hours
        badges.append({'name': '努力家', 'icon': '💪', 'description': '20時間の学習を達成'})
    if total_time >= 3000:  # 50 hours
        badges.append({'name': '達人', 'icon': '🎯', 'description': '50時間の学習を達成'})
    
    # Streak-based badges
    if streak >= 3:
        badges.append({'name': '継続力', 'icon': '🔥', 'description': '3日連続学習'})
    if streak >= 7:
        badges.append({'name': '習慣マスター', 'icon': '⭐', 'description': '7日連続学習'})
    if streak >= 30:
        badges.append({'name': '鉄の意志', 'icon': '💎', 'description': '30日連続学習'})
    
    # Record count badges
    if total_records >= 10:
        badges.append({'name': '記録魔', 'icon': '📝', 'description': '10回の学習記録'})
    if total_records >= 50:
        badges.append({'name': '継続王', 'icon': '👑', 'description': '50回の学習記録'})
    
    # Roadmap completion badges
    completed_roadmaps = sum(1 for rm in roadmaps 
                           if all(m.get('completed', False) for m in rm.get('milestones', [])))
    if completed_roadmaps >= 1:
        badges.append({'name': 'ゴールハンター', 'icon': '🏆', 'description': 'ロードマップ完了'})
    
    return badges

def get_motivational_message(records, streak, level_info):
    """Get appropriate motivational message based on user's progress"""
    messages = {
        'new_user': [
            '学習の旅を始めましょう！最初の一歩が最も大切です 🌟',
            'スキルアップの冒険が始まります！頑張って！ 💪',
            '継続は力なり。小さな積み重ねが大きな成果につながります 📈'
        ],
        'streak_praise': [
            f'素晴らしい！{streak}日連続で学習を続けています 🔥',
            f'{streak}日連続学習達成！この調子で続けましょう ⭐',
            f'連続{streak}日の学習、本当に素晴らしいです！ 🎉'
        ],
        'level_up': [
            f'レベル{level_info["level"]}に到達！さらなる高みを目指しましょう 🚀',
            f'レベルアップおめでとうございます！Lv.{level_info["level"]}の力を感じます ✨',
            f'新しいレベル{level_info["level"]}で新たな挑戦を始めましょう 🎯'
        ],
        'encouragement': [
            '今日も学習を頑張りましょう！小さな一歩が大きな変化を生みます 🌈',
            '成長は毎日の積み重ね。今日も自分に投資しましょう 💎',
            '学びは宝物。今日も新しい知識という宝を見つけましょう 🗝️'
        ]
    }
    
    import random
    
    if not records:
        return random.choice(messages['new_user'])
    elif streak >= 3:
        return random.choice(messages['streak_praise'])
    elif level_info['level'] >= 3:
        return random.choice(messages['level_up'])
    else:
        return random.choice(messages['encouragement'])

def generate_growth_chart_data(records):
    """Generate data for growth chart visualization"""
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    if not records:
        return {'labels': [], 'daily_time': [], 'cumulative_time': [], 'weekly_average': []}
    
    # Group records by date
    daily_time = defaultdict(int)
    for record in records:
        date = record.get('date', '')
        if date:
            daily_time[date] += get_time_value(record)
    
    # Get date range (last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=29)  # 30 days total
    
    labels = []
    daily_times = []
    cumulative_time = 0
    cumulative_times = []
    
    # Generate data for each day
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        date_label = current_date.strftime('%m/%d')
        
        daily_minutes = float(daily_time.get(date_str, 0))
        cumulative_time += daily_minutes
        
        labels.append(date_label)
        daily_times.append(daily_minutes)
        cumulative_times.append(cumulative_time)
        
        current_date += timedelta(days=1)
    
    # Calculate 7-day rolling average
    weekly_averages = []
    for i in range(len(daily_times)):
        start_idx = max(0, i - 6)  # Look back 7 days (including current)
        week_data = daily_times[start_idx:i+1]
        avg = sum(float(x) for x in week_data) / len(week_data) if week_data else 0.0
        weekly_averages.append(round(avg, 1))
    
    return {
        'labels': labels,
        'daily_time': daily_times,
        'cumulative_time': cumulative_times,
        'weekly_average': weekly_averages
    }

def get_learning_insights(records):
    """Generate insights about learning patterns"""
    if not records:
        return {'best_day': None, 'avg_session': 0, 'total_sessions': 0, 'improvement_trend': 'stable'}
    
    from collections import defaultdict
    import statistics
    
    # Analyze by day of week
    day_totals = defaultdict(list)
    for record in records:
        if record.get('date'):
            try:
                date_obj = datetime.strptime(record['date'], '%Y-%m-%d')
                day_name = date_obj.strftime('%A')
                day_totals[day_name].append(get_time_value(record))
            except:
                continue
    
    # Find best performing day
    best_day = None
    best_avg = 0
    day_names_jp = {
        'Monday': '月曜日', 'Tuesday': '火曜日', 'Wednesday': '水曜日',
        'Thursday': '木曜日', 'Friday': '金曜日', 'Saturday': '土曜日', 'Sunday': '日曜日'
    }
    
    for day, times in day_totals.items():
        if times:
            # Convert to float for statistics calculation
            float_times = [float(t) for t in times]
            avg = statistics.mean(float_times)
            if avg > best_avg:
                best_avg = avg
                best_day = day_names_jp.get(day, day)
    
    # Calculate session statistics
    total_sessions = len(records)
    # Convert to float for statistics calculation
    session_times = [float(get_time_value(r)) for r in records]
    avg_session = statistics.mean(session_times) if session_times else 0
    
    # Analyze recent trend (last 7 days vs previous 7 days)
    recent_records = sorted([r for r in records if r.get('date')], 
                          key=lambda x: x['date'], reverse=True)
    
    if len(recent_records) >= 7:
        recent_7 = sum(get_time_value(r) for r in recent_records[:7])
        previous_7 = sum(get_time_value(r) for r in recent_records[7:14]) if len(recent_records) >= 14 else 0
        
        if previous_7 > 0:
            if recent_7 > previous_7 * 1.1:
                trend = 'improving'
            elif recent_7 < previous_7 * 0.9:
                trend = 'declining'
            else:
                trend = 'stable'
        else:
            trend = 'improving' if recent_7 > 0 else 'stable'
    else:
        trend = 'stable'
    
    return {
        'best_day': best_day,
        'avg_session': round(avg_session, 1),
        'total_sessions': total_sessions,
        'improvement_trend': trend
    }

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
    records = query_user_records(get_table())
    roadmaps = query_user_records(get_roadmap_table())
    
    # Default values for error cases
    default_context = {
        'recent_records': [], 'understood_items': [], 'could_not_do_items': [],
        'week_total_time': 0, 'all_time_total': 0, 'total_days': 0, 'avg_time_per_day': 0,
        'streak': 0, 'level_info': {'level': 1, 'experience': 0, 'xp_current_level': 0, 
                                   'xp_for_next_level': 60, 'progress_percent': 0},
        'badges': [], 'motivational_message': '学習を始めましょう！ 🌟',
        'chart_data': {'labels': [], 'daily_time': [], 'cumulative_time': [], 'weekly_average': []},
        'insights': {'best_day': None, 'avg_session': 0, 'total_sessions': 0, 'improvement_trend': 'stable'}
    }
    
    if not records:
        return safe_render_template('dashboard.html', default_context)
    
    # Sort records by date and time
    records.sort(key=lambda x: (x.get('date', ''), x.get('created_at', '')), reverse=True)
    
    # Get recent items and memo insights
    recent_records = records[:10]
    understood_items = [r for r in records if r.get('understood', '').strip()][:5]
    could_not_do_items = [r for r in records if r.get('could_not_do', '').strip()][:5]
    
    # Calculate time statistics
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    week_records = [r for r in records if r.get('date', '') >= week_ago]
    stats = calculate_stats(records)
    
    # Calculate motivation features
    streak = calculate_learning_streak(records)
    level_info = calculate_experience_and_level(records)
    badges = get_achievement_badges(records, roadmaps)
    motivational_message = get_motivational_message(records, streak, level_info)
    
    # Generate chart data and insights
    chart_data = generate_growth_chart_data(records)
    insights = get_learning_insights(records)
    
    return render_template('dashboard.html',
                         recent_records=recent_records,
                         understood_items=understood_items,
                         could_not_do_items=could_not_do_items,
                         week_total_time=sum(get_time_value(r) for r in week_records),
                         all_time_total=stats['total_time'],
                         total_days=stats['total_days'],
                         avg_time_per_day=round(stats['avg_time_per_day'], 1),
                         streak=streak,
                         level_info=level_info,
                         badges=badges,
                         motivational_message=motivational_message,
                         chart_data=chart_data,
                         insights=insights)

@app.route('/add_record', methods=['GET', 'POST'])
def add_record():
    """Add a new study record with memo functionality"""
    roadmaps = query_user_records(get_roadmap_table())
    roadmaps.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    if request.method == 'POST':
        form_data = {
            'date': request.form.get('date'),
            'content': request.form.get('content'),
            'time': request.form.get('time'),
            'category': request.form.get('category', 'その他').strip()
        }
        
        # Validate required fields
        if not all([form_data['date'], form_data['content'], form_data['time'], form_data['category']]):
            flash('日付、内容、時間、カテゴリーは必須項目です。', 'error')
            return render_template('add_record.html', roadmaps=roadmaps)
        
        try:
            # Create record item
            item, record_id = create_record_item(
                form_data['content'], int(form_data['time']), form_data['category'],
                date=form_data['date'],
                could_not_do=request.form.get('could_not_do', '').strip(),
                understood=request.form.get('understood', '').strip(),
                roadmap_id=request.form.get('roadmap_id', '').strip(),
                milestone_id=request.form.get('milestone_id', '').strip()
            )
            
            get_table().put_item(Item=item)
            flash('学習記録が追加されました！', 'success')
            return redirect(url_for('dashboard'))
            
        except (ClientError, ValueError) as e:
            print(f"Error adding record: {e}")
            flash('データベースエラーが発生しました。', 'error')
    
    return render_template('add_record.html', roadmaps=roadmaps)

@app.route('/records')
def records():
    """Display all study records"""
    all_records = query_user_records(get_table())
    
    if not all_records:
        flash('データベースエラーが発生しました。', 'error')
        return render_template('records.html', records=[])
    
    # Sort records
    all_records.sort(key=lambda x: (x.get('date', ''), x.get('created_at', '')), reverse=True)
    
    # Calculate statistics
    stats = calculate_stats(all_records)
    memo_count = sum(1 for r in all_records 
                    if r.get('understood', '').strip() or r.get('could_not_do', '').strip())
    
    return render_template('records.html',
                         records=all_records,
                         total_time=stats['total_time'],
                         total_records=stats['total_records'],
                         total_days=stats['total_days'],
                         avg_time_per_session=round(stats['avg_time_per_session'], 1),
                         avg_time_per_day=round(stats['avg_time_per_day'], 1),
                         total_memos=memo_count)

@app.route('/memo_insights')
def memo_insights():
    """Display memo insights - things understood and things to work on"""
    records = query_user_records(get_table())
    
    if not records:
        flash('データベースエラーが発生しました。', 'error')
        return safe_render_template('memo_insights.html', {
            'understood_items': [], 'could_not_do_items': []
        })
    
    # Sort and filter memo items
    records.sort(key=lambda x: (x.get('date', ''), x.get('created_at', '')), reverse=True)
    understood_items = [r for r in records if r.get('understood', '').strip()]
    could_not_do_items = [r for r in records if r.get('could_not_do', '').strip()]
    
    return render_template('memo_insights.html',
                         understood_items=understood_items,
                         could_not_do_items=could_not_do_items)

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
    all_roadmaps = query_user_records(get_roadmap_table())
    
    if not all_roadmaps:
        flash('データベースエラーが発生しました。', 'error')
        return render_template('roadmaps.html', roadmaps=[])
    
    # Sort and calculate progress
    all_roadmaps.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    for roadmap in all_roadmaps:
        milestones = roadmap.get('milestones', [])
        if milestones:
            completed = sum(1 for m in milestones if m.get('completed', False))
            roadmap['progress'] = int((completed / len(milestones)) * 100)
        else:
            roadmap['progress'] = 0
    
    return render_template('roadmaps.html', roadmaps=all_roadmaps)

@app.route('/roadmap/<roadmap_id>')
def view_roadmap(roadmap_id):
    """View a specific roadmap"""
    roadmap = get_roadmap_by_id(roadmap_id)
    if not roadmap:
        flash('ロードマップが見つかりません。', 'error')
        return redirect(url_for('roadmaps'))
    
    # Get related study records
    all_records = query_user_records(get_table())
    related_records = [r for r in all_records if r.get('roadmap_id') == roadmap_id]
    
    # Calculate milestone statistics and overall progress
    milestone_stats = calculate_milestone_stats(roadmap, related_records)
    progress_data = calculate_roadmap_progress(roadmap, related_records)
    
    # Update roadmap with calculated data
    roadmap.update(progress_data)
    roadmap['related_records_count'] = len(related_records)
    
    return render_template('roadmap_detail.html',
                         roadmap=roadmap,
                         milestone_stats=milestone_stats,
                         related_records=related_records[:10])

@app.route('/add_roadmap', methods=['GET', 'POST'])
def add_roadmap():
    """Add a new learning roadmap"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('タイトルは必須項目です。', 'error')
            return render_template('add_roadmap.html')
        
        # Create roadmap
        roadmap_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        milestones = parse_milestone_form_data()
        
        roadmap_data = {
            'user_id': DEFAULT_USER_ID,
            'roadmap_id': roadmap_id,
            'title': title,
            'description': request.form.get('description', '').strip(),
            'goal': request.form.get('goal', '').strip(),
            'milestones': milestones,
            'created_at': datetime.now().isoformat(),
            'status': 'active'
        }
        
        try:
            get_roadmap_table().put_item(Item=roadmap_data)
            flash('ロードマップが作成されました！', 'success')
            return redirect(url_for('view_roadmap', roadmap_id=roadmap_id))
        except ClientError as e:
            print(f"Error adding roadmap: {e}")
            flash('ロードマップの作成中にエラーが発生しました。', 'error')
    
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
                    'estimated_hours': int(milestone_durations[i]) if i < len(milestone_durations) and milestone_durations[i].isdigit() else 8,
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
    # Get URL parameters
    roadmap_id = request.args.get('roadmap_id', '')
    milestone_id = request.args.get('milestone_id', '')
    
    # Get roadmaps for selection
    roadmap_table = get_roadmap_table()
    roadmaps = []
    selected_roadmap = None
    selected_milestone = None
    
    try:
        response = roadmap_table.query(
            KeyConditionExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': DEFAULT_USER_ID}
        )
        roadmaps = response.get('Items', [])
        roadmaps.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Find selected roadmap and milestone if provided
        if roadmap_id:
            for roadmap in roadmaps:
                if roadmap.get('roadmap_id') == roadmap_id:
                    selected_roadmap = roadmap
                    if milestone_id:
                        for milestone in roadmap.get('milestones', []):
                            if milestone.get('id') == milestone_id:
                                # Ensure estimated_hours exists
                                if 'estimated_hours' not in milestone:
                                    milestone['estimated_hours'] = 1
                                selected_milestone = milestone
                                break
                    break
                    
    except ClientError as e:
        print(f"Error getting roadmaps: {e}")
    
    return render_template('timer.html', 
                         roadmaps=roadmaps,
                         selected_roadmap=selected_roadmap,
                         selected_milestone=selected_milestone,
                         roadmap_id=roadmap_id,
                         milestone_id=milestone_id)

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
        roadmap_id = data.get('roadmap_id', '').strip() if data else ''
        milestone_id = data.get('milestone_id', '').strip() if data else ''
        
        print(f"Parsed - content: '{content}', time: {time_minutes}")  # Debug log
        
        if not content or time_minutes <= 0:
            return {'error': f'Invalid data - content: "{content}", time: {time_minutes}'}, 400
        
        # Create record item using helper function
        item, record_id = create_record_item(
            content, time_minutes, category,
            could_not_do=could_not_do,
            understood=understood,
            roadmap_id=roadmap_id,
            milestone_id=milestone_id,
            source='timer'
        )
        
        get_table().put_item(Item=item)
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
    records = query_user_records(get_table())
    today = datetime.now().strftime('%Y-%m-%d')
    today_records = [r for r in records if r.get('date') == today]
    
    return {
        'total_time_minutes': sum(get_time_value(r) for r in today_records),
        'session_count': len(today_records)
    }

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

@app.route('/import_roadmap_csv', methods=['GET', 'POST'])
def import_roadmap_csv():
    """Import roadmap from CSV file"""
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('ファイルが選択されていません。', 'error')
            return redirect(request.url)
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('ファイルが選択されていません。', 'error')
            return redirect(request.url)
        
        if not file.filename.endswith('.csv'):
            flash('CSVファイルを選択してください。', 'error')
            return redirect(request.url)
        
        try:
            # Read CSV file with multiple encoding support
            file_bytes = file.stream.read()
            print(f"File size: {len(file_bytes)} bytes")
            
            # Try different encodings
            encodings = ['utf-8', 'utf-8-sig', 'shift_jis', 'cp932']
            file_content = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    file_content = file_bytes.decode(encoding)
                    used_encoding = encoding
                    print(f"Successfully decoded with {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            
            if file_content is None:
                raise ValueError("Could not decode file with any supported encoding")
            
            print(f"CSV file content (first 200 chars): {file_content[:200]}")
            
            stream = io.StringIO(file_content, newline=None)
            csv_input = csv.DictReader(stream)
            
            print(f"CSV headers: {csv_input.fieldnames}")
            
            roadmaps_created = 0
            current_roadmap = None
            current_milestones = []
            
            row_count = 0
            for row in csv_input:
                row_count += 1
                print(f"Processing row {row_count}: {row}")
                
                # Skip empty rows
                if not any(row.values()):
                    print("Skipping empty row")
                    continue
                
                # Extract data from row
                title = row.get('ロードマップタイトル', '').strip()
                description = row.get('説明', '').strip()
                goal = row.get('目標', '').strip()
                milestone_title = row.get('マイルストーンタイトル', '').strip()
                milestone_description = row.get('マイルストーン説明', '').strip()
                estimated_hours_str = row.get('推定時間', '8').strip()
                
                print(f"Extracted data - title: '{title}', milestone: '{milestone_title}'")
                
                # Parse estimated hours
                try:
                    estimated_hours = int(estimated_hours_str) if estimated_hours_str.isdigit() else 8
                except (ValueError, AttributeError):
                    estimated_hours = 8
                
                # If we have a new roadmap title, save the previous one and start new
                if title and (current_roadmap is None or current_roadmap['title'] != title):
                    print(f"New roadmap detected: '{title}'")
                    # Save previous roadmap if it exists
                    if current_roadmap is not None:
                        print(f"Saving previous roadmap: '{current_roadmap['title']}' with {len(current_milestones)} milestones")
                        save_roadmap_from_csv(current_roadmap, current_milestones)
                        roadmaps_created += 1
                        print(f"Roadmaps created so far: {roadmaps_created}")
                    
                    # Start new roadmap
                    print(f"Starting new roadmap: '{title}'")
                    current_roadmap = {
                        'title': title,
                        'description': description,
                        'goal': goal
                    }
                    current_milestones = []
                
                # Add milestone to current roadmap
                if milestone_title:
                    if current_roadmap is not None:
                        print(f"Adding milestone '{milestone_title}' to roadmap '{current_roadmap['title']}'")
                        current_milestones.append({
                            'title': milestone_title,
                            'description': milestone_description,
                            'estimated_hours': estimated_hours
                        })
                        print(f"Total milestones in current roadmap: {len(current_milestones)}")
                    else:
                        print(f"Milestone '{milestone_title}' found but no current roadmap! Creating one.")
                        # Create roadmap from milestone
                        current_roadmap = {
                            'title': milestone_title,
                            'description': '',
                            'goal': ''
                        }
                        current_milestones = [{
                            'title': milestone_title,
                            'description': milestone_description,
                            'estimated_hours': estimated_hours
                        }]
                        print(f"Created roadmap from milestone: '{milestone_title}'")
            
            print(f"Finished processing {row_count} rows")
            print(f"Current roadmap at end: {current_roadmap}")
            print(f"Current milestones count: {len(current_milestones) if current_milestones else 0}")
            
            # Save the last roadmap
            if current_roadmap is not None:
                print(f"Saving final roadmap: '{current_roadmap['title']}' with {len(current_milestones)} milestones")
                save_roadmap_from_csv(current_roadmap, current_milestones)
                roadmaps_created += 1
                print(f"Final roadmaps created: {roadmaps_created}")
            else:
                print("No roadmap to save at the end")
            
            if roadmaps_created > 0:
                flash(f'{roadmaps_created}個のロードマップがインポートされました！', 'success')
            else:
                flash('インポートできるロードマップが見つかりませんでした。', 'warning')
            
            return redirect(url_for('roadmaps'))
            
        except Exception as e:
            print(f"Error importing CSV: {e}")
            flash(f'CSVインポート中にエラーが発生しました: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('import_roadmap_csv.html')

def save_roadmap_from_csv(roadmap_data, milestones_data):
    """Helper function to save roadmap from CSV data"""
    try:
        roadmap_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        created_at = datetime.now().isoformat()
        
        milestones = []
        for milestone_data in milestones_data:
            milestones.append({
                'id': str(uuid.uuid4())[:8],
                'title': milestone_data['title'],
                'description': milestone_data['description'],
                'estimated_hours': milestone_data['estimated_hours'],
                'completed': False,
                'completed_date': None
            })
        
        table = get_roadmap_table()
        item = {
            'user_id': DEFAULT_USER_ID,
            'roadmap_id': roadmap_id,
            'title': roadmap_data['title'],
            'description': roadmap_data['description'],
            'goal': roadmap_data['goal'],
            'milestones': milestones,
            'created_at': created_at,
            'status': 'active',
            'source': 'csv_import'
        }
        
        table.put_item(Item=item)
        print(f"Successfully saved roadmap: {roadmap_data['title']}")
        
    except Exception as e:
        print(f"Error saving roadmap: {e}")
        raise

@app.route('/download_roadmap_sample_csv')
def download_roadmap_sample_csv():
    """Download sample CSV for roadmap import"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ロードマップタイトル', '説明', '目標', 'マイルストーンタイトル', 'マイルストーン説明', '推定時間'])
    
    # Write sample data
    writer.writerow([
        'Pythonマスターへの道',
        'Pythonを基礎から応用まで体系的に学習する',
        'Pythonで実用的なアプリケーションを開発できるようになる',
        'Python基礎文法',
        '変数、データ型、制御構文などの基本を学ぶ',
        '20'
    ])
    writer.writerow([
        '',  # Same roadmap
        '',
        '',
        'オブジェクト指向プログラミング',
        'クラス、継承、ポリモーフィズムを理解する',
        '30'
    ])
    writer.writerow([
        '',  # Same roadmap
        '',
        '',
        'Webフレームワーク入門',
        'FlaskまたはDjangoでWebアプリを作る',
        '40'
    ])
    writer.writerow([
        '機械学習入門',
        '機械学習の基礎から実践まで学ぶ',
        'scikit-learnで機械学習モデルを構築できるようになる',
        '数学基礎',
        '線形代数、統計学の基礎を復習',
        '25'
    ])
    writer.writerow([
        '',  # Same roadmap
        '',
        '',
        '機械学習アルゴリズム',
        '主要なアルゴリズムの理論と実装を学ぶ',
        '60'
    ])
    
    # Create response
    output.seek(0)
    csv_data = output.getvalue()
    
    response = Response(
        csv_data.encode('utf-8-sig'),  # UTF-8 with BOM for Excel
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=roadmap_sample_{datetime.now().strftime("%Y%m%d")}.csv',
            'Content-Type': 'text/csv; charset=utf-8-sig'
        }
    )
    
    return response

# Lambda環境での初期化制御
if not os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    # ローカル開発環境でのみinit_dbを実行
    if dynamodb_endpoint:
        init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)