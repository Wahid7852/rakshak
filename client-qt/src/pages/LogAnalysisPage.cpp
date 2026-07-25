#include <rakshak/pages/LogAnalysisPage.h>
#include <rakshak/backend/BackendClient.h>
#include <rakshak/models/AlertsModel.h>
#include <rakshak/models/AlertsProxy.h>
#include <rakshak/common/UiState.h>

#include <QtWidgets/QVBoxLayout>
#include <QtWidgets/QHBoxLayout>
#include <QtWidgets/QLabel>
#include <QtWidgets/QPlainTextEdit>
#include <QtWidgets/QTableView>
#include <QtWidgets/QLineEdit>
#include <QtWidgets/QPushButton>
#include <QtWidgets/QHeaderView>
#include <QtCore/QDateTime>
#include <QtCore/QAbstractItemModel>

using namespace rakshak::pages;
using rakshak::backend::LogScanResult;

LogAnalysisPage::LogAnalysisPage(BackendClient* backend, AlertsModel* alertsModel,
                                  AlertsProxy* alertsProxy, QWidget* parent)
    : QWidget(parent), m_backend(backend), m_alertsModel(alertsModel), m_alertsProxy(alertsProxy),
      m_context(QStringLiteral("loganalysispage")) {
    auto* layout = new QVBoxLayout(this);
    layout->setContentsMargins(48, 40, 48, 32);
    layout->setSpacing(8);

    auto* title = new QLabel(tr("Log analysis"), this);
    title->setObjectName("pageTitle");
    layout->addWidget(title);

    auto* subtitle = new QLabel(tr("Check a line on demand, or point Settings → Log path at a file for continuous background tailing. Either way, flagged verdicts land in the table below."), this);
    subtitle->setObjectName("statusSentence");
    subtitle->setWordWrap(true);
    layout->addWidget(subtitle);

    auto* checkRow = new QHBoxLayout();
    m_checkLineInput = new QLineEdit(this);
    m_checkLineInput->setPlaceholderText(tr("paste a log line to check..."));
    m_checkLineInput->setToolTip(tr("Scores this one line on demand via /v1/scan/logline - "
        "works without any background tailing configured."));
    m_checkLineButton = new QPushButton(tr("Check line"), this);
    checkRow->addWidget(m_checkLineInput, 1);
    checkRow->addWidget(m_checkLineButton);
    layout->addLayout(checkRow);

    m_checkResultLabel = new QLabel(this);
    m_checkResultLabel->setProperty("role", "muted");
    m_checkResultLabel->setWordWrap(true);
    layout->addWidget(m_checkResultLabel);

    layout->addSpacing(12);
    auto* alertsLabel = new QLabel(tr("Flagged lines"), this);
    alertsLabel->setObjectName("sectionLabel");
    layout->addWidget(alertsLabel);

    m_alertsTable = new QTableView(this);
    m_alertsTable->setModel(m_alertsProxy);
    m_alertsTable->setShowGrid(false);
    m_alertsTable->verticalHeader()->hide();
    m_alertsTable->setWordWrap(true);
    m_alertsTable->setEditTriggers(QAbstractItemView::NoEditTriggers);
    layout->addWidget(m_alertsTable, 1);

    m_alertsTable->resizeColumnsToContents();
    m_alertsTable->horizontalHeader()->restoreState(rakshak::common::loadUiState("loganalysis.alerts"));
    connect(m_alertsTable->horizontalHeader(), &QHeaderView::sectionResized, this, [this] {
        rakshak::common::saveUiState("loganalysis.alerts", m_alertsTable->horizontalHeader()->saveState());
    });
    if (auto* source = m_alertsProxy->sourceModel()) {
        connect(source, &QAbstractItemModel::rowsInserted, m_alertsTable, &QTableView::resizeRowsToContents);
        connect(source, &QAbstractItemModel::modelReset, m_alertsTable, &QTableView::resizeRowsToContents);
    }

    auto* tailLabel = new QLabel(tr("Raw tail"), this);
    tailLabel->setObjectName("sectionLabel");
    layout->addWidget(tailLabel);

    m_tailView = new QPlainTextEdit(this);
    m_tailView->setReadOnly(true);
    m_tailView->setProperty("role", "mono");
    m_tailView->setMaximumBlockCount(2000);
    layout->addWidget(m_tailView, 1);

    connect(m_checkLineButton, &QPushButton::clicked, this, &LogAnalysisPage::onCheckLineClicked);

    connect(m_backend, &BackendClient::rawLogLine, this, [this](const QString& line) {
        m_tailView->appendPlainText(line);
    });

    connect(m_backend, &BackendClient::logVerdictReady, this,
            [this](const QString& line, const LogScanResult& verdict) {
                if (!verdict.suspicious) return;
                AlertRow row;
                row.timestamp = QDateTime::currentDateTime().toString(Qt::ISODate);
                row.severity = QStringLiteral("Flagged");
                row.dstIp = QStringLiteral("log tail");
                row.ruleId = verdict.model;
                row.score = verdict.score;
                row.json = line;
                m_alertsModel->addAlert(row);
            });

    auto* api = m_backend->api();
    connect(api, &rakshak::backend::ApiClient::logScanResult, this,
            [this](const QString& context, const QString& line, const LogScanResult& result) {
                if (context != m_context) return;
                m_checkLineButton->setEnabled(true);
                m_checkResultLabel->setText(tr("\"%1\" -> %2 (score %3, confidence %4, model %5)")
                    .arg(line, result.suspicious ? tr("suspicious") : tr("clean"))
                    .arg(result.score, 0, 'f', 3).arg(result.confidence, 0, 'f', 3).arg(result.model));

                // Manual checks aren't part of the background tailer's stream -
                // reflect them in raw tail and recent activity ourselves.
                m_tailView->appendPlainText(line);
                AlertRow row;
                row.timestamp = QDateTime::currentDateTime().toString(Qt::ISODate);
                row.severity = result.suspicious ? QStringLiteral("Flagged") : QStringLiteral("Clean");
                row.srcIp = line.left(60);
                row.dstIp = QStringLiteral("log line");
                row.ruleId = result.model;
                row.score = result.score;
                row.json = line;
                m_alertsModel->addAlert(row);
            });
    connect(api, &rakshak::backend::ApiClient::logScanError, this,
            [this](const QString& context, const QString& /*line*/, const QString& message) {
                if (context != m_context) return;
                m_checkLineButton->setEnabled(true);
                m_checkResultLabel->setText(tr("Check failed: %1").arg(message));
            });
}

void LogAnalysisPage::onCheckLineClicked() {
    const auto line = m_checkLineInput->text().trimmed();
    if (line.isEmpty()) return;
    m_checkLineButton->setEnabled(false);
    m_backend->api()->scanLogLine(line, m_context);
}
