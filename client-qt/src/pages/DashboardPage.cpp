#include <rakshak/pages/DashboardPage.h>
#include <rakshak/models/AlertsProxy.h>
#include <rakshak/common/UiState.h>

#include <QtWidgets/QVBoxLayout>
#include <QtWidgets/QHBoxLayout>
#include <QtWidgets/QLabel>
#include <QtWidgets/QPushButton>
#include <QtWidgets/QTableView>
#include <QtWidgets/QFrame>
#include <QtWidgets/QHeaderView>
#include <QtCore/QAbstractItemModel>
#include <QtCore/QTimer>

using namespace rakshak::pages;

DashboardPage::DashboardPage(AlertsProxy* alertsProxy, QWidget* parent)
    : QWidget(parent), m_alertsProxy(alertsProxy) {
    auto* layout = new QVBoxLayout(this);
    layout->setContentsMargins(48, 40, 48, 32);
    layout->setSpacing(4);

    auto* title = new QLabel(tr("Dashboard"), this);
    title->setObjectName("pageTitle");
    layout->addWidget(title);

    m_statusSentence = new QLabel(this);
    m_statusSentence->setObjectName("statusSentence");
    m_statusSentence->setWordWrap(true);
    layout->addWidget(m_statusSentence);

    m_statsRow = new QLabel(this);
    m_statsRow->setProperty("role", "mono");
    m_statsRow->setWordWrap(true);
    layout->addWidget(m_statsRow);
    layout->addSpacing(8);

    m_uptimeTimer = new QTimer(this);
    m_uptimeTimer->setInterval(1000);
    connect(m_uptimeTimer, &QTimer::timeout, this, &DashboardPage::refreshStatsRow);

    auto* actionsRow = new QHBoxLayout();
    auto* scanBtn = new QPushButton(tr("Scan a file"), this);
    scanBtn->setProperty("role", "primary");
    auto* logsBtn = new QPushButton(tr("Analyze logs"), this);
    auto* quarantineBtn = new QPushButton(tr("Review quarantine"), this);
    actionsRow->addWidget(scanBtn);
    actionsRow->addWidget(logsBtn);
    actionsRow->addWidget(quarantineBtn);
    actionsRow->addStretch();
    layout->addLayout(actionsRow);
    connect(scanBtn, &QPushButton::clicked, this, &DashboardPage::requestScan);
    connect(logsBtn, &QPushButton::clicked, this, &DashboardPage::requestLogAnalysis);
    connect(quarantineBtn, &QPushButton::clicked, this, &DashboardPage::requestQuarantine);

    auto* divider = new QFrame(this);
    divider->setProperty("role", "divider");
    divider->setFrameShape(QFrame::HLine);
    layout->addSpacing(16);
    layout->addWidget(divider);

    auto* sectionLabel = new QLabel(tr("Recent activity"), this);
    sectionLabel->setObjectName("sectionLabel");
    layout->addWidget(sectionLabel);

    m_activityTable = new QTableView(this);
    m_activityTable->setModel(m_alertsProxy);
    m_activityTable->setShowGrid(false);
    m_activityTable->verticalHeader()->hide();
    m_activityTable->setWordWrap(true);
    m_activityTable->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_activityTable->setEditTriggers(QAbstractItemView::NoEditTriggers);
    layout->addWidget(m_activityTable, 1);

    // Every column freely interactive-resizable, no forced full-width
    // stretch on the last one snapping user resizes back on every relayout.
    m_activityTable->resizeColumnsToContents();
    m_activityTable->horizontalHeader()->restoreState(rakshak::common::loadUiState("dashboard.activity"));
    connect(m_activityTable->horizontalHeader(), &QHeaderView::sectionResized, this, [this] {
        rakshak::common::saveUiState("dashboard.activity", m_activityTable->horizontalHeader()->saveState());
    });

    if (auto* source = m_alertsProxy->sourceModel()) {
        connect(source, &QAbstractItemModel::rowsInserted, this, &DashboardPage::refreshStatusSentence);
        connect(source, &QAbstractItemModel::modelReset, this, &DashboardPage::refreshStatusSentence);
        connect(source, &QAbstractItemModel::rowsInserted, m_activityTable, &QTableView::resizeRowsToContents);
        connect(source, &QAbstractItemModel::modelReset, m_activityTable, &QTableView::resizeRowsToContents);
    }

    refreshStatusSentence();
    refreshStatsRow();
}

void DashboardPage::setBackendReachable(bool reachable, const QString& version) {
    m_backendReachable = reachable;
    m_backendVersion = version;
    refreshStatusSentence();
}

void DashboardPage::setQuarantineCount(int count) {
    m_quarantineCount = count;
    refreshStatusSentence();
}

void DashboardPage::setLogThroughput(int entriesPerSec) {
    m_logEps = entriesPerSec;
    refreshStatusSentence();
}

void DashboardPage::setFilesScanned(int count) {
    m_filesScanned = count;
    refreshStatsRow();
}

void DashboardPage::setLinesChecked(int count) {
    m_linesChecked = count;
    refreshStatsRow();
}

void DashboardPage::setMonitoringActive(bool active) {
    if (active) {
        m_monitoringStarted = QDateTime::currentDateTime();
        m_uptimeTimer->start();
    } else {
        m_monitoringStarted = QDateTime();
        m_uptimeTimer->stop();
    }
    refreshStatsRow();
}

void DashboardPage::refreshStatusSentence() {
    const int activityCount = m_alertsProxy && m_alertsProxy->sourceModel()
        ? m_alertsProxy->sourceModel()->rowCount() : 0;

    QString backendPart = m_backendReachable
        ? tr("Backend reachable (v%1).").arg(m_backendVersion.isEmpty() ? tr("unknown") : m_backendVersion)
        : tr("Backend unreachable.");

    QString text = tr("%1 %2 events logged, %3 files quarantined, %4 lines/sec tailed.")
        .arg(backendPart)
        .arg(activityCount)
        .arg(m_quarantineCount)
        .arg(m_logEps);

    m_statusSentence->setText(text);
}

void DashboardPage::refreshStatsRow() {
    QString uptime = tr("not monitoring");
    if (m_monitoringStarted.isValid()) {
        const qint64 secs = m_monitoringStarted.secsTo(QDateTime::currentDateTime());
        uptime = QStringLiteral("%1:%2:%3")
            .arg(secs / 3600, 2, 10, QChar('0'))
            .arg((secs % 3600) / 60, 2, 10, QChar('0'))
            .arg(secs % 60, 2, 10, QChar('0'));
    }

    m_statsRow->setText(tr("Files scanned %1  ·  Lines checked %2  ·  Monitoring uptime %3")
        .arg(m_filesScanned)
        .arg(m_linesChecked)
        .arg(uptime));
}
