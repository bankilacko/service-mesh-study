param(
    [string]$Scenario = "health",
    [int]$VUs = 1,
    [string]$Duration = "10s",
    [string]$BaseUrl = "http://152.66.245.139:22290",
    [ValidateSet("enabled", "disabled", "unknown", "not-applicable")]
    [string]$Mesh = "unknown",
    [string]$PrometheusUrl = "http://152.66.245.139:22293"
)

$ErrorActionPreference = "Stop"

# Projekt gyökérkönyvtára
$ProjectRoot = Split-Path -Parent $PSScriptRoot

# k6 szcenárió
$ScenarioFile = Join-Path $PSScriptRoot "scenarios/$Scenario.js"

if (-not (Test-Path $ScenarioFile)) {
    throw "Nem található a k6-szcenárió: $ScenarioFile"
}

# Eredménymappa létrehozása
$Timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$ResultDir = Join-Path $ProjectRoot "results/$Timestamp"

New-Item -ItemType Directory -Path $ResultDir -Force |
    Out-Null

$MetadataPath = Join-Path $ResultDir "metadata.json"
$SummaryPath = Join-Path $ResultDir "k6-summary.json"
$MetricsPath = Join-Path $ResultDir "prometheus-metrics.json"

# Mérési metaadatok
$Metadata = [ordered]@{
    test_id            = $Timestamp
    scenario           = $Scenario
    base_url           = $BaseUrl
    vus                = $VUs
    duration           = $Duration
    service_mesh       = $Mesh
    started_at         = (Get-Date).ToString("o")
    test_started_at    = $null
    test_finished_at   = $null
    finished_at        = $null
    status             = "running"
    prometheus_status  = "pending"
}

$Metadata |
    ConvertTo-Json -Depth 10 |
    Set-Content -Path $MetadataPath -Encoding utf8

Write-Host ""
Write-Host "Scenario:   $Scenario"
Write-Host "VUs:        $VUs"
Write-Host "Duration:   $Duration"
Write-Host "Mesh:       $Mesh"
Write-Host "Results:    $ResultDir"
Write-Host ""

# Prometheus által lekérdezendő idősorok.
# Az app_* kizárólag az alkalmazáskonténert méri.
# A pod_* a pod összes nem üres, nem POD konténerét összegzi.
$Queries = [ordered]@{
    api_app_cpu_mcpu = 'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"api-service-.*",container="api-service"}[1m])) * 1000'
    api_pod_cpu_mcpu = 'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"api-service-.*",container!="",container!="POD"}[1m])) * 1000'
    api_app_memory_mib = 'sum(container_memory_working_set_bytes{namespace="default",pod=~"api-service-.*",container="api-service"}) / 1024 / 1024'
    api_pod_memory_mib = 'sum(container_memory_working_set_bytes{namespace="default",pod=~"api-service-.*",container!="",container!="POD"}) / 1024 / 1024'

    cpu_app_cpu_mcpu = 'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"cpu-service-.*",container="cpu-service"}[1m])) * 1000'
    cpu_pod_cpu_mcpu = 'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"cpu-service-.*",container!="",container!="POD"}[1m])) * 1000'
    cpu_app_memory_mib = 'sum(container_memory_working_set_bytes{namespace="default",pod=~"cpu-service-.*",container="cpu-service"}) / 1024 / 1024'
    cpu_pod_memory_mib = 'sum(container_memory_working_set_bytes{namespace="default",pod=~"cpu-service-.*",container!="",container!="POD"}) / 1024 / 1024'

    db_app_cpu_mcpu = 'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"db-service-.*",container="db-service"}[1m])) * 1000'
    db_pod_cpu_mcpu = 'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"db-service-.*",container!="",container!="POD"}[1m])) * 1000'
    db_app_memory_mib = 'sum(container_memory_working_set_bytes{namespace="default",pod=~"db-service-.*",container="db-service"}) / 1024 / 1024'
    db_pod_memory_mib = 'sum(container_memory_working_set_bytes{namespace="default",pod=~"db-service-.*",container!="",container!="POD"}) / 1024 / 1024'

    postgres_app_cpu_mcpu = 'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"postgres-.*",container="postgres"}[1m])) * 1000'
    postgres_pod_cpu_mcpu = 'sum(rate(container_cpu_usage_seconds_total{namespace="default",pod=~"postgres-.*",container!="",container!="POD"}[1m])) * 1000'
    postgres_app_memory_mib = 'sum(container_memory_working_set_bytes{namespace="default",pod=~"postgres-.*",container="postgres"}) / 1024 / 1024'
    postgres_pod_memory_mib = 'sum(container_memory_working_set_bytes{namespace="default",pod=~"postgres-.*",container!="",container!="POD"}) / 1024 / 1024'
}

$PreviousBaseUrl = $env:BASE_URL
$TestExitCode = 1
$TestStartUnix = $null
$MetricsStartUnix = $null

try {
    # A config.js ezen a környezeti változón keresztül kapja a címet.
    $env:BASE_URL = $BaseUrl

    # A Prometheus-idősorban a teszt előtti 60 másodpercet is lekérjük.
    $Metadata.test_started_at = (Get-Date).ToString("o")
    $TestStartUnix = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $MetricsStartUnix = $TestStartUnix - 60

    # k6 teszt futtatása
    & k6 run `
        --vus $VUs `
        --duration $Duration `
        --summary-export $SummaryPath `
        $ScenarioFile

    if ($null -ne $LASTEXITCODE) {
        $TestExitCode = [int]$LASTEXITCODE
    }

    if ($TestExitCode -eq 0) {
        $Metadata.status = "completed"
    }
    else {
        $Metadata.status = "failed"
        $Metadata.error = "A k6 kilépési kódja: $TestExitCode"
        Write-Warning $Metadata.error
    }
}
catch {
    $TestExitCode = 1
    $Metadata.status = "failed"
    $Metadata.error = $_.Exception.Message

    Write-Warning "A k6 futtatása sikertelen: $($_.Exception.Message)"
}
finally {
    $Metadata.test_finished_at = (Get-Date).ToString("o")

    # Az eredeti BASE_URL környezeti változó visszaállítása
    if ($null -eq $PreviousBaseUrl) {
        Remove-Item Env:BASE_URL -ErrorAction SilentlyContinue
    }
    else {
        $env:BASE_URL = $PreviousBaseUrl
    }
}

# Prometheus-idősorok lekérdezése
if ($null -ne $MetricsStartUnix) {
    $MetricsEndUnix = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $MetricResults = [ordered]@{}

    $MetricsOutput = [ordered]@{
        collection_status = "running"
        collected_at_utc  = $null
        window_start_unix = $MetricsStartUnix
        window_end_unix   = $MetricsEndUnix
        step              = "15s"
        metrics           = $MetricResults
    }

    try {
        foreach ($MetricName in $Queries.Keys) {
            Write-Host "Prometheus: $MetricName"

            $EncodedQuery = [uri]::EscapeDataString(
                $Queries[$MetricName]
            )

            $QueryUrl = "$($PrometheusUrl.TrimEnd('/'))/api/v1/query_range?query=$EncodedQuery&start=$MetricsStartUnix&end=$MetricsEndUnix&step=15s"

            $Response = Invoke-RestMethod `
                -Uri $QueryUrl `
                -Method Get `
                -TimeoutSec 30

            if ($Response.status -ne "success") {
                throw "A Prometheus-lekérdezés sikertelen: $MetricName"
            }

            $MetricResults[$MetricName] = [ordered]@{
                promql      = $Queries[$MetricName]
                result_type = $Response.data.resultType
                result      = $Response.data.result
            }
        }

        $MetricsOutput.collection_status = "completed"
        $Metadata.prometheus_status = "completed"
    }
    catch {
        $MetricsOutput.collection_status = "failed"
        $MetricsOutput.error = $_.Exception.Message
        $Metadata.prometheus_status = "failed"
        $Metadata.prometheus_error = $_.Exception.Message

        Write-Warning "A Prometheus-adatok mentése nem sikerült: $($_.Exception.Message)"
    }
    finally {
        $MetricsOutput.collected_at_utc =
            [DateTimeOffset]::UtcNow.ToString("o")

        $MetricsOutput |
            ConvertTo-Json -Depth 20 |
            Set-Content -Path $MetricsPath -Encoding utf8
    }
}
else {
    $Metadata.prometheus_status = "skipped"
}

# Metaadatok végleges mentése
$Metadata.finished_at = (Get-Date).ToString("o")

$Metadata |
    ConvertTo-Json -Depth 10 |
    Set-Content -Path $MetadataPath -Encoding utf8

Write-Host ""
Write-Host "k6 status:      $($Metadata.status)"
Write-Host "Prometheus:     $($Metadata.prometheus_status)"
Write-Host "Results:        $ResultDir"
Write-Host "Summary:        $SummaryPath"
Write-Host "Metadata:       $MetadataPath"
Write-Host "Prometheus data: $MetricsPath"

if ($TestExitCode -ne 0) {
    exit 1
}