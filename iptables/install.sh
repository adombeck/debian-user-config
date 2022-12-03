#!/bin/sh

set -x
set -eu

# Drop incoming connections by default
sudo iptables -P INPUT DROP
sudo ip6tables -P INPUT DROP
sudo iptables -P FORWARD DROP
sudo ip6tables -P FORWARD DROP

# Accept on localhost
sudo iptables -A INPUT -i lo -j ACCEPT
sudo ip6tables -A INPUT -i lo -j ACCEPT

# Allow established sessions to receive traffic
sudo iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
sudo ip6tables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Drop invalid packets
sudo iptables -A INPUT -m conntrack --ctstate INVALID -j DROP
sudo ip6tables -A INPUT -m conntrack --ctstate INVALID -j DROP

# Save the iptables rules
sudo iptables-save  -f /etc/iptables/rules.v4
sudo ip6tables-save  -f /etc/iptables/rules.v6

