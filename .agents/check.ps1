$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$checks = @(
    @{ name = 'detect_stack'; script = 'skills/init/detect_stack.py'; arguments = @('--project-root', $repositoryRoot) },
    @{ name = 'design-doc'; script = 'skills/_shared/validate_doc.py'; arguments = @('--project-root', $repositoryRoot, '--contract', 'design-doc', '--file', '.agents/docs/DESIGN.md') },
    @{ name = 'state-doc'; script = 'skills/_shared/validate_doc.py'; arguments = @('--project-root', $repositoryRoot, '--contract', 'state-doc', '--file', '.agents/STATE.md') }
)
$results = @()
foreach ($check in $checks) {
    try {
        $scriptPath = Join-Path $PSScriptRoot $check.script
        $checkArguments = $check.arguments
        $outputLines = & uv run --no-project python -X utf8 $scriptPath @checkArguments
        $checkExitCode = $LASTEXITCODE
        $verdict = ($outputLines -join "`n") | ConvertFrom-Json
        $results += [pscustomobject]@{ name = $check.name; exit_code = $checkExitCode; verdict = $verdict }
    }
    catch {
        $results += [pscustomobject]@{ name = $check.name; exit_code = 1; verdict = @{ ok = $false; error = $_.Exception.Message } }
    }
}
$allPassed = @($results | Where-Object { $_.exit_code -ne 0 -or $_.verdict.ok -ne $true }).Count -eq 0
[pscustomobject]@{ ok = $allPassed; checks = $results } | ConvertTo-Json -Depth 12
if ($allPassed) { exit 0 }
exit 2
