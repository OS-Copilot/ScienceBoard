#!/bin/bash
pkill -f wxgui.py; pkill -f mapdisp; pkill -f /usr/lib/grass78; pkill -f update-notifier
gsettings set com.ubuntu.update-notifier no-show-notifications true 2>&1
gsettings set com.ubuntu.update-notifier regular-auto-launch-interval 0 2>&1
gsettings set org.gnome.software download-updates false 2>&1
gsettings set org.gnome.software allow-updates false 2>&1
printf 'APT::Periodic::Update-Package-Lists "0";\nAPT::Periodic::Download-Upgradeable-Packages "0";\nAPT::Periodic::AutocleanInterval "0";\nAPT::Periodic::Unattended-Upgrade "0";\n' > /tmp/20auto-upgrades
echo password | sudo -S -p '' cp /tmp/20auto-upgrades /etc/apt/apt.conf.d/20auto-upgrades
echo password | sudo -S -p '' systemctl disable --now apt-daily.timer apt-daily-upgrade.timer unattended-upgrades 2>&1 | tail -2
cat /etc/apt/apt.conf.d/20auto-upgrades; pgrep -af 'grass78|wxgui' | head -2; echo QUIET_DONE
