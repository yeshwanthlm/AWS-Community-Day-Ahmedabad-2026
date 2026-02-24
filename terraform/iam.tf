# -----------------------------------------------------------------------------------
# Execution Role
# -----------------------------------------------------------------------------------
# This is the role that the application (running on ECS, EKS, Lambda, or EC2) will assume.
data "aws_caller_identity" "current" {}

resource "aws_iam_role" "food_agent_exec_role" {
  name = "${var.app_name}-${var.environment}-exec-role"

  # Trust relationships allow a compute service to assume this role.
  # Adjust this depending on your target compute platform (Lambda, ECS, etc).
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          # Example: Allow an ECS task to assume this role:
          Service = "ecs-tasks.amazonaws.com"
          # To allow local testing from your dev environment user:
          # AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------------
# Bedrock Foundation Models Policy
# -----------------------------------------------------------------------------------
resource "aws_iam_policy" "bedrock_model_invocation" {
  name        = "${var.app_name}-${var.environment}-bedrock-invoke-policy"
  description = "Allows invoking specific Bedrock models (Claude Haiku)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        # Principle of Least Privilege: Restrict to exactly the models used in food-agent.ipynb
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/us.anthropic.claude-3-5-haiku-20241022-v1:0",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/us.anthropic.claude-3-haiku-20240307-v1:0"
        ]
      }
    ]
  })
}
resource "aws_iam_role_policy_attachment" "attach_bedrock_invoke" {
  role       = aws_iam_role.food_agent_exec_role.name
  policy_arn = aws_iam_policy.bedrock_model_invocation.arn
}

# -----------------------------------------------------------------------------------
# Bedrock Memory Management Policy
# -----------------------------------------------------------------------------------
resource "aws_iam_policy" "bedrock_memory_management" {
  name        = "${var.app_name}-${var.environment}-bedrock-memory-policy"
  description = "Allows the agent to create and manage Bedrock AgentCore Memories"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:CreateMemory",
          "bedrock:GetMemory",
          "bedrock:ListMemories",
          "bedrock:UpdateMemory",
          "bedrock:DeleteMemory"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:memory/*"
      }
    ]
  })
}
resource "aws_iam_role_policy_attachment" "attach_bedrock_memory" {
  role       = aws_iam_role.food_agent_exec_role.name
  policy_arn = aws_iam_policy.bedrock_memory_management.arn
}

# -----------------------------------------------------------------------------------
# AgentCore Identity / STS Web Identity Federation Policy
# -----------------------------------------------------------------------------------
resource "aws_iam_policy" "sts_web_identity" {
  name        = "${var.app_name}-${var.environment}-sts-identity-policy"
  description = "Allows obtaining IAM JWT tokens using sts:GetWebIdentityToken for AgentCore Identity"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sts:GetWebIdentityToken",
          "sts:AssumeRoleWithWebIdentity"
        ]
        Resource = "*"
      }
    ]
  })
}
resource "aws_iam_role_policy_attachment" "attach_sts_identity" {
  role       = aws_iam_role.food_agent_exec_role.name
  policy_arn = aws_iam_policy.sts_web_identity.arn
}
