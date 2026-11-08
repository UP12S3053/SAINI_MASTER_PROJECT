# R23.5. Run this file. A skip is not a pass.
# Do not launch Open_Enrollment.bat or open_launcher.py.
Set-Location -LiteralPath (Split-Path -Parent $MyInvocation.MyCommand.Path)
py -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output "STOP: Teacher Trial NOT AUTHORIZED. Production NOT APPROVED."
