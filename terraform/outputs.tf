output "execution_role_arn" {
  description = "The ARN of the IAM Role the application should assume"
  value       = aws_iam_role.food_agent_exec_role.arn
}

output "execution_role_name" {
  description = "The Name of the IAM Role the application should assume"
  value       = aws_iam_role.food_agent_exec_role.name
}
