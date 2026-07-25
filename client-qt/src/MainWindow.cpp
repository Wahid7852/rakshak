#include <rakshak/MainWindow.h>

#include <rakshak/backend/BackendClient.h>
#include <rakshak/models/AlertsModel.h>
#include <rakshak/models/AlertsProxy.h>
#include <rakshak/models/AuditModel.h>
#include <rakshak/models/QuarantineModel.h>
#include <rakshak/widgets/ToastNotification.h>
#include <rakshak/common/UiState.h>
#include <rakshak/common/Settings.h>
#include <rakshak/pages/DashboardPage.h>
#include <rakshak/pages/ScanPage.h>
#include <rakshak/pages/ScanResultPage.h>
#include <rakshak/pages/LogAnalysisPage.h>
#include <rakshak/pages/QuarantinePage.h>
#include <rakshak/pages/AuditLogsPage.h>
#include <rakshak/pages/SettingsPage.h>

#include <QtWidgets/QApplication>
#include <QtWidgets/QWidget>
#include <QtWidgets/QHBoxLayout>
#include <QtWidgets/QVBoxLayout>
#include <QtWidgets/QStackedWidget>
#include <QtWidgets/QSplitter>
#include <QtWidgets/QLabel>
#include <QtWidgets/QPushButton>
#include <QtWidgets/QStatusBar>
#include <QtCore/QDateTime>
#include <QtCore/QVariantMap>
#include <QtCore/QSize>
#include <QtCore/QFile>
#include <QtCore/QFileInfo>
#include <QtGui/QIcon>
#include <utility>

using rakshak::backend::FileScanResult;
using rakshak::backend::LogScanResult;
using rakshak::widgets::ToastNotification;
using namespace rakshak::pages;

namespace {
QVariantMap auditEvent(const QString& action, const QString& status, const QString& hash = QString()) {
    QVariantMap m;
    m["timestamp"] = QDateTime::currentDateTime().toString(Qt::ISODate);
    m["actor"] = QStringLiteral("system");
    m["action"] = action;
    m["status"] = status;
    m["hash"] = hash;
    return m;
}
}

MainWindow::MainWindow(QWidget* parent) : QMainWindow(parent) {
    setWindowTitle(tr("RAKSHAK"));
    resize(1100, 720);

    m_backend = new BackendClient(this);
    m_alertsModel = new AlertsModel(this);
    m_alertsProxy = new AlertsProxy(this);
    m_alertsProxy->setSourceModel(m_alertsModel);
    m_flaggedProxy = new AlertsProxy(this);
    m_flaggedProxy->setSourceModel(m_alertsModel);
    m_flaggedProxy->setSeverityFilter(QStringLiteral("Flagged"));
    m_auditModel = new AuditModel(this);
    m_quarantineModel = new QuarantineModel(this);

    buildChrome();
    buildPages();
    wireConnections();

    applyTheme(rakshak::common::Settings::instance().load().darkMode);
    m_backend->start();
    restartMonitoringFromSettings();
    navigateTo(m_dashboardPage);
}

MainWindow::~MainWindow() = default;

void MainWindow::buildChrome() {
    auto* splitter = new QSplitter(Qt::Horizontal, this);
    splitter->setChildrenCollapsible(false);
    splitter->setHandleWidth(1);

    auto* sidebar = new QWidget(splitter);
    sidebar->setObjectName("sidebar");
    sidebar->setMinimumWidth(160);
    sidebar->setMaximumWidth(360);
    auto* sidebarLayout = new QVBoxLayout(sidebar);
    sidebarLayout->setContentsMargins(20, 24, 20, 24);
    sidebarLayout->setSpacing(2);

    auto* logoRow = new QHBoxLayout();
    auto* logoIcon = new QLabel(sidebar);
    logoIcon->setPixmap(QIcon(":/icons/logo-shield.svg").pixmap(22, 22));
    auto* logoText = new QVBoxLayout();
    auto* logoTitle = new QLabel(tr("RAKSHAK"), sidebar);
    logoTitle->setObjectName("logoTitle");
    auto* logoSubtitle = new QLabel(tr("Guardian"), sidebar);
    logoSubtitle->setObjectName("logoSubtitle");
    logoText->addWidget(logoTitle);
    logoText->addWidget(logoSubtitle);
    logoText->setSpacing(0);
    logoRow->addWidget(logoIcon);
    logoRow->addLayout(logoText);
    logoRow->addStretch();
    sidebarLayout->addLayout(logoRow);
    sidebarLayout->addSpacing(24);

    auto makeNavButton = [sidebar](const QString& text, const QString& iconPath) {
        auto* btn = new QPushButton(QIcon(iconPath), text, sidebar);
        btn->setObjectName("navButton");
        btn->setCheckable(true);
        btn->setIconSize(QSize(16, 16));
        return btn;
    };
    m_navDashboard = makeNavButton(tr("Dashboard"), ":/icons/dashboard.svg");
    m_navScan = makeNavButton(tr("Scan"), ":/icons/scan.svg");
    m_navLogs = makeNavButton(tr("Log analysis"), ":/icons/log.svg");
    m_navQuarantine = makeNavButton(tr("Quarantine"), ":/icons/quarantine.svg");
    m_navAudit = makeNavButton(tr("Audit log"), ":/icons/audit.svg");
    m_navSettings = makeNavButton(tr("Settings"), ":/icons/settings.svg");
    for (auto* btn : {m_navDashboard, m_navScan, m_navLogs, m_navQuarantine, m_navAudit, m_navSettings}) {
        sidebarLayout->addWidget(btn);
    }
    sidebarLayout->addStretch();

    m_themeToggle = new QPushButton(sidebar);
    m_themeToggle->setObjectName("navButton");
    m_themeToggle->setIconSize(QSize(16, 16));
    m_themeToggle->setToolTip(tr("Switch between light and dark theme - applies immediately, persists across restarts."));
    connect(m_themeToggle, &QPushButton::clicked, this, [this] { applyTheme(!m_darkMode); });
    sidebarLayout->addWidget(m_themeToggle);

    m_stack = new QStackedWidget(splitter);

    splitter->addWidget(sidebar);
    splitter->addWidget(m_stack);
    splitter->setStretchFactor(0, 0);
    splitter->setStretchFactor(1, 1);
    splitter->restoreState(rakshak::common::loadUiState("mainwindow.splitter"));
    connect(splitter, &QSplitter::splitterMoved, this, [splitter] {
        rakshak::common::saveUiState("mainwindow.splitter", splitter->saveState());
    });
    setCentralWidget(splitter);

    m_backendStatusLabel = new QLabel(tr("backend: unknown"), this);
    statusBar()->addPermanentWidget(m_backendStatusLabel);

    m_toast = new ToastNotification(this);
}

void MainWindow::buildPages() {
    m_dashboardPage = new DashboardPage(m_alertsProxy, this);
    m_scanPage = new ScanPage(m_backend->api(), this);
    m_scanResultPage = new ScanResultPage(this);
    m_logAnalysisPage = new LogAnalysisPage(m_backend, m_alertsModel, m_flaggedProxy, this);
    m_quarantinePage = new QuarantinePage(m_backend->api(), m_quarantineModel, this);
    m_auditLogsPage = new AuditLogsPage(m_auditModel, this);
    m_settingsPage = new SettingsPage(m_backend->api(), this);

    for (auto* page : {static_cast<QWidget*>(m_dashboardPage), static_cast<QWidget*>(m_scanPage),
                        static_cast<QWidget*>(m_scanResultPage), static_cast<QWidget*>(m_logAnalysisPage),
                        static_cast<QWidget*>(m_quarantinePage), static_cast<QWidget*>(m_auditLogsPage),
                        static_cast<QWidget*>(m_settingsPage)}) {
        m_stack->addWidget(page);
    }
}

void MainWindow::navigateTo(QWidget* page) {
    m_stack->setCurrentWidget(page);
    for (auto pair : {std::pair{m_navDashboard, static_cast<QWidget*>(m_dashboardPage)},
                        std::pair{m_navScan, static_cast<QWidget*>(m_scanPage)},
                        std::pair{m_navLogs, static_cast<QWidget*>(m_logAnalysisPage)},
                        std::pair{m_navQuarantine, static_cast<QWidget*>(m_quarantinePage)},
                        std::pair{m_navAudit, static_cast<QWidget*>(m_auditLogsPage)},
                        std::pair{m_navSettings, static_cast<QWidget*>(m_settingsPage)}}) {
        pair.first->setChecked(pair.second == page);
    }
    if (page == m_quarantinePage) m_quarantinePage->refresh();
}

void MainWindow::applyTheme(bool dark) {
    m_darkMode = dark;

    QFile styleFile(dark ? ":/style/rakshak-dark.qss" : ":/style/rakshak.qss");
    if (styleFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
        qApp->setStyleSheet(QString::fromUtf8(styleFile.readAll()));
    }

    m_themeToggle->setIcon(QIcon(dark ? ":/icons/theme-light.svg" : ":/icons/theme-dark.svg"));
    m_themeToggle->setText(dark ? tr("Light mode") : tr("Dark mode"));

    auto d = rakshak::common::Settings::instance().load();
    d.darkMode = dark;
    rakshak::common::Settings::instance().save(d);
}

void MainWindow::toast(const QString& message, bool isError) {
    m_toast->showToast(message, isError ? ToastNotification::ToastType::Danger
                                         : ToastNotification::ToastType::Success);
}

void MainWindow::recordActivity(bool flagged, const QString& subject, const QString& kind,
                                 const QString& model, double score, const QString& raw) {
    AlertRow row;
    row.timestamp = QDateTime::currentDateTime().toString(Qt::ISODate);
    row.severity = flagged ? QStringLiteral("Flagged") : QStringLiteral("Clean");
    row.srcIp = subject.left(60);
    row.dstIp = kind;
    row.ruleId = model;
    row.score = score;
    row.json = raw;
    m_alertsModel->addAlert(row);
}

void MainWindow::restartMonitoringFromSettings() {
    const auto logPath = rakshak::common::Settings::instance().load().logPath;
    m_backend->stopMonitoring();
    if (!logPath.isEmpty()) {
        m_backend->startMonitoring(logPath);
    }
}

void MainWindow::wireConnections() {
    connect(m_navDashboard, &QPushButton::clicked, this, [this] { navigateTo(m_dashboardPage); });
    connect(m_navScan, &QPushButton::clicked, this, [this] { navigateTo(m_scanPage); });
    connect(m_navLogs, &QPushButton::clicked, this, [this] { navigateTo(m_logAnalysisPage); });
    connect(m_navQuarantine, &QPushButton::clicked, this, [this] { navigateTo(m_quarantinePage); });
    connect(m_navAudit, &QPushButton::clicked, this, [this] { navigateTo(m_auditLogsPage); });
    connect(m_navSettings, &QPushButton::clicked, this, [this] { navigateTo(m_settingsPage); });

    connect(m_dashboardPage, &DashboardPage::requestScan, this, [this] { navigateTo(m_scanPage); });
    connect(m_dashboardPage, &DashboardPage::requestLogAnalysis, this, [this] { navigateTo(m_logAnalysisPage); });
    connect(m_dashboardPage, &DashboardPage::requestQuarantine, this, [this] { navigateTo(m_quarantinePage); });

    connect(m_scanPage, &ScanPage::fileScanReady, this,
            [this](const QString& path, const FileScanResult& result) {
                m_scanResultPage->setFileResult(path, result);
                navigateTo(m_scanResultPage);
                m_auditModel->addEvent(path, auditEvent(QStringLiteral("scan_file"),
                    result.malicious ? QStringLiteral("malicious") : QStringLiteral("clean"), result.sha256));
                if (result.quarantined) toast(tr("File quarantined."), true);
                m_dashboardPage->setFilesScanned(++m_filesScanned);
                recordActivity(result.malicious, QFileInfo(path).fileName(), QStringLiteral("file scan"),
                                result.model, result.score, path);
            });
    connect(m_scanPage, &ScanPage::logLineScanReady, this,
            [this](const QString& line, const LogScanResult& result) {
                m_scanResultPage->setLogResult(line, result);
                navigateTo(m_scanResultPage);
                recordActivity(result.suspicious, line, QStringLiteral("log line"),
                                result.model, result.score, line);
            });
    connect(m_scanResultPage, &ScanResultPage::backRequested, this, [this] { navigateTo(m_scanPage); });
    connect(m_scanResultPage, &ScanResultPage::viewQuarantineRequested, this, [this] { navigateTo(m_quarantinePage); });

    connect(m_quarantinePage, &QuarantinePage::statusMessage, this, [this](const QString& msg, bool isError) {
        toast(msg, isError);
        m_auditModel->addEvent(QStringLiteral("quarantine"),
            auditEvent(QStringLiteral("quarantine_action"), isError ? QStringLiteral("failed") : QStringLiteral("ok")));
    });
    connect(m_settingsPage, &SettingsPage::statusMessage, this, [this](const QString& msg, bool isError) {
        toast(msg, isError);
        if (!isError) {
            m_auditModel->addEvent(QStringLiteral("settings"), auditEvent(QStringLiteral("settings_saved"), QStringLiteral("ok")));
        }
    });
    connect(m_settingsPage, &SettingsPage::settingsApplied, this, [this] {
        applyTheme(rakshak::common::Settings::instance().load().darkMode);
        restartMonitoringFromSettings();
    });

    connect(m_backend, &BackendClient::backendHealthChanged, this, [this](bool reachable, const QString& version) {
        m_backendStatusLabel->setText(reachable
            ? tr("backend: reachable (v%1)").arg(version)
            : tr("backend: unreachable"));
        m_dashboardPage->setBackendReachable(reachable, version);
        if (reachable != m_lastBackendReachable) {
            m_auditModel->addEvent(QStringLiteral("backend"),
                auditEvent(QStringLiteral("health_change"), reachable ? QStringLiteral("reachable") : QStringLiteral("unreachable")));
            m_lastBackendReachable = reachable;
        }
    });
    connect(m_backend, &BackendClient::logThroughput, this, [this](int eps) {
        m_dashboardPage->setLogThroughput(eps);
    });
    connect(m_backend, &BackendClient::monitoringStatusChanged, this, [this](const QString& status) {
        m_auditModel->addEvent(QStringLiteral("monitoring"), auditEvent(QStringLiteral("monitoring_status"), status));
        m_dashboardPage->setMonitoringActive(status == QLatin1String("monitoring started"));
    });
    connect(m_backend, &BackendClient::rawLogLine, this, [this](const QString&) {
        m_dashboardPage->setLinesChecked(++m_linesChecked);
    });

    connect(m_quarantineModel, &QuarantineModel::modelReset, this, [this] {
        m_dashboardPage->setQuarantineCount(m_quarantineModel->rowCount());
    });
    connect(m_quarantineModel, &QuarantineModel::rowsRemoved, this, [this] {
        m_dashboardPage->setQuarantineCount(m_quarantineModel->rowCount());
    });
}
