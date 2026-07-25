#include <rakshak/pages/ScanResultPage.h>

#include <QtWidgets/QVBoxLayout>
#include <QtWidgets/QHBoxLayout>
#include <QtWidgets/QLabel>
#include <QtWidgets/QPushButton>
#include <QtWidgets/QStyle>

using namespace rakshak::pages;
using rakshak::backend::FileScanResult;
using rakshak::backend::LogScanResult;

namespace {
QLabel* monoLabel(QWidget* parent) {
    auto* l = new QLabel(parent);
    l->setProperty("role", "mono");
    l->setWordWrap(true);
    return l;
}
}

ScanResultPage::ScanResultPage(QWidget* parent) : QWidget(parent) {
    auto* layout = new QVBoxLayout(this);
    layout->setContentsMargins(48, 40, 48, 32);
    layout->setSpacing(8);

    auto* title = new QLabel(tr("Scan result"), this);
    title->setObjectName("pageTitle");
    layout->addWidget(title);

    m_subjectLabel = new QLabel(this);
    m_subjectLabel->setObjectName("statusSentence");
    m_subjectLabel->setWordWrap(true);
    layout->addWidget(m_subjectLabel);

    layout->addSpacing(12);

    m_verdictLabel = new QLabel(this);
    m_verdictLabel->setStyleSheet("font-size:17px; font-weight:600;");
    layout->addWidget(m_verdictLabel);

    m_scoreLabel = monoLabel(this);
    layout->addWidget(m_scoreLabel);
    m_modelLabel = monoLabel(this);
    layout->addWidget(m_modelLabel);
    m_shaLabel = monoLabel(this);
    layout->addWidget(m_shaLabel);

    m_reasonLabel = new QLabel(this);
    m_reasonLabel->setProperty("role", "muted");
    m_reasonLabel->setWordWrap(true);
    layout->addWidget(m_reasonLabel);

    m_quarantineLabel = new QLabel(this);
    m_quarantineLabel->setWordWrap(true);
    layout->addWidget(m_quarantineLabel);

    auto* buttonRow = new QHBoxLayout();
    auto* backButton = new QPushButton(tr("Back"), this);
    m_viewQuarantineButton = new QPushButton(tr("View quarantine"), this);
    m_viewQuarantineButton->setVisible(false);
    buttonRow->addWidget(backButton);
    buttonRow->addWidget(m_viewQuarantineButton);
    buttonRow->addStretch();
    layout->addLayout(buttonRow);
    layout->addStretch();

    connect(backButton, &QPushButton::clicked, this, &ScanResultPage::backRequested);
    connect(m_viewQuarantineButton, &QPushButton::clicked, this, &ScanResultPage::viewQuarantineRequested);
}

void ScanResultPage::applySeverity(bool alarmed) {
    m_verdictLabel->setProperty("severity", alarmed ? "critical" : "clean");
    m_verdictLabel->style()->unpolish(m_verdictLabel);
    m_verdictLabel->style()->polish(m_verdictLabel);
}

void ScanResultPage::setFileResult(const QString& path, const FileScanResult& result) {
    m_subjectLabel->setText(tr("File: %1").arg(path));
    m_verdictLabel->setText(result.malicious ? tr("Malicious") : tr("Clean"));
    applySeverity(result.malicious);
    m_scoreLabel->setText(tr("score %1  ·  confidence %2")
        .arg(result.score, 0, 'f', 3).arg(result.confidence, 0, 'f', 3));
    m_modelLabel->setText(tr("model: %1").arg(result.model));
    m_shaLabel->setText(tr("sha256: %1").arg(result.sha256));
    m_reasonLabel->setText(result.reason);

    if (result.quarantined) {
        m_quarantineLabel->setText(tr("Quarantined (id %1).").arg(result.quarantineId));
        m_viewQuarantineButton->setVisible(true);
    } else {
        m_quarantineLabel->setText(QString());
        m_viewQuarantineButton->setVisible(false);
    }
}

void ScanResultPage::setLogResult(const QString& line, const LogScanResult& result) {
    m_subjectLabel->setText(tr("Log line: %1").arg(line));
    m_verdictLabel->setText(result.suspicious ? tr("Suspicious") : tr("Clean"));
    applySeverity(result.suspicious);
    m_scoreLabel->setText(tr("score %1  ·  confidence %2")
        .arg(result.score, 0, 'f', 3).arg(result.confidence, 0, 'f', 3));
    m_modelLabel->setText(tr("model: %1").arg(result.model));
    m_shaLabel->setText(QString());
    m_reasonLabel->setText(result.reason);
    m_quarantineLabel->setText(QString());
    m_viewQuarantineButton->setVisible(false);
}
