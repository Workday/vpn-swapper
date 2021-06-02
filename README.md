# VPN Swapper

A fire and forget command-line tool to allow for easy transitions of VPN
connections between a pool of AWS machines.

## Dependencies

* `poetry` - Recommended installation via `pip`
* `wireguard-tools` - Recommended installation via `brew`
* `awscli` - Recommended installation via `brew`
* `terraform` - Recommended installation via `brew`

## Setup

1. Make sure to setup an AWS profile in `awscli` that has the following
   security policy attached: `AmazonEC2FullAccess`

2. Setup a `config.json` file in `~/.vpn-swapper`. An example can be found in
   `config.json.example`.

3. Run the following commands to set up terraform:
```
cd infra
terraform init
terraform plan -out theplan
terraform apply theplan
```

NOTE: When running `terraform plan -out theplan` the variable for ingress ips need to be entered as an array of CIDR block strings. Ex: ["xxx.xxx.xxx.xxx/32"]

## Running

Install dependencies:
```
poetry install
```

To connect to a VPN (or switch to a new VPN):
```
poetry run python3 -m vpn_swapper
```

## Shutting Down

To disconnect from all VPN's:
```
poetry run python3 -m vpn_swapper --terminate
```

To teardown AWS infrastructure:
```
terraform destroy
```

## Caveats
The VPN built here is designed for IPv4 only. **Make sure to disable IPv6 on any
machine you use this on or it will leak**



## Development

The build tools can be downloaded with
```
poetry install --dev
```

The code is linted with `flake8`, which can be run with
```
poetry run flake8
```

The code is tested with `pytest`, which can be run with
```
poetry run pytest -v
```
