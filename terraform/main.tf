variable "my_ip" {
  description = "Your public IP in CIDR notation, e.g. 1.2.3.4/32"
  type        = string
}

variable "account_id" {
  description = "Your AWS account ID"
  type        = string
}

provider "aws" {
  region = "us-east-1"
}

# ── S3 bucket for durable data storage ──────────────────────────────────────

resource "aws_s3_bucket" "health_data" {
  bucket = "health-pipeline-data-tf-${var.account_id}"
}

# ── IAM role so EC2 can talk to S3 without embedded credentials ─────────────

resource "aws_iam_role" "ec2_role" {
  name = "health-pipeline-ec2-role-tf"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "s3_access" {
  name = "health-pipeline-s3-access"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.health_data.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.health_data.arn
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "health-pipeline-profile-tf"
  role = aws_iam_role.ec2_role.name
}

# ── Security group: SSH + app port locked to a single IP ────────────────────

resource "aws_security_group" "health_pipeline" {
  name        = "health-pipeline-sg-tf"
  description = "Health pipeline security group"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }

  ingress {
    description = "App"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ── EC2 instance ─────────────────────────────────────────────────────────────

resource "aws_instance" "health_pipeline" {
  ami                    = "ami-0de568ccf3b0080d9"
  instance_type          = "t3.micro"
  key_name               = "health-pipeline-key"
  vpc_security_group_ids = [aws_security_group.health_pipeline.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  # Install Docker and run the pipeline container on first boot
  user_data = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y docker
    service docker start
    usermod -aG docker ec2-user
    docker run -d -p 8080:8080 \
      -e S3_BUCKET=${aws_s3_bucket.health_data.bucket} \
      --name health-pipeline \
      --restart unless-stopped \
      health_pipeline || true
  EOF

  tags = {
    Name = "health-pipeline-tf"
  }
}

# ── Outputs ──────────────────────────────────────────────────────────────────

output "ec2_public_ip" {
  value = aws_instance.health_pipeline.public_ip
}

output "s3_bucket" {
  value = aws_s3_bucket.health_data.bucket
}
