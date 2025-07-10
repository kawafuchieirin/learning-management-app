# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Learning Management Application (学習記録管理アプリ) built with Flask and DynamoDB Local. It tracks study sessions with memos for understanding and challenges.

## Key Commands

### Setup and Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start DynamoDB Local (automated setup)
python setup_dynamodb.py

# Start Flask application (in a new terminal)
python app.py
```

The application runs at http://localhost:5000 with debug mode enabled.

### DynamoDB Local Manual Start

```bash
cd dynamodb_local
java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb -port 8000
```

## Architecture Overview

### Core Application Structure

The entire application logic resides in `app.py`, which handles:
- Flask routes and request handling
- DynamoDB table operations via boto3
- Session management and flash messages
- Data validation and error handling

### Database Design

**DynamoDB Table: `study_records`**
- Partition Key: `user_id` (String)
- Sort Key: `record_id` (String - timestamp + UUID)
- Attributes: date, content, time, could_not_do, understood, created_at

### Key Routes

1. `/` - Dashboard with recent records and statistics
2. `/add_record` - Form for adding new study records
3. `/records` - Display all study records
4. `/memo_insights` - View memo highlights (understood/challenges)

### Frontend Architecture

- Templates use Jinja2 with base template inheritance (`base.html`)
- Bootstrap 5 for responsive design
- Font Awesome for icons
- Japanese language interface throughout

## Development Considerations

### DynamoDB Local vs Production

The app uses DynamoDB Local for development. For AWS deployment, modify the boto3 resource configuration in `app.py:12-18` by removing `endpoint_url` and updating credentials.

### Error Handling

All DynamoDB operations are wrapped in try-except blocks to handle `ClientError`. Flash messages provide user feedback for all operations.

### Data Flow

1. User submits form data
2. Flask validates and processes input
3. Data stored in DynamoDB with generated `record_id`
4. Success/error feedback via flash messages
5. Redirect to appropriate view

### Session Management

Uses Flask's built-in session management with a secret key. Currently supports a single user (`default_user`).

## Important Notes

- No test suite exists - testing would need to be added
- No linting or type checking configuration
- Single-user application (multi-user support would require auth implementation)
- All datetime operations use local timezone
- DynamoDB Local requires Java 8+