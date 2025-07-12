# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Learning Management Application (学習記録管理アプリ) built with Flask and DynamoDB Local. It tracks study sessions with memos for understanding and challenges, and includes learning roadmap functionality.

## Key Commands

### Setup and Development

```bash
# Install dependencies
pip install -r requirements.txt

# Setup DynamoDB Local (downloads and extracts automatically)
python setup_dynamodb.py

# Start both DynamoDB Local and Flask (recommended)
python run.py
# OR python start.py (alternative launcher)

# Start services individually (if needed)
python setup_dynamodb.py  # Terminal 1: DynamoDB Local
python app.py             # Terminal 2: Flask app
```

The application runs at http://localhost:5000 with debug mode enabled.
DynamoDB Local runs on port 8002.

### DynamoDB Local Manual Start

```bash
cd dynamodb_local
java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb -port 8002
```

## Architecture Overview

### Core Application Structure

The entire application logic resides in `app.py` (805 lines), which handles:
- Flask routes and request handling  
- DynamoDB table operations via boto3
- Session management and flash messages
- Data validation and error handling
- Two main data models: study records and learning roadmaps

### Database Design

**Primary Table: `study_records`**
- Partition Key: `user_id` (String)
- Sort Key: `record_id` (String - timestamp + UUID)
- Attributes: date, content, time, category, could_not_do, understood, created_at, source

**Secondary Table: `learning_roadmaps`**
- Partition Key: `user_id` (String)  
- Sort Key: `roadmap_id` (String - timestamp + UUID)
- Attributes: title, description, goal, milestones[], created_at, status

### Key Routes and Features

**Study Records:**
- `/` - Dashboard with recent records and statistics
- `/add_record` - Form for adding new study records
- `/records` - Display all study records with statistics
- `/memo_insights` - View memo highlights (understood/challenges)
- `/export_csv` - Export records to CSV
- `/timer` - Study timer with session tracking
- `/category_stats` - Category-wise statistics

**Learning Roadmaps:**
- `/roadmaps` - List all learning roadmaps
- `/roadmap/<id>` - View specific roadmap details
- `/add_roadmap` - Create new learning roadmap
- `/edit_roadmap/<id>` - Edit existing roadmap
- `/update_milestone/<roadmap_id>/<milestone_id>` - Update milestone completion
- `/delete_roadmap/<id>` - Delete roadmap

**API Endpoints:**
- `/api/today_stats` - Get today's study statistics
- `/save_timer_session` - Save study session from timer

### Frontend Architecture

- Templates use Jinja2 with base template inheritance (`base.html`)
- Bootstrap 5 for responsive design
- Font Awesome for icons
- JavaScript for interactive features (timer, milestone updates)
- Japanese language interface throughout
- 10 template files for different views

### Application Entry Points

Multiple startup scripts available:
- `app.py` - Direct Flask app launch
- `run.py` - Integrated launcher (DynamoDB + Flask)
- `start.py` - Simplified integrated launcher  
- `setup_dynamodb.py` - DynamoDB Local setup only

## Development Considerations

### DynamoDB Local vs Production

The app uses DynamoDB Local for development with port 8002. For AWS deployment, modify the boto3 resource configuration in `app.py:14-20` by removing `endpoint_url` and updating credentials.

### Error Handling

All DynamoDB operations are wrapped in try-except blocks to handle `ClientError`. Flash messages provide user feedback for all operations.

### Data Flow

1. User submits form data
2. Flask validates and processes input
3. Data stored in DynamoDB with generated unique IDs
4. Success/error feedback via flash messages
5. Redirect to appropriate view

### Session Management

Uses Flask's built-in session management with a secret key. Currently supports a single user (`default_user`).

### Code Organization

- All business logic in single `app.py` file
- Helper functions for table access (`get_table()`, `get_roadmap_table()`)
- Database initialization in `init_db()` function
- Consistent error handling patterns throughout

## Important Notes

- No test suite exists - testing would need to be added
- No linting or type checking configuration
- Single-user application (multi-user support would require auth implementation)
- All datetime operations use local timezone
- DynamoDB Local requires Java 8+
- Port 8002 is used for DynamoDB Local (not 8000)