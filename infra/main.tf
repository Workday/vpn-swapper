locals {
  vpn-swapper-config = jsondecode(file(pathexpand(var.vpn-swapper-config)))
}

provider "aws" {
  region  = local.vpn-swapper-config["region"]
  profile = local.vpn-swapper-config["profile"]
}

data "aws_ami" "ubuntu" {
    most_recent = true

    filter {
        name   = "name"
        values = [var.base-image-query]
    }

    filter {
        name   = "virtualization-type"
        values = ["hvm"]
    }

    owners = [var.base-image-owner]
}

resource "aws_default_vpc" "default" {}

data "aws_availability_zones" "available" {}

resource "aws_default_subnet" "default_az" {
  count = length(data.aws_availability_zones.available.names)
  availability_zone = data.aws_availability_zones.available.names[count.index]
}

resource "aws_security_group" "vpn-swapper-sg" {
  name = "vpn-swapper-sg"
  vpc_id = aws_default_vpc.default.id

  # Enable SSH for handshake
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ingress-ips
  }

  # Enable Wireguard
  ingress {
    from_port   = local.vpn-swapper-config["wg_port"]
    to_port     = local.vpn-swapper-config["wg_port"]
    protocol    = "udp"
    cidr_blocks = var.ingress-ips
  }

  # Allow the VPN to egress any port/protocol
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"  # This means any, this is a bad decision on terraform's part
    cidr_blocks = var.egress-ips
  }
}

resource "tls_private_key" "vpn-key-material" {
  algorithm = "RSA"
  rsa_bits = 4096
}

resource "aws_key_pair" "vpn-key" {
  key_name = "vpn-key"
  public_key = tls_private_key.vpn-key-material.public_key_openssh
}

resource "aws_kms_key" "vpn-kms-key" {
  description = "KMS key for VPN secrets in SSM"
}

resource "aws_ssm_parameter" "vpn-key-ssm" {
  name        = local.vpn-swapper-config["ssh_key_path"]
  description = "Private key to SSH into VPN hosts"
  type        = "SecureString"
  value       = tls_private_key.vpn-key-material.private_key_pem
  key_id      = aws_kms_key.vpn-kms-key.id

}

# Create Client IAM user

data "aws_caller_identity" "current" {}

resource "aws_iam_user" "user" {
  name = "vpnswap-user"

}
resource "aws_iam_policy" "policy" {
  name = "vpnswap-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
        "kms:Decrypt"
        ]
        Resource = format("arn:aws:kms:%s:%s:key/%s", local.vpn-swapper-config["region"],
        data.aws_caller_identity.current.account_id, aws_kms_key.vpn-kms-key.id)
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = format("arn:aws:ssm:%s:%s:parameter%s", local.vpn-swapper-config["region"],
        data.aws_caller_identity.current.account_id, local.vpn-swapper-config["ssh_key_path"])
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:TerminateInstances"
        ]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_user_policy_attachment" "policy-attach" {
  user       = aws_iam_user.user.name
  policy_arn = aws_iam_policy.policy.arn
}

resource "aws_iam_access_key" "vpnswap_key" {
  user = aws_iam_user.user.name
}

output "aws_iam_credentials" {
  value = aws_iam_access_key.vpnswap_key
}

module "vpn-asg" {
  source = "terraform-aws-modules/autoscaling/aws"
  version = "~> 3.0"

  name = "vpn-asg"

  # Launch Configuration details
  lc_name                     = "vpn-lc"
  image_id                    = data.aws_ami.ubuntu.id
  instance_type               = var.instance-type
  security_groups             = [aws_security_group.vpn-swapper-sg.id]
  associate_public_ip_address = true
  key_name                    = aws_key_pair.vpn-key.key_name
  root_block_device           = [{encrypted = true}]

  # Autoscaling details
  asg_name                  = "vpn-asg"
  vpc_zone_identifier       = aws_default_subnet.default_az[*].id
  health_check_type         = "EC2"
  health_check_grace_period = 120
  min_size                  = var.num-vpns
  max_size                  = var.num-vpns
  desired_capacity          = var.num-vpns
  wait_for_capacity_timeout = 0

  # User Data
  user_data = templatefile("${path.module}/templates/user-data.sh",
    {
      wg-port = local.vpn-swapper-config["wg_port"]
    }
  )
}
