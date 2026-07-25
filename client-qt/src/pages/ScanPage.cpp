#include <rakshak/pages/ScanPage.h>

#include <QtWidgets/QVBoxLayout>
#include <QtWidgets/QHBoxLayout>
#include <QtWidgets/QLabel>
#include <QtWidgets/QPushButton>
#include <QtWidgets/QProgressBar>
#include <QtWidgets/QLineEdit>
#include <QtWidgets/QFileDialog>
#include <QtWidgets/QStyle>
#include <QtCore/QFileInfo>
#include <QtCore/QVariant>

using namespace rakshak::pages;
using rakshak::backend::ApiClient;
using rakshak::backend::FileScanResult;
using rakshak::backend::LogScanResult;

ScanPage::ScanPage(ApiClient* api, QWidget* parent)
    : QWidget(parent), m_api(api), m_context(QStringLiteral("scanpage")) {
    auto* layout = new QVBoxLayout(this);
    layout->setContentsMargins(48, 40, 48, 32);
    layout->setSpacing(10);

    auto* title = new QLabel(tr("Scan"), this);
    title->setObjectName("pageTitle");
    layout->addWidget(title);

    auto* subtitle = new QLabel(tr("Upload a file to /v1/scan/file for a real verdict from the backend."), this);
    subtitle->setObjectName("statusSentence");
    subtitle->setWordWrap(true);
    layout->addWidget(subtitle);

    layout->addSpacing(12);

    auto* fileRow = new QHBoxLayout();
    m_chooseButton = new QPushButton(tr("Choose file..."), this);
    m_selectedFileLabel = new QLabel(tr("No file selected"), this);
    m_selectedFileLabel->setProperty("role", "muted");
    fileRow->addWidget(m_chooseButton);
    fileRow->addWidget(m_selectedFileLabel, 1);
    layout->addLayout(fileRow);

    m_scanButton = new QPushButton(tr("Scan file"), this);
    m_scanButton->setProperty("role", "primary");
    m_scanButton->setEnabled(false);
    layout->addWidget(m_scanButton);

    m_progress = new QProgressBar(this);
    m_progress->setRange(0, 0); // busy/indeterminate while a request is in flight
    m_progress->setVisible(false);
    layout->addWidget(m_progress);

    layout->addSpacing(20);
    auto* lineLabel = new QLabel(tr("Or check a single log line:"), this);
    lineLabel->setObjectName("sectionLabel");
    layout->addWidget(lineLabel);

    auto* lineRow = new QHBoxLayout();
    m_logLineInput = new QLineEdit(this);
    m_logLineInput->setPlaceholderText(tr("paste a log line..."));
    m_checkLineButton = new QPushButton(tr("Check line"), this);
    lineRow->addWidget(m_logLineInput, 1);
    lineRow->addWidget(m_checkLineButton);
    layout->addLayout(lineRow);

    layout->addStretch();

    connect(m_chooseButton, &QPushButton::clicked, this, &ScanPage::onChooseFile);
    connect(m_scanButton, &QPushButton::clicked, this, &ScanPage::onScanClicked);
    connect(m_checkLineButton, &QPushButton::clicked, this, &ScanPage::onCheckLineClicked);

    connect(m_api, &ApiClient::fileScanResult, this,
            [this](const QString& context, const QString& path, const FileScanResult& result) {
                if (context != m_context) return;
                m_progress->setVisible(false);
                m_scanButton->setEnabled(true);
                emit fileScanReady(path, result);
            });
    connect(m_api, &ApiClient::fileScanError, this,
            [this](const QString& context, const QString& /*path*/, const QString& message) {
                if (context != m_context) return;
                m_progress->setVisible(false);
                m_scanButton->setEnabled(true);
                m_selectedFileLabel->setText(tr("Scan failed: %1").arg(message));
            });
    connect(m_api, &ApiClient::logScanResult, this,
            [this](const QString& context, const QString& line, const LogScanResult& result) {
                if (context != m_context) return;
                m_checkLineButton->setEnabled(true);
                emit logLineScanReady(line, result);
            });
    connect(m_api, &ApiClient::logScanError, this,
            [this](const QString& context, const QString& /*line*/, const QString& message) {
                if (context != m_context) return;
                m_checkLineButton->setEnabled(true);
                m_logLineInput->setPlaceholderText(tr("check failed: %1").arg(message));
            });
}

void ScanPage::onChooseFile() {
    const auto path = QFileDialog::getOpenFileName(this, tr("Choose a file to scan"));
    if (path.isEmpty()) return;
    m_selectedPath = path;
    m_selectedFileLabel->setProperty("role", QVariant());
    m_selectedFileLabel->style()->unpolish(m_selectedFileLabel);
    m_selectedFileLabel->style()->polish(m_selectedFileLabel);
    m_selectedFileLabel->setText(QFileInfo(path).fileName());
    m_scanButton->setEnabled(true);
}

void ScanPage::onScanClicked() {
    if (m_selectedPath.isEmpty()) return;
    m_scanButton->setEnabled(false);
    m_progress->setVisible(true);
    m_api->scanFile(m_selectedPath, m_context);
}

void ScanPage::onCheckLineClicked() {
    const auto line = m_logLineInput->text().trimmed();
    if (line.isEmpty()) return;
    m_checkLineButton->setEnabled(false);
    m_api->scanLogLine(line, m_context);
}
