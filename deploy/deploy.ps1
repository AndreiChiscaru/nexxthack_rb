param(
    [Parameter(Mandatory = $true)][string]$KeyPath,
    [string]$ServerHost = "ubuntu@158.180.47.250",
    [switch]$WithGame
)
$root = Split-Path $PSScriptRoot -Parent
$ssh = @("-i", $KeyPath, "-o", "StrictHostKeyChecking=accept-new")

function Check($step) { if ($LASTEXITCODE -ne 0) { throw "$step a esuat (exit $LASTEXITCODE)" } }

ssh @ssh $ServerHost "sudo mkdir -p /opt/extras && sudo chown ubuntu:ubuntu /opt/extras"; Check "mkdir"
scp @ssh -r "$root\app" "$root\static" "$root\data" "$root\deploy" "$root\requirements.txt" "$root\.env.example" "${ServerHost}:/opt/extras/"; Check "scp"
if (Test-Path "$root\.env") { scp @ssh "$root\.env" "${ServerHost}:/opt/extras/.env"; Check "scp .env" }
ssh @ssh $ServerHost "sed -i 's/\r$//' /opt/extras/deploy/*.sh /opt/extras/deploy/*.service /opt/extras/deploy/*.conf && bash /opt/extras/deploy/setup_server.sh 2>&1"; Check "setup_server.sh"

if ($WithGame) {
    ssh @ssh $ServerHost "rm -rf /opt/extras/raiffquest"; Check "clean game source"
    scp @ssh -r "$root\raiffquest" "${ServerHost}:/opt/extras/"; Check "scp raiffquest"
    ssh @ssh $ServerHost "bash /opt/extras/deploy/build_game.sh 2>&1 && bash /opt/extras/deploy/setup_tunnel.sh url"; Check "build_game.sh"
}
