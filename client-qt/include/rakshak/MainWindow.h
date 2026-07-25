#pragma once
#include <QtWidgets/QMainWindow>
#include <QtCore/QString>

class QStackedWidget;
class QLabel;
class QPushButton;
class BackendClient;
class AlertsModel;
class AlertsProxy;
class AuditModel;
class QuarantineModel;

namespace rakshak::widgets { class ToastNotification; }
namespace rakshak::pages {
class DashboardPage;
class ScanPage;
class ScanResultPage;
class LogAnalysisPage;
class QuarantinePage;
class AuditLogsPage;
class SettingsPage;
}

// Real member pointers, constructed in code, wired with direct connect()
// calls - no anonymous-namespace globals, no findChild<T>("stringName")
// lookups into a Designer .ui form.
class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    explicit MainWindow(QWidget* parent = nullptr);
    ~MainWindow() override;

private:
    void buildChrome();
    void buildPages();
    void wireConnections();
    void navigateTo(QWidget* page);
    void toast(const QString& message, bool isError);
    void applyTheme(bool dark);
    void restartMonitoringFromSettings();
    void recordActivity(bool flagged, const QString& subject, const QString& kind,
                         const QString& model, double score, const QString& raw);

    // chrome
    QStackedWidget* m_stack = nullptr;
    QLabel* m_backendStatusLabel = nullptr;
    QPushButton* m_navDashboard = nullptr;
    QPushButton* m_navScan = nullptr;
    QPushButton* m_navLogs = nullptr;
    QPushButton* m_navQuarantine = nullptr;
    QPushButton* m_navAudit = nullptr;
    QPushButton* m_navSettings = nullptr;
    QPushButton* m_themeToggle = nullptr;
    bool m_darkMode = false;
    rakshak::widgets::ToastNotification* m_toast = nullptr;

    // backend + models (single source of truth, injected into pages)
    BackendClient* m_backend = nullptr;
    AlertsModel* m_alertsModel = nullptr;
    AlertsProxy* m_alertsProxy = nullptr;   // unfiltered - Dashboard's "recent activity"
    AlertsProxy* m_flaggedProxy = nullptr;  // severity == "Flagged" only - LogAnalysisPage's table
    AuditModel* m_auditModel = nullptr;
    QuarantineModel* m_quarantineModel = nullptr;

    // pages
    rakshak::pages::DashboardPage* m_dashboardPage = nullptr;
    rakshak::pages::ScanPage* m_scanPage = nullptr;
    rakshak::pages::ScanResultPage* m_scanResultPage = nullptr;
    rakshak::pages::LogAnalysisPage* m_logAnalysisPage = nullptr;
    rakshak::pages::QuarantinePage* m_quarantinePage = nullptr;
    rakshak::pages::AuditLogsPage* m_auditLogsPage = nullptr;
    rakshak::pages::SettingsPage* m_settingsPage = nullptr;

    bool m_lastBackendReachable = false;
    int m_filesScanned = 0;
    int m_linesChecked = 0;

    Q_DISABLE_COPY(MainWindow)
};
