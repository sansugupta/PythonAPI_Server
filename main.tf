provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    dynamodb = "http://172.17.0.2:4566"
    s3       = "http://172.17.0.2:4566"
  }

  default_tags {
    tags = {
      Environment = "local"
    }
  }
}

resource "aws_dynamodb_table" "users" {
  name         = "users"
  billing_mode = "PROVISIONED"
  read_capacity  = 1
  write_capacity = 1
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

resource "aws_s3_bucket" "avatars" {
  bucket = "prima-tech-challenge"
}

