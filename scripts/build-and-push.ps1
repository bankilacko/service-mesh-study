$ErrorActionPreference = "Stop"

$services = @(
    @{
        Name = "api-service"
        Image = "bankilacko11/api-service:latest"
    },
    @{
        Name = "cpu-service"
        Image = "bankilacko11/cpu-service:latest"
    },
    @{
        Name = "db-service"
        Image = "bankilacko11/db-service:latest"
    }
)

foreach ($service in $services) {
    Write-Host ""
    Write-Host "=== $($service.Name) ===" -ForegroundColor Cyan

    Push-Location $service.Name

    try {
        Write-Host "Building $($service.Image)..."
        docker build -t $service.Image .

        if ($LASTEXITCODE -ne 0) {
            throw "Docker build failed for $($service.Name)"
        }

        Write-Host "Pushing $($service.Image)..."
        docker push $service.Image

        if ($LASTEXITCODE -ne 0) {
            throw "Docker push failed for $($service.Name)"
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "All images built and pushed successfully." -ForegroundColor Green