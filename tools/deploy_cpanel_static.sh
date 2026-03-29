#!/usr/bin/env bash
set -euo pipefail

deploy_enabled="${DEPLOY_ENABLED:-false}"
source_dir="${DEPLOY_SOURCE_DIR:-web/dist}"
build_command="${DEPLOY_BUILD_COMMAND:-}"
cpanel_host="${CPANEL_HOST:-}"
cpanel_port="${CPANEL_PORT:-22}"
cpanel_username="${CPANEL_USERNAME:-}"
cpanel_target_path="${CPANEL_TARGET_PATH:-}"
cpanel_public_url="${CPANEL_PUBLIC_URL:-}"
ssh_private_key="${CPANEL_SSH_PRIVATE_KEY:-}"
ssh_known_hosts="${CPANEL_SSH_KNOWN_HOSTS:-}"

if [[ "$deploy_enabled" != "true" ]]; then
  echo "DEPLOY_ENABLED is not true for this environment yet; skipping deploy."
  exit 0
fi

all_connection_values_empty=true
for value in "$cpanel_host" "$cpanel_username" "$cpanel_target_path" "$ssh_private_key" "$ssh_known_hosts"; do
  if [[ -n "$value" ]]; then
    all_connection_values_empty=false
    break
  fi
done

if [[ "$all_connection_values_empty" == true ]]; then
  echo "Deployment configuration is not set for this environment yet; skipping deploy."
  exit 0
fi

required_names=(CPANEL_HOST CPANEL_USERNAME CPANEL_TARGET_PATH CPANEL_SSH_PRIVATE_KEY CPANEL_SSH_KNOWN_HOSTS)
required_values=("$cpanel_host" "$cpanel_username" "$cpanel_target_path" "$ssh_private_key" "$ssh_known_hosts")

missing_names=()
for index in "${!required_names[@]}"; do
  if [[ -z "${required_values[$index]}" ]]; then
    missing_names+=("${required_names[$index]}")
  fi
done

if (( ${#missing_names[@]} > 0 )); then
  echo "Partial deployment configuration detected. Missing: ${missing_names[*]}" >&2
  exit 1
fi

if [[ -n "$build_command" ]]; then
  echo "Running build command before deploy"
  bash -lc "$build_command"
fi

if [[ ! -d "$source_dir" ]]; then
  echo "Deploy source directory '$source_dir' was not found." >&2
  echo "Set DEPLOY_SOURCE_DIR to the built static site folder, or set DEPLOY_BUILD_COMMAND to create it." >&2
  exit 1
fi

key_file="$RUNNER_TEMP/cpanel_deploy_key"
known_hosts_file="$RUNNER_TEMP/cpanel_known_hosts"

printf '%s\n' "$ssh_private_key" > "$key_file"
chmod 600 "$key_file"
printf '%s\n' "$ssh_known_hosts" > "$known_hosts_file"
chmod 600 "$known_hosts_file"

ssh_cmd=(ssh -p "$cpanel_port" -i "$key_file" -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$known_hosts_file")

"${ssh_cmd[@]}" "$cpanel_username@$cpanel_host" "mkdir -p '$cpanel_target_path'"

rsync -az --delete \
  -e "ssh -p $cpanel_port -i $key_file -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$known_hosts_file" \
  "$source_dir/" "$cpanel_username@$cpanel_host:$cpanel_target_path/"

echo "Static site deployed to $cpanel_username@$cpanel_host:$cpanel_target_path"
if [[ -n "$cpanel_public_url" ]]; then
  echo "Public URL: $cpanel_public_url"
fi