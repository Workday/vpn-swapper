#!/bin/bash

apt-get update
apt-get install -y wireguard

sysctl -w net.ipv4.ip_forward=1

cat << EOF > /etc/wireguard/wg0.conf
[Interface]
Address = 10.73.31.1/24
SaveConfig = true
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
ListenPort = ${wg-port}
PrivateKey = $(wg genkey)
EOF

wg-quick up wg0
