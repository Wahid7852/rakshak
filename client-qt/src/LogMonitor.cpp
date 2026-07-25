#include "rakshak/LogMonitor.h"
#include <QtCore/QtCore>

#ifdef Q_OS_WIN
#include <fileapi.h>
#else
#include <unistd.h>
#include <sys/types.h>
#endif

LogMonitor::LogMonitor(QObject* parent) 
    : QObject(parent) {
    
    connect(&m_pollTimer, &QTimer::timeout, this, &LogMonitor::processNewData);
}

LogMonitor::~LogMonitor() {
    stopMonitoring();
}

void LogMonitor::startMonitoring(const QString& logPath) {
    if (m_logFile.isOpen()) {
        stopMonitoring();
    }

    m_logFile.setFileName(logPath);
    if (!m_logFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
        QString msg = tr("Failed to open log file: %1").arg(logPath);
        emit error(msg);
        emit monitoringError(msg, 2);
        return;
    }

    // Seek to end for new data only
    m_lastPosition = m_logFile.size();
    setupWatcher();
    
    // Start polling as backup in case file system events fail
    m_pollTimer.start(1000);  // 1 second backup polling
}

void LogMonitor::stopMonitoring() {
    m_pollTimer.stop();
    cleanupWatcher();
    if (m_logFile.isOpen()) {
        m_logFile.close();
    }
}

void LogMonitor::setupWatcher() {
#ifdef Q_OS_WIN
    // Windows directory change notification
    QString dirPath = QFileInfo(m_logFile).absolutePath();
    m_changeHandle = FindFirstChangeNotificationW(
        (LPCWSTR)dirPath.utf16(),
        FALSE,  // Don't watch subtree
        FILE_NOTIFY_CHANGE_LAST_WRITE  // Watch for write changes
    );
    
    if (m_changeHandle == INVALID_HANDLE_VALUE) {
        qWarning() << "Failed to setup Windows file change notification";
        return;
    }

#else
    // Linux inotify setup
    m_inotifyFd = inotify_init();
    if (m_inotifyFd < 0) {
        qWarning() << "Failed to initialize inotify";
        return;
    }

    m_watchFd = inotify_add_watch(
        m_inotifyFd,
        qPrintable(m_logFile.fileName()),
        IN_MODIFY
    );
    
    if (m_watchFd < 0) {
        close(m_inotifyFd);
        m_inotifyFd = -1;
        qWarning() << "Failed to add inotify watch";
        return;
    }
#endif
}

void LogMonitor::cleanupWatcher() {
#ifdef Q_OS_WIN
    if (m_changeHandle != INVALID_HANDLE_VALUE) {
        FindCloseChangeNotification(m_changeHandle);
        m_changeHandle = INVALID_HANDLE_VALUE;
    }
#else
    if (m_watchFd >= 0) {
        inotify_rm_watch(m_inotifyFd, m_watchFd);
        m_watchFd = -1;
    }
    if (m_inotifyFd >= 0) {
        close(m_inotifyFd);
        m_inotifyFd = -1;
    }
#endif
}

void LogMonitor::processNewData() {
    if (!m_logFile.isOpen()) return;

    // Check file size
    qint64 currentSize = m_logFile.size();
    if (currentSize == m_lastPosition) return;  // No new data

    // Handle file truncation
    if (currentSize < m_lastPosition) {
        m_lastPosition = 0;
        m_logFile.seek(0);
    } else {
        m_logFile.seek(m_lastPosition);
    }

    // Process new lines
    QTextStream stream(&m_logFile);
    int processedCount = 0;
    QElapsedTimer timer;
    timer.start();

    while (!stream.atEnd() && processedCount < m_batchSize) {
        QString line = stream.readLine();
        if (line.isEmpty()) continue;

        m_pendingEntries.enqueue(line);
        emit newLogEntry(line);

        if (m_extractFeatures) {
            QVariantMap features = extractFeatures(line);
            if (!features.isEmpty()) {
                emit newFeatures(features);
                // Provide higher-level event signal for UI
                QString src = QFileInfo(m_logFile.fileName()).fileName();
                emit logEventDetected(src, features);
            }
        }

        processedCount++;
    }

    // Update position and stats
    m_lastPosition = m_logFile.pos();
    double elapsed = timer.elapsed() / 1000.0;  // Convert to seconds
    if (elapsed > 0) {
        int entriesPerSec = static_cast<int>(processedCount / elapsed);
        double cpuUsage = QThread::currentThread()->priority() / 7.0 * 100.0;  // Rough estimate
        emit processingStats(entriesPerSec, cpuUsage);
    }
}

QVariantMap LogMonitor::extractFeatures(const QString& logEntry) {
    QVariantMap features;
    
    // Check if JSON or log format
    if (logEntry.startsWith('{')) {
        // Parse threat.json format
        QJsonDocument doc = QJsonDocument::fromJson(logEntry.toUtf8());
        if (!doc.isObject()) return features;
        
        QJsonObject obj = doc.object();
        
        // Extract common threat features
        features["timestamp"] = obj["timestamp"].toDouble();
        features["bytes"] = obj["bytes"].toDouble();
        features["proto"] = obj["proto"].toString();
        features["src_ip"] = obj["src"].toString();
        features["dst_ip"] = obj["dst"].toString();
        features["src_port"] = obj["sport"].toInt();
        features["dst_port"] = obj["dport"].toInt();
        
        // Network behavior features
        features["tcp_flags"] = obj["tcp_flags"].toInt();
        features["src_bytes"] = obj["src_bytes"].toDouble();
        features["dst_bytes"] = obj["dst_bytes"].toDouble();
        
    } else {
        // Parse auth.log format
        static QRegularExpression re(R"((\w+\s+\d+\s+\d+:\d+:\d+).*?(sshd|sudo|su).*?(\d+\.\d+\.\d+\.\d+)?)");
        QRegularExpressionMatch match = re.match(logEntry);
        
        if (match.hasMatch()) {
            QDateTime timestamp = QDateTime::fromString(match.captured(1), "MMM d hh:mm:ss");
            features["timestamp"] = timestamp.toSecsSinceEpoch();
            features["service"] = match.captured(2);
            features["src_ip"] = match.captured(3);
            features["is_auth_attempt"] = true;
        }
    }
    
    return features;
}