#pragma once
#include <QtWidgets/QWidget>
#include <QtCore/QString>
#include <QtCore/QDateTime>

class QLabel;
class QTableView;
class QTimer;
class AlertsProxy;

namespace rakshak::pages {

// Landing page: one real status sentence built from live numbers, plus a
// recent-activity table - no KPI tiles, no invented metrics.
class DashboardPage : public QWidget {
    Q_OBJECT
public:
    explicit DashboardPage(AlertsProxy* alertsProxy, QWidget* parent = nullptr);

public slots:
    void setBackendReachable(bool reachable, const QString& version);
    void setQuarantineCount(int count);
    void setLogThroughput(int entriesPerSec);
    void setFilesScanned(int count);
    void setLinesChecked(int count);
    void setMonitoringActive(bool active);

signals:
    void requestScan();
    void requestLogAnalysis();
    void requestQuarantine();

private:
    void refreshStatusSentence();
    void refreshStatsRow();

    AlertsProxy* m_alertsProxy;
    QLabel* m_statusSentence;
    QLabel* m_statsRow;
    QTableView* m_activityTable;
    QTimer* m_uptimeTimer;

    bool m_backendReachable = false;
    QString m_backendVersion;
    int m_quarantineCount = 0;
    int m_logEps = 0;
    int m_filesScanned = 0;
    int m_linesChecked = 0;
    QDateTime m_monitoringStarted; // null when not monitoring
};

} // namespace rakshak::pages
