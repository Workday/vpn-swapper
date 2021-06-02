variable "vpn-swapper-config" {
  default = "~/.vpn-swapper/config.json"
}

variable "instance-type" {
  default = "t2.micro"
}

variable "base-image-query" {
  default = "ubuntu/images/hvm-ssd/ubuntu-bionic-18.04-amd64-server-*"
}

variable "base-image-owner" {
  default = "099720109477" # Canonical
}

variable "ingress-ips" {
  # No default because we don't want to open stuff up to the world by default
  type = list(string)
}

variable "egress-ips" {
  type = list(string)
  default = ["0.0.0.0/0"]
}

variable "num-vpns" {
}
