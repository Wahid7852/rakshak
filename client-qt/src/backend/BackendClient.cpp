#include <rakshak/backend/BackendClient.h>
#include <rakshak/LogMonitor.h>

using rakshak::backend::ApiClient;
using rakshak::backend::LogScanResult;

namespace {
constexpr int kHealthPollMs = 5000;
}

BackendClient::BackendClient(QObject* parent)
    : QObject(parent), m_api(new ApiClient(this)) {
    connect(&m_healthTimer, &QTimer::timeout, m_api, &ApiClient::checkHealth);
    connect(m_api, &ApiClient::healthChecked, this, &BackendClient::backendHealthChanged);

    m_logMonitor = std::make_unique<LogMonitor>();

    connect(m_logMonitor.get(), &LogMonitor::newLogEntry, this, [this](const QString& line) {
        emit rawLogLine(line);
        m_api->scanLogLine(line, QString(kContext));
    });

    connect(m_logMonitor.get(), &LogMonitor::error, this, [this](const QString& message) {
        emit monitoringStatusChanged(QStringLiteral("log error: %1").arg(message));
    });

    connect(m_logMonitor.get(), &LogMonitor::processingStats, this, [this](int eps, double /*cpu*/) {
        emit logThroughput(eps);
    });

    connect(m_api, &ApiClient::logScanResult, this,
            [this](const QString& context, const QString& line, const LogScanResult& verdict) {
                if (context != QLatin1String(kContext)) return;
                emit logVerdictReady(line, verdict);
            });
    connect(m_api, &ApiClient::logScanError, this,
            [this](const QString& context, const QString& line, const QString& message) {
                if (context != QLatin1String(kContext)) return;
                emit logVerdictFailed(line, message);
            });
}

BackendClient::~BackendClient() {
    stop();
}

void BackendClient::start() {
    m_api->checkHealth();
    m_healthTimer.start(kHealthPollMs);
}

void BackendClient::stop() {
    m_healthTimer.stop();
    stopMonitoring();
}

void BackendClient::startMonitoring(const QString& logPath) {
    m_logMonitor->startMonitoring(logPath);
    emit monitoringStatusChanged(QStringLiteral("monitoring started"));
}

void BackendClient::stopMonitoring() {
    if (m_logMonitor) m_logMonitor->stopMonitoring();
    emit monitoringStatusChanged(QStringLiteral("monitoring stopped"));
}

void BackendClient::setFeatureExtraction(bool enabled) {
    if (m_logMonitor) m_logMonitor->setFeatureExtractionMode(enabled);
}
