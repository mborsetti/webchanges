#!/bin/sh
# Installs /crontab for user webchanges and runs busybox crond in the foreground, logging to the container's output.
set -e

echo "$(webchanges --version | head -n 1) container started at $(date)"
# Creates the default config.yaml and jobs.yaml if missing, and logs the jobs; a broken file is logged, not fatal
su webchanges -c 'webchanges --list' || true
crontab -u webchanges /crontab
exec crond -f -l 6
