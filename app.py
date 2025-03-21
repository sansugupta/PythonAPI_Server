from flask import Flask, request, jsonify
import boto3
import os
import uuid

app = Flask(__name__)

# AWS Configuration
AWS_REGION = "us-east-1"
DYNAMODB_TABLE = "users"
S3_BUCKET = "prima-tech-challenge"

# Use LocalStack endpoint if running locally
LOCALSTACK_ENDPOINT = "http://172.17.0.2:4566"

# Set environment variables for dummy credentials (Required for LocalStack)
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

# Initialize AWS clients with LocalStack endpoint
dynamodb = boto3.client("dynamodb", region_name=AWS_REGION, endpoint_url=LOCALSTACK_ENDPOINT)
s3 = boto3.client("s3", region_name=AWS_REGION, endpoint_url=LOCALSTACK_ENDPOINT)

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

@app.route("/users", methods=["GET"])
def get_users():
    response = dynamodb.scan(TableName=DYNAMODB_TABLE)
    users = [{"id": item["id"]["S"], "name": item["name"]["S"], "email": item["email"]["S"], "avatar_url": item.get("avatar_url", {}).get("S", "")}
             for item in response.get("Items", [])]
    return jsonify(users)

@app.route("/user", methods=["POST"])
def create_user():
    user_id = str(uuid.uuid4())  # Generate unique ID

    if request.content_type == "application/json":
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        name = data.get("name")
        email = data.get("email")
        avatar_url = ""  # Default empty avatar URL if no file is uploaded

    else:  # Handle multipart/form-data (File Upload)
        name = request.form.get("name")
        email = request.form.get("email")

        if "avatar" in request.files:
            file = request.files["avatar"]
            file_ext = file.filename.split(".")[-1]
            avatar_filename = f"{uuid.uuid4()}.{file_ext}"
            s3.upload_fileobj(file, S3_BUCKET, avatar_filename)
            avatar_url = f"http://localhost:4566/{S3_BUCKET}/{avatar_filename}"
        else:
            avatar_url = ""

    # Validate required fields
    if not name or not email:
        return jsonify({"error": "Missing 'name' or 'email'"}), 400

    # Save to DynamoDB
    try:
        dynamodb.put_item(
            TableName=DYNAMODB_TABLE,
            Item={
                "id": {"S": user_id},  # 🔹 Added Required ID Field
                "name": {"S": name},
                "email": {"S": email},
                "avatar_url": {"S": avatar_url}
            },
        )
        return jsonify({"message": "User created successfully", "id": user_id, "avatar_url": avatar_url}), 201

    except Exception as e:
        print("DynamoDB Error:", e)  # Log error
        return jsonify({"error": "Failed to save user", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

