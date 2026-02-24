terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # NOTE: In production, configure remote state backend here.
  # backend "s3" {
  #   bucket         = "my-terraform-state-bucket"
  #   key            = "food-agent/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-lock"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = "FoodAgentCore"
      ManagedBy   = "Terraform"
    }
  }
}
