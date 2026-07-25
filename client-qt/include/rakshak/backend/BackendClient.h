#pragma once
#include <QtCore/QObject>
#include <QtCore/QString>
#include <QtCore/QTimer>
#include <memory>
#include <rakshak/backend/ApiClient.h>

class LogMonitor;

// Owns the real backend connection (ApiClient) and the local log-tailing
// pipeline (LogMonitor). Every signal here reflects something that actually
// happened - no simulated telemetry.
class BackendClient : public QObject {
    Q_OBJECT
public:
    explicit BackendClient(QObject* parent = nullptr);
    ~BackendClient() override;

    // lifecycle
    void start();
    void stop();
    void startMonitoring(const QString& logPath);
    void stopMonitoring();
    void setFeatureExtraction(bool enabled);

    rakshak::backend::ApiClient* api() const { return m_api; }

signals:
    // Real backend reachability, polled on a timer - not a simulated status.
    void backendHealthChanged(bool reachable, const QString& version);

    // A tailed log line got a real verdict back from /v1/scan/logline.
    void logVerdictReady(const QString& line, const rakshak::backend::LogScanResult& verdict);
    void logVerdictFailed(const QString& line, const QString& message);

    // Real lines-per-second from LogMonitor.
    void logThroughput(int entriesPerSec);

    // Every raw tailed line, verbatim, before any scan verdict comes back.
    void rawLogLine(const QString& line);

    void monitoringStatusChanged(const QString& status);

private:
    static constexpr auto kContext = "logmonitor";

    rakshak::backend::ApiClient* m_api;
    QTimer m_healthTimer;
    std::unique_ptr<LogMonitor> m_logMonitor;
};
