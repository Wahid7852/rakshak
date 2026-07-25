#pragma once

#include <QtCore/QObject>
#include <QtCore/QString>
#include <QtCore/QVector>

class QNetworkAccessManager;
class QNetworkReply;
class QNetworkRequest;

namespace rakshak::backend {

struct FileScanResult {
    bool malicious = false;
    double score = 0.0;
    double confidence = 0.0;
    QString model;
    QString reason;
    QString sha256;
    bool quarantined = false;
    QString quarantineId;
};

struct LogScanResult {
    bool suspicious = false;
    double score = 0.0;
    double confidence = 0.0;
    QString model;
    QString reason;
};

struct QuarantineEntryDto {
    QString quarantineId;
    QString originalPath;
    QString quarantineFile;
    QString reason;
    QString sha256;
    double timestamp = 0.0;
};

// Thin async REST client for the real FastAPI backend (backend/api/main.py).
// Every call is fire-and-forget from the caller's side; results arrive on the
// paired signal below. Nothing here blocks the UI thread.
class ApiClient : public QObject {
    Q_OBJECT
public:
    explicit ApiClient(QObject* parent = nullptr);
    ~ApiClient() override;

public slots:
    // Re-reads base URL / API key from Settings. Call after Settings::save().
    void reloadSettings();

    void checkHealth();
    // context is an opaque caller-chosen tag echoed back on the result signal -
    // lets two callers (e.g. two LogMonitors) tell their own requests apart
    // even when the line/path text alone wouldn't disambiguate them.
    void scanFile(const QString& localPath, const QString& context = QString());
    void scanLogLine(const QString& line, const QString& context = QString());
    void listQuarantine();
    void restoreQuarantine(const QString& quarantineId, const QString& destPath = QString());
    void deleteQuarantine(const QString& quarantineId);

signals:
    void healthChecked(bool reachable, const QString& version);

    // context/localPath/line are echoed back so callers can correlate results
    // when more than one scan is in flight at once.
    void fileScanResult(const QString& context, const QString& localPath, const FileScanResult& result);
    void fileScanError(const QString& context, const QString& localPath, const QString& message);

    void logScanResult(const QString& context, const QString& line, const LogScanResult& result);
    void logScanError(const QString& context, const QString& line, const QString& message);

    void quarantineListResult(const QVector<QuarantineEntryDto>& entries);
    void quarantineListError(const QString& message);

    void quarantineRestored(const QString& quarantineId, bool ok, const QString& message);
    void quarantineDeleted(const QString& quarantineId, bool ok, const QString& message);

private:
    QString url(const QString& path) const;
    void setAuthHeader(QNetworkRequest& request) const;
    QString describeError(QNetworkReply* reply, const QByteArray& body) const;

    QNetworkAccessManager* m_net;
    QString m_baseUrl;
    QString m_apiKey;
};

} // namespace rakshak::backend
