$output = "nexora_core_code.txt"

if (Test-Path $output) { Remove-Item $output -Force }

@"
Nexora - Core Source Code Only
Generated on: $(Get-Date)
========================================

"@ | Out-File -FilePath $output -Encoding utf8

# الملفات والمجلدات اللي هنأخدها فقط
$includePaths = @(
    "app",
    "requirements",
    "docker",
    ".env.example",
    "pyproject.toml",
    "docker-compose.yml",
    "docker-compose.dev.yml",
    "webcam.py"
)

$files = @()

foreach ($path in $includePaths) {
    if (Test-Path $path) {
        if (Test-Path $path -PathType Container) {
            $files += Get-ChildItem -Path $path -Recurse -File | Where-Object {
                $_.Extension -match '\.(py|txt|yml|yaml|toml|html|css|js|ini)$' -and
                $_.Name -ne ".env"
            }
        } else {
            $files += Get-Item $path
        }
    }
}

foreach ($file in $files) {
    $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)

    @"

===== FILE: $relativePath =====

"@ | Out-File -FilePath $output -Append -Encoding utf8

    try {
        Get-Content -Path $file.FullName -Raw -Encoding utf8 | Out-File -FilePath $output -Append -Encoding utf8
    } catch {}

    @"

===== END FILE: $relativePath =====

"@ | Out-File -FilePath $output -Append -Encoding utf8
}

Write-Host "`nتم إنشاء الملف: $output" -ForegroundColor Green
Write-Host