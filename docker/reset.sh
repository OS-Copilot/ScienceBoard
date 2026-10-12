#!/usr/bin/env bash
# A new container already has a fresh network namespace.  The VMware guest
# reset bounced NetworkManager to refresh NAT; doing that in Docker would only
# disconnect the task container.
exit 0
