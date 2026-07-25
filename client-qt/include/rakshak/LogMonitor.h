#pragma once
#include <QtCore/QObject>
#include <QtCore/QTimer>
#include <QtCore/QString>
#include <QtCore/QFile>
#include <QtCore/QQueue>
#include <QtCore/QVariant>
#include <QtCore/QVariantMap>

// Platform-specific includes
#ifdef Q_OS_WIN
#include <windows.h>
#else
#include <sys/inotify.h>
#endif

class LogMonitor : public QObject {
    Q_OBJECT
public:
    explicit LogMonitor(QObject* parent = nullptr);
    ~LogMonitor();

    void startMonitoring(const QString& logPath);
    void stopMonitoring();
    void setFeatureExtractionMode(bool enabled) { m_extractFeatures = enabled; }
    void setBatchSize(int size) { m_batchSize = size; }
    
signals:
    void newLogEntry(const QString& entry);
    void newFeatures(const QVariantMap& features);
    void error(const QString& message);
    void processingStats(int entriesPerSec, double cpuUsage);
    void logEventDetected(const QString& source, const QVariantMap& event);
    void monitoringError(const QString& error, int severity);

private:
    void processNewData();
    void setupWatcher();
    void cleanupWatcher();
    QVariantMap extractFeatures(const QString& logEntry);
    
    QFile m_logFile;
    QTimer m_pollTimer;
    qint64 m_lastPosition{0};
    int m_batchSize{100};
    bool m_extractFeatures{true};
    QQueue<QString> m_pendingEntries;

    // Platform specific members
#ifdef Q_OS_WIN
    HANDLE m_changeHandle{INVALID_HANDLE_VALUE};
    OVERLAPPED m_overlapped{};
#else
    int m_inotifyFd{-1};
    int m_watchFd{-1};
#endif
};