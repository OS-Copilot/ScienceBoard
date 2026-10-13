#!/bin/bash
# Pin the OSWorld-web hostnames to the Mac's vmnet8 address inside the guest.
# The guest's DNS goes through the Mac's resolver, where a local proxy returns
# fake addresses (for example 2001:2::3c) for <app>.172.16.120.1.nip.io, so the
# sites were unreachable from the VM although the Mac itself resolved them.
set -u
HOST_IP=${1:-172.16.120.1}
SUFFIX=${2:-172.16.120.1.nip.io}
APPS="awsconsole budgetwise calendar careerlink cloudcrm dinogame eventix expenseflow formcraft glbviewer insurance-claim interfacinglinux mailhub overleaf overleaf-collab reviewsphere slidepuzzle streamview studio.streamview teamchat travelhubpro trippza vaultbank visaapplication wandb"
{
  echo "# osworld-web mock sites (vm_config/arm64/guest/hosts-mocksites.sh)"
  for a in $APPS; do echo "$HOST_IP $a.$SUFFIX"; done
} > /tmp/hosts-mocksites
echo password | sudo -S -p '' sed -i '/osworld-web mock sites/,$d' /etc/hosts
echo password | sudo -S -p '' sh -c 'cat /tmp/hosts-mocksites >> /etc/hosts'
getent hosts dinogame.$SUFFIX; curl -s -m 10 -o /dev/null -w "guest->dinogame http=%{http_code}\n" "http://dinogame.$SUFFIX/"; curl -s -m 10 -o /dev/null -w "guest->mailhub http=%{http_code}\n" "http://mailhub.$SUFFIX/"
echo HOSTS_DONE
