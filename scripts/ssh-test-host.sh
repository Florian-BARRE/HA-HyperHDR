#!/usr/bin/env bash
# Sets up this machine as a fake HyperHDR host for the SSH live test (needs root):
# an OpenSSH server on port 2222, a user that may use sudo with its password,
# and a systemctl that only writes down what it was asked, then drops the
# session as a machine going down would. Nothing is powered off.
#   SSH_TEST_USER (hhpi), SSH_TEST_PASSWORD (hh-pass-1234), SSH_TEST_LOG (/tmp/hh-systemctl.log)
set -euo pipefail
user="${SSH_TEST_USER:-hhpi}"
password="${SSH_TEST_PASSWORD:-hh-pass-1234}"
log="${SSH_TEST_LOG:-/tmp/hh-systemctl.log}"

id "$user" > /dev/null 2>&1 || useradd -m -s /bin/bash "$user"
echo "$user:$password" | chpasswd
usermod -aG sudo "$user"

# First in sudo's secure_path: stands in for the real systemctl.
cat > /usr/local/sbin/systemctl <<SCRIPT
#!/bin/sh
echo "\$*" >> "$log"
chmod 666 "$log"
case "\$1" in poweroff|reboot) pkill -KILL -u "$user" ;; esac
SCRIPT
chmod 755 /usr/local/sbin/systemctl
: > "$log"
chmod 666 "$log"

mkdir -p /run/sshd
ssh-keygen -A > /dev/null
cat > /etc/ssh/sshd_config.d/hh-test.conf <<CONF
Port 2222
PasswordAuthentication yes
KbdInteractiveAuthentication no
UsePAM yes
CONF
pid=/run/sshd-hh-test.pid
if [ -f "$pid" ]; then kill "$(cat "$pid")" 2> /dev/null || true; fi
/usr/sbin/sshd -p 2222 -o PidFile="$pid"
for _ in $(seq 1 20); do
  (echo > /dev/tcp/127.0.0.1/2222) 2> /dev/null && exit 0
  sleep 0.5
done
echo "sshd did not start" >&2
exit 1
